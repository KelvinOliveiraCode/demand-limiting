"""Modelagem tarifaria horaria (ponta / fora de ponta).

Hourly tariff modeling (on-peak / off-peak).
"""

from __future__ import annotations

from dataclasses import dataclass

# Nomes das faixas / band names
PONTA = "PONTA"
FORA_PONTA = "FORA_PONTA"

# Horas de um intervalo de 15 minutos / hours in one 15-min interval
HORA_INTERVALO = 0.25


def parse_horario(texto: str) -> int:
    """Converte 'HH:MM' em minutos do dia.

    Convert 'HH:MM' into minutes of the day.
    """
    partes = texto.strip().split(":")
    if len(partes) != 2:
        raise ValueError(
            f"Horario invalido / invalid time format: {texto!r}. Use 'HH:MM'."
        )
    try:
        hora = int(partes[0])
        minuto = int(partes[1])
    except ValueError as exc:
        raise ValueError(
            f"Horario invalido / invalid time format: {texto!r}. Use 'HH:MM'."
        ) from exc
    if not 0 <= hora <= 23:
        raise ValueError(f"Hora fora do dia / hour out of range: {hora}")
    if not 0 <= minuto <= 59:
        raise ValueError(f"Minuto fora da hora / minute out of range: {minuto}")
    return hora * 60 + minuto


def janela_para_minutos(inicio: str, fim: str) -> tuple[int, int]:
    """Converte uma janela 'HH:MM'-'HH:MM' em (inicio, fim) em minutos.

    Convert a 'HH:MM'-'HH:MM' window into (start, end) in minutes.
    """
    a = parse_horario(inicio)
    b = parse_horario(fim)
    if b <= a:
        raise ValueError(
            f"Janela invalida / invalid window: inicio >= fim ({a} >= {b})."
        )
    return a, b


def faixa_do_intervalo(minutos: int, janelas_ponta: list[tuple[int, int]]) -> str:
    """Retorna PONTA se minutos cai em alguma janela de ponta; senao, FORA_PONTA.

    Return PONTA if minutes falls inside any on-peak window; else FORA_PONTA.
    """
    for inicio, fim in janelas_ponta:
        if inicio <= minutos < fim:
            return PONTA
    return FORA_PONTA


@dataclass(frozen=True)
class Tarifa:
    """Tarifas ficticias de baixa tensao.

    Fictitious low-voltage tariff parameters.
    """

    energia_ponta: float
    energia_fora_ponta: float
    demanda_rpor_kw: float
    multa_percentual: float

    def tarifa_energia(self, faixa: str) -> float:
        """Tarifa de energia (R$/kWh) da faixa dada.

        Energy rate (BRL/kWh) of the given band.
        """
        return self.energia_ponta if faixa == PONTA else self.energia_fora_ponta


def custo_energia(kwh: float, faixa: str, tarifa: Tarifa) -> float:
    """Custo de energia de um trecho, em R$.

    Energy cost of a slice, in BRL.
    """
    if kwh < 0:
        raise ValueError(f"Energia negativa / negative energy: {kwh}")
    return kwh * tarifa.tarifa_energia(faixa)


def custo_demanda(demanda_mensal: float, contratada: float, tarifa: Tarifa) -> tuple[float, float]:
    """Custo de demanda e multa de um mes.

    Monthly demand charge and fine.

    Regra: a demanda faturada e o maior entre a demanda medida e a
    contratada. Se a medida estoura a contratada, a multa e
    `multa_percentual` por cento do valor do excedente.
    Rule: the billed demand is the larger of measured and contracted
    demand. If the measured value exceeds the contracted one, the fine
    is `multa_percentual` percent of the excess value.
    """
    if demanda_mensal < 0:
        raise ValueError(f"Demanda negativa / negative demand: {demanda_mensal}")
    if contratada <= 0:
        raise ValueError(f"Demanda contratada deve ser positiva / must be positive: {contratada}")
    demanda_faturada = max(demanda_mensal, contratada)
    custo = demanda_faturada * tarifa.demanda_rpor_kw
    excedente = max(0.0, demanda_mensal - contratada)
    multa = excedente * tarifa.demanda_rpor_kw * (tarifa.multa_percentual / 100.0)
    return custo, multa
