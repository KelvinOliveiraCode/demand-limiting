"""Critério de aceite do projeto P19.

Acceptance criterion of project P19.

Sem corte a simulacao estoura a demanda contratada; com corte nao; e a
economia bate com o detalhamento (custo total sem corte menos custo
total com corte).
Without cut the simulation exceeds the contracted demand; with cut it
does not; and the saving matches the detail (total cost without cut
minus total cost with cut).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from demandlimit.corte import carregar_cargas
from demandlimit.demanda import carregar_contrato, carregar_curva
from demandlimit.simulador import comparar, simular

RAIZ = Path(__file__).resolve().parents[1]


def _todas():
    cargas = carregar_cargas(RAIZ / "dados" / "cargas.yaml")
    contrato = carregar_contrato(RAIZ / "dados" / "contrato.yaml")
    curva = carregar_curva(RAIZ / "dados" / "curva-de-carga.csv", cargas)
    sem = simular(curva, contrato, cargas, com_corte=False)
    com = simular(curva, contrato, cargas, com_corte=True)
    return curva, contrato, cargas, sem, com


def test_criterio_de_aceite():
    """Sem corte estoura, com corte nao, e a economia confere.

    Without cut it exceeds; with cut it does not; the saving matches.
    """
    _c, contrato, _x, sem, com = _todas()
    # 1) Sem corte, a demanda mensal estoura o contrato.
    # Without cut, the monthly demand exceeds the contract.
    assert sem.demanda_mensal_kw > contrato.demanda_contratada_kw
    assert sem.multa > 0
    # 2) Com corte, fica dentro.
    # With cut, it stays inside.
    assert com.demanda_mensal_kw <= contrato.demanda_contratada_kw + 1e-6
    assert com.multa == 0.0
    # 3) A economia confere com a diferenca dos custos.
    # The saving matches the cost difference.
    comp = comparar(sem, com)
    assert comp.economia == pytest.approx(sem.custo_total - com.custo_total)
    assert comp.economia > 0
    assert comp.multa_evitada == pytest.approx(sem.multa)


def test_dia_plantado_estoura_contratada():
    """Existe ao menos um dia cujo pico sem corte passa da contratada.

    At least one day has an uncut peak above the contracted demand.
    """
    curva, contrato, _x, _sem, _com = _todas()
    excedidos = [
        curva.pico_dia(d)[0]
        for d in range(curva.n_dias)
        if curva.pico_dia(d)[0] > contrato.demanda_contratada_kw
    ]
    assert len(excedidos) >= 1


def test_pico_mensal_bate_com_corte_intervalo_a_intervalo():
    """A demanda mensal com corte e o maximo da curva ja cortada.

    The monthly demand with cut is the max of the cut curve.
    """
    curva, contrato, cargas, _sem, com = _todas()
    from demandlimit.corte import planejar_cortes
    from demandlimit.simulador import demanda_com_corte

    plano = planejar_cortes(
        curva,
        cargas,
        contrato.demanda_contratada_kw,
        contrato.tempo_minimo_acionamento_minutos // 15,
    )
    efetivos = [
        demanda_com_corte(curva, plano, idx)
        for idx in range(curva.n_intervalos)
    ]
    assert com.demanda_mensal_kw == pytest.approx(max(efetivos))
