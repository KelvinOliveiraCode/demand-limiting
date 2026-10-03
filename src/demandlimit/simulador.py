"""Simulacao mensal com e sem corte de demanda.

Monthly simulation with and without demand cut.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .corte import Carga, PlanoCorte, planejar_cortes
from .demanda import Contrato, Curva, N_INTERVALOS_POR_DIA
from .tarifa import custo_demanda, faixa_do_intervalo


@dataclass
class PicoDia:
    """Pico de um dia e o corte ativo no intervalo do pico.

    A day's peak and the cut active at the peak interval.
    """

    data: str
    indice: int
    demanda_kw: float
    demanda_com_corte_kw: float
    corte_no_pico: dict[str, float] = field(default_factory=dict)


@dataclass
class ResultadoSimulacao:
    """Resultado de um mes simulado.

    Result of one simulated month.
    """

    com_corte: bool
    demanda_mensal_kw: float
    indice_pico: int
    energia_kwh: float
    custo_energia: float
    custo_demanda: float
    multa: float
    custo_total: float
    picos_diarios: list[PicoDia] = field(default_factory=list)
    cortes_por_carga_kwh: dict[str, float] = field(default_factory=dict)


def demanda_com_corte(curva: Curva, plano: PlanoCorte, idx: int) -> float:
    """Total do intervalo menos o corte ativo.

    Interval total minus the active cut.
    """
    return curva.total_no_intervalo(idx) - sum(
        corte for corte in plano.corte_no(idx).values() if corte > 0
    )


def simular(
    curva: Curva,
    contrato: Contrato,
    cargas: list[Carga],
    com_corte: bool,
) -> ResultadoSimulacao:
    """Simula o mes com ou sem corte e devolve os totais.

    Simulate the month with or without cut and return the totals.
    """
    tempo_min = contrato.tempo_minimo_acionamento_minutos // 15
    plano: PlanoCorte | None = None
    if com_corte:
        plano = _plano(curva, cargas, contrato, tempo_min)

    demanda_max = 0.0
    indice_pico = 0
    energia = 0.0
    custo_energia = 0.0
    picos: list[tuple[float, int]] = []

    for dia in range(curva.n_dias):
        inicio = dia * N_INTERVALOS_POR_DIA
        pico_kw, pico_idx = curva.pico_dia(dia)
        picos.append((pico_kw, pico_idx))
        for idx in range(inicio, inicio + N_INTERVALOS_POR_DIA):
            total = curva.total_no_intervalo(idx)
            efetivo = (
                demanda_com_corte(curva, plano, idx) if plano is not None else total
            )
            if efetivo > demanda_max:
                demanda_max = efetivo
                indice_pico = idx
            minutos = curva.minutos_do_intervalo(idx)
            kwh = total * 0.25
            if plano is not None:
                kwh -= sum(plano.corte_no(idx).values()) * 0.25
            faixa = faixa_do_minuto(minutos, contrato)
            energia += kwh
            custo_energia += kwh * contrato.tarifa.tarifa_energia(faixa)

    custo_da_demanda, multa = custo_demanda(
        demanda_max, contrato.demanda_contratada_kw, contrato.tarifa
    )
    picos_diarios = [
        PicoDia(
            data=curva.data_do_intervalo(idx).isoformat(),
            indice=idx,
            demanda_kw=pico_kw,
            demanda_com_corte_kw=demanda_com_corte(curva, plano, idx)
            if plano is not None
            else pico_kw,
            corte_no_pico=plano.corte_no(idx) if plano is not None else {},
        )
        for pico_kw, idx in picos
    ]
    cortes_kwh = (
        {nome: plano.kWh_cortados(nome) for nome in curva.cargas}
        if plano is not None
        else {}
    )
    return ResultadoSimulacao(
        com_corte=com_corte,
        demanda_mensal_kw=demanda_max,
        indice_pico=indice_pico,
        energia_kwh=energia,
        custo_energia=custo_energia,
        custo_demanda=custo_da_demanda,
        multa=multa,
        custo_total=custo_energia + custo_da_demanda + multa,
        picos_diarios=picos_diarios,
        cortes_por_carga_kwh=cortes_kwh,
    )


def _plano(
    curva: Curva,
    cargas: list[Carga],
    contrato: Contrato,
    tempo_min: int,
) -> PlanoCorte:
    """Gera o plano de corte a partir do contrato.

    Build the cut plan from the contract.
    """
    return planejar_cortes(
        curva,
        cargas,
        contrato.demanda_contratada_kw,
        tempo_min,
    )


def faixa_do_minuto(minutos: int, contrato: Contrato) -> str:
    """Faixa tarifaria (PONTA / FORA_PONTA) de um minuto do dia.

    Tariff band (ON_PEAK / OFF_PEAK) of a minute of the day.
    """
    return faixa_do_intervalo(minutos, list(contrato.janelas_ponta))


@dataclass
class Comparacao:
    """Comparacao entre o mes com corte e o mes sem corte.

    Comparison between the month with cut and the month without cut.
    """

    economia: float
    percentual: float
    multa_evitada: float
    demanda_evitada: float


def comparar(
    sem_corte: ResultadoSimulacao,
    com_corte: ResultadoSimulacao,
) -> Comparacao:
    """Diferencas entre as duas simulacoes.

    Differences between the two simulations.
    """
    economia = sem_corte.custo_total - com_corte.custo_total
    percentual = (
        (economia / sem_corte.custo_total * 100.0) if sem_corte.custo_total > 0 else 0.0
    )
    return Comparacao(
        economia=economia,
        percentual=percentual,
        multa_evitada=sem_corte.multa - com_corte.multa,
        demanda_evitada=sem_corte.demanda_mensal_kw - com_corte.demanda_mensal_kw,
    )
