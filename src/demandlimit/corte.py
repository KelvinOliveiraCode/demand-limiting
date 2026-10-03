"""Algoritmo de corte de demanda com prioridade e tempo minimo.

Demand cut algorithm with priority and minimum actuation time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .demanda import Curva

# Tolerancia de ponto flutuante para comparacoes / float tolerance
EPS = 1e-6


@dataclass(frozen=True)
class Carga:
    """Carga cortavel: tipo, prioridade e teto de corte.

    Curtailable load: type, priority and cut ceiling.

    prioridade: 1 = nao cortar, 2 = cortar parcialmente (antes),
                3 = cortar por ultimo.
    priority:   1 = never cut, 2 = cut partially (first), 3 = cut last.
    recorte_maximo_percent: 0 a 100; maior fracao da potencia cortavel.
    recorte_maximo_percent: 0 to 100; max share of power that can be cut.
    """

    nome: str
    tipo: str
    prioridade: int
    recorte_maximo_percent: float

    def pode_cortar(self) -> bool:
        """Se a carga admite corte.

        Whether the load may be cut.
        """
        return self.recorte_maximo_percent > 0 and self.prioridade > 1


def carregar_cargas(caminho: str | Path) -> list[Carga]:
    """Lê o YAML das cargas e valida a estrutura.

    Read the loads YAML and validate its structure.
    """
    dados = yaml.safe_load(Path(caminho).read_text(encoding="utf-8"))
    if not isinstance(dados, dict) or not isinstance(dados.get("cargas"), list):
        raise ValueError(
            f"YAML de cargas invalido / invalid loads YAML: {caminho}. "
            "Esperado: lista de 'cargas' / expected: a 'cargas' list."
        )
    vistos: set[str] = set()
    cargas: list[Carga] = []
    for item in dados["cargas"]:
        try:
            carga = Carga(
                nome=str(item["nome"]).strip(),
                tipo=str(item["tipo"]).strip(),
                prioridade=int(item["prioridade"]),
                recorte_maximo_percent=float(item["recorte_maximo_percent"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"Carga invalida / invalid load entry: {exc}"
            ) from exc
        if not carga.nome:
            raise ValueError("Carga sem nome / load without name")
        if carga.nome in vistos:
            raise ValueError(f"Carga duplicada / duplicate load: {carga.nome}")
        if carga.prioridade < 1:
            raise ValueError(
                f"Prioridade invalida / invalid priority: {carga.prioridade}"
            )
        if not 0 <= carga.recorte_maximo_percent <= 100:
            raise ValueError(
                f"Recorte fora de 0-100 / out of range: "
                f"{carga.recorte_maximo_percent} ({carga.nome})"
            )
        vistos.add(carga.nome)
        cargas.append(carga)
    if not cargas:
        raise ValueError("Sem cargas no YAML / no loads in YAML")
    return cargas


@dataclass
class PlanoCorte:
    """Plano de corte aplicado ao periodo.

    Cut plan applied over the period.
    """

    cortes: dict[str, list[float]] = field(default_factory=dict)
    acoes: dict[str, int] = field(default_factory=dict)

    def corte_no(self, idx: int) -> dict[str, float]:
        """Cortes (kW) por carga no intervalo dado.

        Cuts (kW) per load at the given interval.
        """
        return {nome: serie[idx] for nome, serie in self.cortes.items()}

    def kWh_cortados(self, carga: str) -> float:
        """Energia total cortada da carga no periodo (kWh).

        Total energy cut from the load over the period (kWh).
        """
        serie = self.cortes.get(carga, [])
        return sum(serie) * 0.25

    def total_kWh_cortados(self) -> float:
        """Energia cortada em todas as cargas (kWh).

        Energy cut across all loads (kWh).
        """
        return sum(self.kWh_cortados(nome) for nome in self.cortes)


def planejar_cortes(
    curva: Curva,
    cargas: list[Carga],
    contratada_kw: float,
    tempo_minimo_intervalos: int,
) -> PlanoCorte:
    """Planeja o corte intervalo a intervalo.

    Plan the cut interval by interval.

    A cada intervalo a soma das potencias (menos o corte ja ativo) e
    comparada com a demanda contratada. O excedente e cortado em ordem
    de prioridade: iluminacao nunca; climatizacao parcialmente;
    producao por ultimo. Uma carga cortada fica cortada por pelo
    menos `tempo_minimo_intervalos` intervalos (tempo minimo de
    acionamento), para evitar liga/desliga constante.
    Each interval, the sum of powers (minus the cut already active) is
    compared to the contracted demand. The excess is cut in priority
    order: lighting never; air conditioning partially; production last.
    A cut load stays cut for at least `tempo_minimo_intervalos`
    intervals (minimum actuation time), to avoid constant on/off.
    """
    n = curva.n_intervalos
    if not 0 < tempo_minimo_intervalos:
        raise ValueError("Tempo minimo deve ser positivo / must be positive")

    nomes = [c.nome for c in cargas]
    # Ordem de corte: prioridade menor first, nome quebra empate.
    # Cut order: lower priority number first, name breaks ties.
    ordem = sorted(cargas, key=lambda c: (c.prioridade, c.nome))

    cortes: dict[str, list[float]] = {nome: [0.0] * n for nome in nomes}
    acoes: dict[str, int] = {nome: 0 for nome in nomes}
    nivel: dict[str, float] = {nome: 0.0 for nome in nomes}
    liberar_em: dict[str, int] = {nome: -1 for nome in nomes}

    for idx in range(n):
        # 1) Libera cortes cujo tempo minimo ja expirou.
        # Release cuts whose minimum time has expired.
        for nome in nomes:
            if nivel[nome] > 0 and idx > liberar_em[nome]:
                nivel[nome] = 0.0
                cortes[nome][idx] = 0.0

        # 2) Excedente sobre a demanda contratada, ja descontando corte ativo.
        # Excess over the contracted demand, already net of active cuts.
        total_corte = sum(nivel.values())
        excedente = curva.total_no_intervalo(idx) - total_corte - contratada_kw
        if excedente <= EPS:
            # Nao precisa cortar; apenas acompanha o corte ativo (ou zero).
            # No cut needed; just track the active cut (or zero).
            for nome in nomes:
                cortes[nome][idx] = nivel[nome]
            continue

        # 3) Corta em ordem de prioridade ate cobrir o excedente.
        # Cut in priority order until the excess is covered.
        for carga in ordem:
            if excedente <= EPS:
                break
            if not carga.pode_cortar():
                continue
            capacidade = (
                curva.potencia[carga.nome][idx]
                * carga.recorte_maximo_percent
                / 100.0
            )
            delta = min(excedente, capacidade - nivel[carga.nome])
            if delta <= EPS:
                continue
            era_zero = nivel[carga.nome] <= EPS
            nivel[carga.nome] += delta
            cortes[carga.nome][idx] = nivel[carga.nome]
            liberar_em[carga.nome] = idx + tempo_minimo_intervalos - 1
            if era_zero:
                acoes[carga.nome] += 1
            excedente -= delta

        # 4) Se nao deu para cobrir tudo, o excedente sobra para a demanda.
        # If it could not be fully covered, the rest hits the demand.
    return PlanoCorte(cortes=cortes, acoes=acoes)
