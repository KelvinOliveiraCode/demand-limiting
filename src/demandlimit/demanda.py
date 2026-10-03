"""Curva de carga e contrato de demanda.

Load curve and demand contract loading.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Sequence

import yaml

from .tarifa import Tarifa, janela_para_minutos

# Constantes do modelo / model constants
DIA_BASE = date(2026, 1, 1)
N_INTERVALOS_POR_DIA = 96
COLUNAS_OBRIGATORIAS = ("data", "intervalo", "hora", "carga", "potencia_kw")


@dataclass
class Curva:
    """Curva de carga: potencia por carga e por intervalo de 15 min.

    Load curve: power per load and per 15-minute interval.
    """

    dias: list[date]
    cargas: list[str]
    potencia: dict[str, list[float]] = field(default_factory=dict)

    @property
    def n_dias(self) -> int:
        """Numero de dias da curva.

        Number of days in the curve.
        """
        return len(self.dias)

    @property
    def n_intervalos(self) -> int:
        """Total de intervalos (dias x 96).

        Total intervals (days x 96).
        """
        return self.n_dias * N_INTERVALOS_POR_DIA

    def total_no_intervalo(self, idx: int) -> float:
        """Soma das potencias de todas as cargas no intervalo (kW).

        Sum of all load powers at the interval (kW).
        """
        if not 0 <= idx < self.n_intervalos:
            raise IndexError(f"Intervalo fora do periodo / interval out of range: {idx}")
        return sum(vals[idx] for vals in self.potencia.values())

    def data_do_intervalo(self, idx: int) -> date:
        """Data (dia) do intervalo.

        Date (day) of the interval.
        """
        return self.dias[idx // N_INTERVALOS_POR_DIA]

    def minutos_do_intervalo(self, idx: int) -> int:
        """Minutos do dia (0 a 1439) do intervalo.

        Minutes of the day (0 to 1439) of the interval.
        """
        return (idx % N_INTERVALOS_POR_DIA) * 15

    def pico_dia(self, dia_index: int) -> tuple[float, int]:
        """Maior total de 15 min dentro do dia.

        Highest 15-minute total within the day.
        """
        inicio = dia_index * N_INTERVALOS_POR_DIA
        fim = inicio + N_INTERVALOS_POR_DIA
        indice = max(range(inicio, fim), key=lambda i: self.total_no_intervalo(i))
        return self.total_no_intervalo(indice), indice

    def demanda_mensal(self) -> tuple[float, int]:
        """Maior total de 15 min de todo o periodo (a demanda do mes).

        Highest 15-minute total of the whole period (the monthly demand).
        """
        indice = max(range(self.n_intervalos), key=lambda i: self.total_no_intervalo(i))
        return self.total_no_intervalo(indice), indice


def carregar_curva(caminho: str | Path, cargas_esperadas: Sequence[str | object]) -> Curva:
    """Lê o CSV de curva de carga e valida a estrutura.

    Read the load curve CSV and validate its structure.

    Colunas: data, intervalo, hora, carga, potencia_kw.
    O CSV precisa ter exatamente 96 intervalos por dia (0 a 95), uma
    linha por carga por intervalo, e so cargas da lista esperada.
    A lista esperada pode ser nomes (str) ou objetos Carga.
    Columns: data, intervalo, hora, carga, potencia_kw.
    The CSV must have exactly 96 intervals per day (0 to 95), one row
    per load per interval, and only loads from the expected list.
    The expected list may be names (str) or Carga objects.
    """
    # Aceita str ou objeto com .nome (Carga).
    # Accepts str or objects with .nome (Carga).
    esperadas = [getattr(c, "nome", c) for c in cargas_esperadas]
    registros: list[dict[str, str]] = []
    with Path(caminho).open("r", encoding="utf-8", newline="") as arq:
        leitor = csv.DictReader(arq)
        colunas = leitor.fieldnames or []
        faltando = [c for c in COLUNAS_OBRIGATORIAS if c not in colunas]
        if faltando:
            raise ValueError(
                "CSV sem colunas obrigatorias / CSV missing required columns: "
                + ", ".join(faltando)
            )
        for linha in leitor:
            registros.append(linha)

    if not registros:
        raise ValueError("CSV vazio / empty CSV: " + str(caminho))

    potencias: dict[tuple[str, int, int], float] = {}
    datas: set[str] = set()
    for n, linha in enumerate(registros, start=2):
        try:
            data_txt = linha["data"].strip()
            date.fromisoformat(data_txt)
            intervalo = int(linha["intervalo"])
            hora_txt = linha["hora"].strip()
            hora_s, minuto_s = hora_txt.split(":")
            horas = int(hora_s)
            minutos = int(minuto_s)
            carga = linha["carga"].strip()
            potencia = float(linha["potencia_kw"])
        except (ValueError, TypeError) as exc:
            raise ValueError(
                f"CSV linha {n} mal formada / malformed CSV row: {exc}"
            ) from exc
        if not 0 <= intervalo < N_INTERVALOS_POR_DIA:
            raise ValueError(
                f"CSV linha {n}: intervalo fora de 0-95 / out of range: {intervalo}"
            )
        minutos_esperado = intervalo * 15
        if horas * 60 + minutos != minutos_esperado:
            raise ValueError(
                f"CSV linha {n}: hora {hora_txt} nao confere com o intervalo {intervalo} "
                f"/ time does not match interval"
            )
        if carga not in esperadas:
            raise ValueError(
                f"CSV linha {n}: carga desconhecida / unknown load: {carga!r}. "
                f"Esperadas: {', '.join(esperadas)}"
            )
        if potencia < 0:
            raise ValueError(f"CSV linha {n}: potencia negativa / negative power")
        chave = (data_txt, intervalo, esperadas.index(carga))
        if chave in potencias:
            raise ValueError(
                f"CSV linha {n}: registro duplicado / duplicate record "
                f"({data_txt}, intervalo {intervalo}, {carga})"
            )
        potencias[chave] = potencia
        datas.add(data_txt)

    # Um dia so existe no CSV se todas as cargas dele estao presentes.
    # A checagem final garante 96 registros por carga por dia.
    dias_txt = sorted(datas)
    if len(dias_txt) == 0:
        raise ValueError("CSV sem dias / no days in CSV")
    for dia_txt in dias_txt:
        for carga_i in range(len(esperadas)):
            faltantes = [
                i
                for i in range(N_INTERVALOS_POR_DIA)
                if (dia_txt, i, carga_i) not in potencias
            ]
            if faltantes:
                primeiro = faltantes[0]
                raise ValueError(
                    f"CSV: dia {dia_txt} incompleto / incomplete day - falta "
                    f"intervalo {primeiro} de {esperadas[carga_i]} "
                    f"({len(faltantes)} registros faltando / missing)"
                )

    dias = [date.fromisoformat(t) for t in dias_txt]
    potencia_por_carga: dict[str, list[float]] = {}
    for carga in esperadas:
        pos = esperadas.index(carga)
        serie: list[float] = []
        for dia_txt in dias_txt:
            serie.extend(potencias[(dia_txt, i, pos)] for i in range(N_INTERVALOS_POR_DIA))
        potencia_por_carga[carga] = serie
    return Curva(dias=dias, cargas=list(esperadas), potencia=potencia_por_carga)


@dataclass(frozen=True)
class Contrato:
    """Contrato de demanda: limite, tarifas e janelas de ponta.

    Demand contract: limit, tariffs and on-peak windows.
    """

    unidade: str
    demanda_contratada_kw: float
    tarifa: Tarifa
    janelas_ponta: tuple[tuple[int, int], ...]
    tempo_minimo_acionamento_minutos: int


def carregar_contrato(caminho: str | Path) -> Contrato:
    """Lê o YAML do contrato e valida os campos.

    Read the contract YAML and validate its fields.
    """
    dados = yaml.safe_load(Path(caminho).read_text(encoding="utf-8"))
    if not isinstance(dados, dict):
        raise ValueError("Contrato vazio ou invalido / empty or invalid contract YAML")
    try:
        contrato = Contrato(
            unidade=str(dados.get("unidade", "UTA-DEMO")),
            demanda_contratada_kw=float(dados["demanda_contratada_kw"]),
            tarifa=Tarifa(
                energia_ponta=float(dados["tarifas"]["energia_ponta_rpor_kwh"]),
                energia_fora_ponta=float(dados["tarifas"]["energia_fora_ponta_rpor_kwh"]),
                demanda_rpor_kw=float(dados["tarifas"]["demanda_rpor_kw"]),
                multa_percentual=float(dados["tarifas"]["multa_percentual"]),
            ),
            janelas_ponta=tuple(
                janela_para_minutos(i, f)
                for i, f in (dados.get("faixa_ponta") or [])
            ),
            tempo_minimo_acionamento_minutos=int(
                dados.get("tempo_minimo_acionamento_minutos", 30)
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            f"Contrato invalido / invalid contract YAML ({caminho}): {exc}"
        ) from exc
    if contrato.demanda_contratada_kw <= 0:
        raise ValueError("Demanda contratada deve ser positiva / must be positive")
    if contrato.tempo_minimo_acionamento_minutos < 15:
        raise ValueError(
            "Tempo minimo de acionamento menor que um intervalo / "
            "below one interval: "
            + str(contrato.tempo_minimo_acionamento_minutos)
        )
    return contrato
