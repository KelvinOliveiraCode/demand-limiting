"""Relatorio de corte de demanda em Markdown.

Markdown demand-cut report.
"""

from __future__ import annotations

from dataclasses import dataclass

from .corte import Carga, PlanoCorte
from .demanda import Contrato, Curva, N_INTERVALOS_POR_DIA
from .simulador import ResultadoSimulacao, comparar
from .tarifa import HORA_INTERVALO, custo_demanda

# Tolerancia ao comparar centavos no relatorio / cent tolerance
TOL_CENTAVO = 0.011


def _formata_moeda(valor: float) -> str:
    """Formata R$ com duas casas e separador de milhar.

    Format BRL with two decimals and thousands separator.
    """
    return f"{valor:,.2f}"


def _formata_kw(valor: float) -> str:
    """Formata kW com duas casas.

    Format kW with two decimals.
    """
    return f"{valor:.2f}"


def _hora_de_minutos(minutos: int) -> str:
    """Converte minutos do dia em 'HH:MM'.

    Convert minutes of the day into 'HH:MM'.
    """
    return f"{minutos // 60:02d}:{minutos % 60:02d}"


@dataclass
class DiaAnalise:
    """Analise de um dia de pico.

    Analysis of one peak day.
    """

    data: str
    hora_pico: str
    demanda_sem_corte: float
    demanda_com_corte: float
    corte_no_pico: dict[str, float]
    custo_sem_corte: float
    custo_com_corte: float
    economia: float
    multa_evitada: float


def custo_dia_isolado(
    curva: Curva,
    contrato: Contrato,
    plano: PlanoCorte | None,
    dia_index: int,
) -> dict[str, float]:
    """Custo de um dia tratado como mes isolado.

    Cost of one day treated as an isolated month.

    O custo de demanda e mensal; por dia ele e estimado aplicando a
    regra do contrato ao pico daquele dia. Esta aproximacao esta
    documentada no relatorio.
    The demand charge is monthly; per day it is estimated by applying
    the contract rule to that day's peak. The approximation is
    documented in the report.
    """
    inicio = dia_index * N_INTERVALOS_POR_DIA
    fim = inicio + N_INTERVALOS_POR_DIA
    demanda_sem = 0.0
    demanda_com = 0.0
    custo_energia_sem = 0.0
    custo_energia_com = 0.0
    kwh_sem = 0.0
    kwh_com = 0.0
    for idx in range(inicio, fim):
        total = curva.total_no_intervalo(idx)
        corte = sum(plano.corte_no(idx).values()) if plano is not None else 0.0
        efetivo = total - corte
        if total > demanda_sem:
            demanda_sem = total
        if efetivo > demanda_com:
            demanda_com = efetivo
        minutos = curva.minutos_do_intervalo(idx)
        faixa = faixa_do_minuto(curva, contrato, idx)
        tarifa = contrato.tarifa.tarifa_energia(faixa)
        kwh_sem += total * HORA_INTERVALO
        kwh_com += efetivo * HORA_INTERVALO
        custo_energia_sem += total * HORA_INTERVALO * tarifa
        custo_energia_com += efetivo * HORA_INTERVALO * tarifa
    custo_demanda_sem, multa_sem = custo_demanda(
        demanda_sem, contrato.demanda_contratada_kw, contrato.tarifa
    )
    custo_demanda_com, multa_com = custo_demanda(
        demanda_com, contrato.demanda_contratada_kw, contrato.tarifa
    )
    custo_sem = custo_energia_sem + custo_demanda_sem + multa_sem
    custo_com = custo_energia_com + custo_demanda_com + multa_com
    return {
        "demanda_sem": demanda_sem,
        "demanda_com": demanda_com,
        "custo_sem": custo_sem,
        "custo_com": custo_com,
        "multa_sem": multa_sem,
        "multa_com": multa_com,
        "kwh_sem": kwh_sem,
        "kwh_com": kwh_com,
    }


def faixa_do_minuto(curva: Curva, contrato: Contrato, idx: int) -> str:
    """Faixa tarifaria do intervalo.

    Tariff band of the interval.
    """
    from .tarifa import faixa_do_intervalo

    return faixa_do_intervalo(curva.minutos_do_intervalo(idx), list(contrato.janelas_ponta))


