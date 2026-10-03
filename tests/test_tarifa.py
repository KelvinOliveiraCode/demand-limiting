"""Testes do modelo tarifario.

Tests for the tariff model.
"""

from __future__ import annotations

import pytest

from demandlimit.tarifa import (
    FORA_PONTA,
    PONTA,
    Tarifa,
    custo_demanda,
    custo_energia,
    faixa_do_intervalo,
    janela_para_minutos,
    parse_horario,
)

JANELAS = [(480, 720), (840, 1200)]  # 08:00-12:00 e 14:00-20:00


def test_parse_horario_valido():
    """'HH:MM' vira minutos do dia.

    'HH:MM' becomes minutes of the day.
    """
    assert parse_horario("00:00") == 0
    assert parse_horario("08:00") == 480
    assert parse_horario("23:45") == 1425
    assert parse_horario(" 07:30 ") == 450


def test_parse_horario_invalido_levanta_erro():
    """Formato ou valor fora do dia viram erro bilingue.

    Bad format or out-of-day values raise.
    """
    with pytest.raises(ValueError, match="invalid time|fora do dia|fora da hora"):
        parse_horario("24:00")
    with pytest.raises(ValueError, match="invalid time|fora da hora"):
        parse_horario("08:60")
    with pytest.raises(ValueError, match="invalid time"):
        parse_horario("oito horas")


def test_janela_para_minutos_valida_ordem():
    """Janela com inicio >= fim e invalida.

    A window with start >= end is invalid.
    """
    assert janela_para_minutos("08:00", "12:00") == (480, 720)
    with pytest.raises(ValueError, match="invalid window|inicio >= fim"):
        janela_para_minutos("12:00", "08:00")


def test_faixa_ponta_e_fora_ponta():
    """Dentro da janela e PONTA; fora, FORA_PONTA.

    Inside a window it is ON_PEAK; outside, OFF_PEAK.
    """
    assert faixa_do_intervalo(480, JANELAS) == PONTA
    assert faixa_do_intervalo(719, JANELAS) == PONTA
    assert faixa_do_intervalo(840, JANELAS) == PONTA
    assert faixa_do_intervalo(1199, JANELAS) == PONTA
    assert faixa_do_intervalo(479, JANELAS) == FORA_PONTA
    assert faixa_do_intervalo(720, JANELAS) == FORA_PONTA
    assert faixa_do_intervalo(1200, JANELAS) == FORA_PONTA
    assert faixa_do_intervalo(1439, JANELAS) == FORA_PONTA
    assert faixa_do_intervalo(0, JANELAS) == FORA_PONTA


def test_tarifa_energia_por_faixa():
    """A tarifa devolve o valor da faixa pedida.

    The tariff returns the rate of the asked band.
    """
    tarifa = Tarifa(0.742, 0.568, 31.40, 30.0)
    assert tarifa.tarifa_energia(PONTA) == 0.742
    assert tarifa.tarifa_energia(FORA_PONTA) == 0.568


def test_custo_energia_por_faixa_e_erro_negativo():
    """kWh x tarifa; energia negativa e erro.

    kWh x rate; negative energy raises.
    """
    tarifa = Tarifa(0.742, 0.568, 31.40, 30.0)
    assert custo_energia(10.0, PONTA, tarifa) == pytest.approx(7.42)
    assert custo_energia(10.0, FORA_PONTA, tarifa) == pytest.approx(5.68)
    with pytest.raises(ValueError, match="negative energy|Energia negativa"):
        custo_energia(-1.0, PONTA, tarifa)


def test_custo_demanda_dentro_do_contrato():
    """Sem excedente: fatura a demanda contratada e multa zero.

    No excess: bill the contracted demand and zero fine.
    """
    tarifa = Tarifa(0.742, 0.568, 31.40, 30.0)
    custo, multa = custo_demanda(250.0, 260.0, tarifa)
    assert custo == pytest.approx(260.0 * 31.40)
    assert multa == 0.0


def test_custo_demanda_com_excedente_aplica_multa_30():
    """Excedente: fatura o pico e multa de 30% sobre o excedente.

    Excess: bill the peak and a 30% fine on the excess.
    """
    tarifa = Tarifa(0.742, 0.568, 31.40, 30.0)
    custo, multa = custo_demanda(300.0, 260.0, tarifa)
    assert custo == pytest.approx(300.0 * 31.40)
    assert multa == pytest.approx(40.0 * 31.40 * 0.30)


def test_custo_demanda_invalidos_levantam_erro():
    """Demanda negativa ou contrato nulo viram erro.

    Negative demand or zero contract raise.
    """
    tarifa = Tarifa(0.742, 0.568, 31.40, 30.0)
    with pytest.raises(ValueError, match="negative demand|Demanda negativa"):
        custo_demanda(-5.0, 260.0, tarifa)
    with pytest.raises(ValueError, match="positiva|positive"):
        custo_demanda(250.0, 0.0, tarifa)
