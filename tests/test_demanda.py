"""Testes da curva de carga e do contrato.

Tests for the load curve and the contract.
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import pytest

from demandlimit.demanda import (
    N_INTERVALOS_POR_DIA,
    Curva,
    carregar_contrato,
    carregar_curva,
)

RAIZ = Path(__file__).resolve().parents[1]
CURVA_REAL = RAIZ / "dados" / "curva-de-carga.csv"
CONTRATO_REAL = RAIZ / "dados" / "contrato.yaml"
CARGAS_REAL = RAIZ / "dados" / "cargas.yaml"

DOIS_CARGAS = ["Carga-1", "Carga-2"]


def escrever_csv(caminho: Path, dados: list[tuple[str, int, str, str, float]]) -> None:
    """Grava os registros no CSV.

    Write the records into the CSV.
    """
    with caminho.open("w", encoding="utf-8", newline="") as arq:
        escritor = csv.writer(arq, lineterminator="\n")
        escritor.writerow(["data", "intervalo", "hora", "carga", "potencia_kw"])
        for data, i, hora, carga, kw in dados:
            escritor.writerow([data, i, hora, carga, f"{kw:.3f}"])


def linha_completa(cargas: list[str]) -> list[tuple[str, int, str, str, float]]:
    """Um dia completo com as cargas dadas.

    A full day with the given loads.
    """
    dados = []
    for i in range(N_INTERVALOS_POR_DIA):
        hora = f"{i // 4:02d}:{(i % 4) * 15:02d}"
        for n, carga in enumerate(cargas):
            dados.append(("2026-01-01", i, hora, carga, 10.0 + n))
    return dados


def test_carregar_curva_real_23040_registros():
    """O CSV do repositario tem 30 dias x 96 intervalos x 8 cargas.

    The repository CSV has 30 days x 96 intervals x 8 loads.
    """
    from demandlimit.corte import carregar_cargas

    cargas = carregar_cargas(CARGAS_REAL)
    curva = carregar_curva(CURVA_REAL, cargas)
    assert curva.n_dias == 30
    assert len(curva.cargas) == 8
    assert curva.n_intervalos == 2880
    assert all(len(serie) == 2880 for serie in curva.potencia.values())
    assert all(kw >= 0 for serie in curva.potencia.values() for kw in serie)


def test_carregar_curva_rejeita_carga_desconhecida(tmp_path: Path):
    """Carga fora da lista esperada e erro.

    A load outside the expected list is an error.
    """
    dados = linha_completa(["Carga-X"])
    caminho = tmp_path / "curva.csv"
    escrever_csv(caminho, dados)
    with pytest.raises(ValueError, match="carga desconhecida|unknown load"):
        carregar_curva(caminho, DOIS_CARGAS)


def test_carregar_curva_rejeita_potencia_negativa(tmp_path: Path):
    """Potencia negativa e erro.

    Negative power is an error.
    """
    dados = linha_completa(DOIS_CARGAS)
    dados[100] = ("2026-01-01", 10, "02:30", "Carga-1", -1.0)
    caminho = tmp_path / "curva.csv"
    escrever_csv(caminho, dados)
    with pytest.raises(ValueError, match="potencia negativa|negative power"):
        carregar_curva(caminho, DOIS_CARGAS)


def test_carregar_curva_rejeita_intervalo_faltante(tmp_path: Path):
    """Dia com menos de 96 intervalos e erro.

    A day with fewer than 96 intervals is an error.
    """
    dados = linha_completa(DOIS_CARGAS)[:-2]  # tira o ultimo intervalo (95)
    caminho = tmp_path / "curva.csv"
    escrever_csv(caminho, dados)
    with pytest.raises(ValueError, match="incompleto|incomplete"):
        carregar_curva(caminho, DOIS_CARGAS)


def test_carregar_curva_rejeita_registro_duplicado(tmp_path: Path):
    """Dois registros da mesma carga no mesmo intervalo e erro.

    Two records for the same load and interval is an error.
    """
    dados = linha_completa(DOIS_CARGAS)
    dados.append(dados[0])  # duplica o primeiro registro
    caminho = tmp_path / "curva.csv"
    escrever_csv(caminho, dados)
    with pytest.raises(ValueError, match="duplicado|duplicate"):
        carregar_curva(caminho, DOIS_CARGAS)


def test_pico_dia_e_dia_total_coerentes():
    """O pico mensal e o maior dos picos diarios.

    The monthly peak is the largest of the daily peaks.
    """
    from demandlimit.corte import carregar_cargas

    cargas = carregar_cargas(CARGAS_REAL)
    curva = carregar_curva(CURVA_REAL, cargas)
    picos_diarios = [curva.pico_dia(d)[0] for d in range(curva.n_dias)]
    demanda_mensal, _idx = curva.demanda_mensal()
    assert demanda_mensal == pytest.approx(max(picos_diarios))
    assert demanda_mensal > 0


def test_total_no_intervalo_fora_do_periodo_levanta_erro():
    """Indice fora do periodo e erro.

    An index outside the period is an error.
    """
    curva = Curva(
        dias=[date(2026, 1, 1)],
        cargas=["A"],
        potencia={"A": [1.0] * N_INTERVALOS_POR_DIA},
    )
    with pytest.raises(IndexError, match="out of range|fora do periodo"):
        curva.total_no_intervalo(curva.n_intervalos)


def test_carregar_contrato_e_cargas_reais():
    """O contrato e as cargas do repositario carregam com os valores certos.

    The repository contract and loads load with the right values.
    """
    from demandlimit.corte import carregar_cargas

    contrato = carregar_contrato(CONTRATO_REAL)
    assert contrato.demanda_contratada_kw == 260.0
    assert contrato.tarifa.multa_percentual == 30.0
    assert contrato.janelas_ponta == ((480, 720), (840, 1200))
    assert contrato.tempo_minimo_acionamento_minutos == 30

    cargas = carregar_cargas(CARGAS_REAL)
    assert len(cargas) == 8
    por_tipo: dict[str, int] = {}
    for carga in cargas:
        por_tipo[carga.tipo] = por_tipo.get(carga.tipo, 0) + 1
    assert por_tipo == {"iluminacao": 2, "climatizacao": 3, "producao": 3}
    assert sorted({c.prioridade for c in cargas}) == [1, 2, 3]