def analisar_dias(
    curva: Curva,
    contrato: Contrato,
    plano: PlanoCorte | None,
    top_dias: int,
) -> list[DiaAnalise]:
    """Analisa os dias de pico mais altos (maior pico sem corte).

    Analyze the highest peak days (by uncut peak).
    """
    dias = sorted(
        range(curva.n_dias),
        key=lambda i: curva.pico_dia(i)[0],
        reverse=True,
    )
    analises: list[DiaAnalise] = []
    for i in dias[:top_dias]:
        pico_kw, pico_idx = curva.pico_dia(i)
        cortes_pico = plano.corte_no(pico_idx) if plano is not None else {}
        custo = custo_dia_isolado(curva, contrato, plano, i)
        analises.append(
            DiaAnalise(
                data=curva.data_do_intervalo(pico_idx).isoformat(),
                hora_pico=_hora_de_minutos(curva.minutos_do_intervalo(pico_idx)),
                demanda_sem_corte=pico_kw,
                demanda_com_corte=custo["demanda_com"],
                corte_no_pico=cortes_pico,
                custo_sem_corte=custo["custo_sem"],
                custo_com_corte=custo["custo_com"],
                economia=custo["custo_sem"] - custo["custo_com"],
                multa_evitada=custo["multa_sem"] - custo["multa_com"],
            )
        )
    return analises


