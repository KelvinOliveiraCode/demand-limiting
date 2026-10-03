"""Testes do relatorio de corte em Markdown.

Tests for the Markdown cut report.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from demandlimit.corte import carregar_cargas, planejar_cortes
from demandlimit.demanda import carregar_contrato, carregar_curva
from demandlimit.relatorio import gerar_relatorio
from demandlimit.simulador import simular

RAIZ = Path(__file__).resolve().parents[1]


def _relatorio() -> tuple[str, float, float]:
    """Gera o relatorio com o dado real.

    Generate the report with the real data.
    """
    cargas = carregar_cargas(RAIZ / "dados" / "cargas.yaml")
    contrato = carregar_contrato(RAIZ / "dados" / "contrato.yaml")
    curva = carregar_curva(RAIZ / "dados" / "curva-de-carga.csv", cargas)
    plano = planejar_cortes(
        curva, cargas, contrato.demanda_contratada_kw,
        contrato.tempo_minimo_acionamento_minutos // 15,
    )
    sem = simular(curva, contrato, cargas, com_corte=False)
    com = simular(curva, contrato, cargas, com_corte=True)
    texto = gerar_relatorio(curva, contrato, cargas, plano, sem, com)
    return texto, contrato.demanda_contratada_kw, com.demanda_mensal_kw


def _valor(texto: str, chave: str) -> float:
    """Lê um valor da secao de conferencia.

    Read one value from the arithmetic-check section.
    """
    padrao = rf"^- {re.escape(chave)}: R?\\?\$? ?([0-9.,]+)"
    m = re.search(padrao, texto, flags=re.M)
    assert m is not None, f"chave ausente / missing key: {chave}"
    bruto = m.group(1).replace("R$", "").replace(",", "").strip()
    return float(bruto)


def test_relatorio_conta_campos_obrigatorios():
    """O relatorio tem resumo, dias de pico e conferencia.

    The report has the summary, peak days and the check section.
    """
    texto, _contratada, _com = _relatorio()
    for secao in (
        "## Resumo mensal",
        "## Dias de pico",
        "## Cortes no mes",
        "## Conferencia aritmetica",
        "Economia do mes",
        "Multa evitada",
    ):
        assert secao in texto, secao
    # Ao menos um dia de pico detalhado / at least one detailed peak day
    assert re.search(r"^### Dia 1 - \d{4}-\d{2}-\d{2}", texto, flags=re.M)
    assert "Corte aplicado por carga" in texto


def test_relatorio_consistencia_aritmetica():
    """economia == custo total sem corte - custo total com corte.

    saving == total cost without cut - total cost with cut.
    """
    texto, _contratada, _com = _relatorio()
    sem = _valor(texto, "custo_total_sem_corte")
    com = _valor(texto, "custo_total_com_corte")
    economia = _valor(texto, "economia")
    assert economia == pytest.approx(sem - com, abs=0.011)

    multa_sem = _valor(texto, "multa_sem_corte")
    multa_com = _valor(texto, "multa_com_corte")
    multa_evitada = _valor(texto, "multa_evitada")
    assert multa_evitada == pytest.approx(multa_sem - multa_com, abs=0.011)
    assert multa_sem > 0
    assert multa_com == 0.0


def test_relatorio_pico_com_corte_dentro_do_contrato():
    """O pico com corte nao passa da demanda contratada.

    The peak with cut does not pass the contracted demand.
    """
    texto, contratada, com = _relatorio()
    pico_com = _valor(texto, "demanda_mensal_com_corte")
    assert pico_com <= contratada + 1e-6
    assert com <= contratada + 1e-6
    pico_sem = _valor(texto, "demanda_mensal_sem_corte")
    assert pico_sem > contratada


def test_relatorio_energia_com_corte_menor():
    """Cortar consome menos energia.

    Cutting consumes less energy.
    """
    texto, _contratada, _com = _relatorio()
    sem = _valor(texto, "energia_sem_corte")
    com = _valor(texto, "energia_com_corte")
    assert 0 < com < sem


def test_relatorio_dia_plantado_aparece():
    """O dia 21/01 (pico plantado) aparece nos dias de pico.

    The planted peak day 2026-01-21 shows up in the peak days.
    """
    texto, _contratada, _com = _relatorio()
    assert "2026-01-21" in texto
