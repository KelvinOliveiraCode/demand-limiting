"""Testes da simulacao mensal com e sem corte.

Tests for the monthly simulation with and without cut.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from demandlimit.corte import carregar_cargas
from demandlimit.demanda import carregar_contrato, carregar_curva
from demandlimit.simulador import comparar, simular

RAIZ = Path(__file__).resolve().parents[1]


def simulacao_real():
    """Carrega o dado real e roda as duas simulacoes.

    Load the real data and run both simulations.
    """
    cargas = carregar_cargas(RAIZ / "dados" / "cargas.yaml")
    contrato = carregar_contrato(RAIZ / "dados" / "contrato.yaml")
    curva = carregar_curva(RAIZ / "dados" / "curva-de-carga.csv", cargas)
    sem = simular(curva, contrato, cargas, com_corte=False)
    com = simular(curva, contrato, cargas, com_corte=True)
    return curva, contrato, cargas, sem, com


def test_simular_sem_corte_estoura_no_dado_real():
    """No dado real, sem corte o mes estoura a demanda contratada.

    On the real data, without cut the month exceeds the contract.
    """
    _c, contrato, _x, sem, _y = simulacao_real()
    assert sem.demanda_mensal_kw > contrato.demanda_contratada_kw
    assert sem.multa > 0
    assert sem.custo_demanda > contrato.demanda_contratada_kw * contrato.tarifa.demanda_rpor_kw


def test_simular_com_corte_fica_dentro_do_contrato():
    """Com corte, o pico mensal fica dentro da demanda contratada.

    With cut, the monthly peak stays within the contracted demand.
    """
    _c, contrato, _x, _sem, com = simulacao_real()
    assert com.demanda_mensal_kw <= contrato.demanda_contratada_kw + 1e-6
    assert com.multa == 0.0


def test_economia_igual_diferenca_de_custos():
    """A economia e a diferenca exata dos custos totais.

    The saving is the exact difference of the total costs.
    """
    _c, _k, _x, sem, com = simulacao_real()
    comp = comparar(sem, com)
    assert comp.economia == pytest.approx(sem.custo_total - com.custo_total)
    assert comp.multa_evitada == pytest.approx(sem.multa - com.multa)
    assert comp.economia > 0


def test_energia_cortada_bate_com_cortes_por_carga():
    """Energia com corte = energia sem corte menos os kWh cortados.

    Energy with cut = energy without cut minus the cut kWh.
    """
    curva, _k, _x, sem, com = simulacao_real()
    cortados = sum(com.cortes_por_carga_kwh.values())
    assert sem.energia_kwh - com.energia_kwh == pytest.approx(cortados, abs=1e-6)
    assert cortados > 0
    # Iluminacao (prioridade 1) nao entra nos cortes.
    for nome in curva.cargas:
        if nome.startswith("Iluminacao"):
            assert com.cortes_por_carga_kwh[nome] == 0.0


def test_simulacao_eh_deterministica():
    """Duas execucoes com o mesmo input dao o mesmo resultado.

    Two runs with the same input give the same result.
    """
    cargas = carregar_cargas(RAIZ / "dados" / "cargas.yaml")
    contrato = carregar_contrato(RAIZ / "dados" / "contrato.yaml")
    curva1 = carregar_curva(RAIZ / "dados" / "curva-de-carga.csv", cargas)
    curva2 = carregar_curva(RAIZ / "dados" / "curva-de-carga.csv", cargas)
    a = simular(curva1, contrato, cargas, com_corte=True)
    b = simular(curva2, contrato, cargas, com_corte=True)
    assert a.demanda_mensal_kw == b.demanda_mensal_kw
    assert a.energia_kwh == b.energia_kwh
    assert a.custo_total == b.custo_total
    assert a.picos_diarios == b.picos_diarios