def gerar_relatorio(
    curva: Curva,
    contrato: Contrato,
    cargas: list[Carga],
    plano: PlanoCorte | None,
    sem: ResultadoSimulacao,
    com: ResultadoSimulacao,
    top_dias: int = 5,
) -> str:
    """Gera o relatorio completo em Markdown.

    Generate the full Markdown report.
    """
    comp = comparar(sem, com)
    dias_excedidos = sum(
        1
        for pico, _idx in (curva.pico_dia(i) for i in range(curva.n_dias))
        if pico > contrato.demanda_contratada_kw
    )
    top = analisar_dias(curva, contrato, plano, top_dias)

    linhas: list[str] = []
    add = linhas.append

    add("# Relatorio de corte de demanda")
    add("")
    add(f"- Unidade / unit: {contrato.unidade}")
    add(
        f"- Periodo: {curva.n_dias} dias ({curva.dias[0].isoformat()} a "
        f"{curva.dias[-1].isoformat()}), {curva.n_intervalos} intervalos de 15 min"
    )
    add(f"- Demanda contratada: {_formata_kw(contrato.demanda_contratada_kw)} kW")
    add(f"- Multa de excedente: {contrato.tarifa.multa_percentual:.1f}%")
    add(
        f"- Tempo minimo de acionamento: "
        f"{contrato.tempo_minimo_acionamento_minutos} min "
        f"({contrato.tempo_minimo_acionamento_minutos // 15} intervalos)"
    )
    add("")

    # Resumo mensal / monthly summary
    add("## Resumo mensal")
    add("")
    add("| Item | Sem corte | Com corte |")
    add("|---|---:|---:|")
    add(
        f"| Demanda do mes (kW) | {_formata_kw(sem.demanda_mensal_kw)} "
        f"| {_formata_kw(com.demanda_mensal_kw)} |"
    )
    add(
        f"| Energia (kWh) | {_formata_kw(sem.energia_kwh)} "
        f"| {_formata_kw(com.energia_kwh)} |"
    )
    add(
        f"| Custo de energia (R$) | {_formata_moeda(sem.custo_energia)} "
        f"| {_formata_moeda(com.custo_energia)} |"
    )
    add(
        f"| Custo de demanda (R$) | {_formata_moeda(sem.custo_demanda)} "
        f"| {_formata_moeda(com.custo_demanda)} |"
    )
    add(
        f"| Multa de excedente (R$) | {_formata_moeda(sem.multa)} "
        f"| {_formata_moeda(com.multa)} |"
    )
    add(
        f"| Custo total (R$) | {_formata_moeda(sem.custo_total)} "
        f"| {_formata_moeda(com.custo_total)} |"
    )
    add("")
    add(f"**Economia do mes: R$ {_formata_moeda(comp.economia)} ({comp.percentual:.2f}%)**")
    add(f"**Multa evitada: R$ {_formata_moeda(comp.multa_evitada)}**")
    add(f"**Demanda evitada no pico: {_formata_kw(comp.demanda_evitada)} kW**")
    add("")

    # Dias de pico / peak days
    add("## Dias de pico")
    add("")
    add(
        f"Sem corte, {dias_excedidos} de {curva.n_dias} dias ultrapassam a demanda "
        f"contratada no pico. Custos por dia: estimativa de mes isolado (o custo de "
        f"demanda e mensal; aqui ele e aplicado ao pico do dia)."
    )
    add("")
    for n, dia in enumerate(top, start=1):
        add(f"### Dia {n} - {dia.data} (pico sem corte: {_formata_kw(dia.demanda_sem_corte)} kW as {dia.hora_pico})")
        add("")
        add(f"- Demanda sem corte: {_formata_kw(dia.demanda_sem_corte)} kW")
        add(f"- Demanda com corte: {_formata_kw(dia.demanda_com_corte)} kW")
        add("- Corte aplicado por carga, no intervalo do pico:")
        add("")
        add("| Carga | Tipo | Prioridade | Corte (kW) |")
        add("|---|---|---:|---:|")
        for carga in sorted(cargas, key=lambda c: (c.prioridade, c.nome)):
            add(
                f"| {carga.nome} | {carga.tipo} | {carga.prioridade} "
                f"| {_formata_kw(dia.corte_no_pico.get(carga.nome, 0.0))} |"
            )
        add("")
        add(f"- Custo do dia sem corte: R$ {_formata_moeda(dia.custo_sem_corte)}")
        add(f"- Custo do dia com corte: R$ {_formata_moeda(dia.custo_com_corte)}")
        add(f"- Economia do dia: R$ {_formata_moeda(dia.economia)}")
        add(f"- Multa evitada no dia: R$ {_formata_moeda(dia.multa_evitada)}")
        add("")

    # Cortes no mes / monthly cuts
    add("## Cortes no mes")
    add("")
    if plano is None:
        add("Nenhum corte planejado.")
        add("")
    else:
        add("| Carga | Tipo | Acoes | kWh cortados |")
        add("|---|---|---:|---:|")
        for carga in sorted(cargas, key=lambda c: (c.prioridade, c.nome)):
            add(
                f"| {carga.nome} | {carga.tipo} "
                f"| {plano.acoes.get(carga.nome, 0)} "
                f"| {_formata_kw(plano.kWh_cortados(carga.nome))} |"
            )
        add("")
        add(
            f"kWh cortados no total: {_formata_kw(plano.total_kWh_cortados())}. "
            f"Cortar em pulsos curtos demais causa liga/desliga constante e desgaste "
            f"de equipamento; por isso o corte fica ativo por pelo menos o tempo minimo."
        )
        add("")

    # Conferencia aritmetica / arithmetic check (machine readable)
    add("## Conferencia aritmetica")
    add("")
    add(f"- demanda_mensal_sem_corte: {_formata_kw(sem.demanda_mensal_kw)} kW")
    add(f"- demanda_mensal_com_corte: {_formata_kw(com.demanda_mensal_kw)} kW")
    add(f"- energia_sem_corte: {_formata_kw(sem.energia_kwh)} kWh")
    add(f"- energia_com_corte: {_formata_kw(com.energia_kwh)} kWh")
    add(f"- custo_energia_sem_corte: R$ {_formata_moeda(sem.custo_energia)}")
    add(f"- custo_energia_com_corte: R$ {_formata_moeda(com.custo_energia)}")
    add(f"- custo_demanda_sem_corte: R$ {_formata_moeda(sem.custo_demanda)}")
    add(f"- custo_demanda_com_corte: R$ {_formata_moeda(com.custo_demanda)}")
    add(f"- multa_sem_corte: R$ {_formata_moeda(sem.multa)}")
    add(f"- multa_com_corte: R$ {_formata_moeda(com.multa)}")
    add(f"- custo_total_sem_corte: R$ {_formata_moeda(sem.custo_total)}")
    add(f"- custo_total_com_corte: R$ {_formata_moeda(com.custo_total)}")
    add(f"- economia: R$ {_formata_moeda(comp.economia)}")
    add(f"- percentual_economia: {comp.percentual:.2f}%")
    add(f"- multa_evitada: R$ {_formata_moeda(comp.multa_evitada)}")
    add(f"- demanda_evitada: {_formata_kw(comp.demanda_evitada)} kW")
    add("")
    return "\n".join(linhas)
