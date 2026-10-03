"""Gera dados/curva-de-carga.csv de forma deterministica (seed fixa).

Generates dados/curva-de-carga.csv deterministically (fixed seed).

So biblioteca padrao / standard library only.

Modelo da planta ficticia UTA-DEMO-0001:
- 8 cargas: 2 de iluminacao, 3 de climatizacao, 3 de producao.
- Perfis horarios por tipo (turnos, picos de calor, pausa de almoco).
- Fatores aleatorios por dia (uniforme, seed fixa) e ruido de +/- 2.5%
  por intervalo.
- Onda de calor plantada nos dias 20 a 22/01 (indice 19 a 21), com o
  pico no dia 21: a soma das cargas EXCEDE a demanda contratada (260 kW)
  nesse dia - o criterio de aceite da simulacao depende disso.
Fictitious plant UTA-DEMO-0001:
- 8 loads: 2 lighting, 3 air conditioning, 3 production.
- Hourly profiles per type (shifts, heat peaks, lunch break).
- Random per-day factors (uniform, fixed seed) and +/- 2.5% noise per
  interval.
- A heat wave planted on Jan 20-22 (index 19-21), peaking on Jan 21: the
  sum of the loads EXCEEDS the contracted demand (260 kW) that day - the
  simulation acceptance criterion depends on it.
"""

from __future__ import annotations

import csv
import math
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 20260119
DIA_INICIAL = date(2026, 1, 1)
N_DIAS = 30
N_INTERVALOS = 96
# Demanda contratada de referencia, apenas para a checagem final
# (o valor usado na simulacao fica em dados/contrato.yaml).
# Contracted demand for reference, only for the final check (the value
# used by the simulation lives in dados/contrato.yaml).
CONTRATADO_REF_KW = 260.0

# Potencias de referencia (kW) por carga.
# Reference powers (kW) per load.
BASE_KW = {
    "Iluminacao-Atendimento": 12.0,
    "Iluminacao-Operacional": 15.0,
    "Climatizacao-Comercial": 24.0,
    "Climatizacao-Servicos": 22.0,
    "Climatizacao-Deposito": 16.0,
    "Producao-Linha-A": 58.0,
    "Producao-Linha-B": 50.0,
    "Producao-Utilidades": 34.0,
}
# Ordem fixa das cargas na saida / fixed load order in the output
ORDEN_CARGAS = list(BASE_KW)


def _bump(horas_float: float, a: float, b: float, amp: float) -> float:
    """Bump sinusoidal entre as horas a e b, zero fora do intervalo.

    Sine bump between hours a and b, zero outside.
    """
    if a <= horas_float <= b:
        return amp * math.sin(math.pi * (horas_float - a) / (b - a))
    return 0.0


def perfil_iluminacao(i: int) -> float:
    """Iluminacao: alta do turno comercial, base noturna pequena.

    Lighting: high during the commercial shift, small night base.
    """
    hora = i // 4
    if 7 <= hora < 18:
        return 1.0
    return 0.12


def perfil_climatizacao(i: int) -> float:
    """Climatizacao: dois picos de calor, manha e tarde.

    Air conditioning: two heat peaks, morning and afternoon.
    """
    hora = i / 4.0
    manha = _bump(hora, 9.5, 13.5, 1.0)
    tarde = _bump(hora, 13.5, 18.5, 0.9)
    return min(1.0, manha + tarde + 0.08)


def perfil_producao_a(i: int) -> float:
    """Linha A: turno 07-18, pausa de almoco 12-13.

    Line A: 07-18 shift, 12-13 lunch pause.
    """
    hora = i // 4
    if 7 <= hora < 12:
        return 1.0
    if 12 <= hora < 13:
        return 0.35
    if 13 <= hora < 18:
        return 0.95
    return 0.05


def perfil_producao_b(i: int) -> float:
    """Linha B: turno 08-17, pausa de almoco 12-14.

    Line B: 08-17 shift, 12-14 lunch pause.
    """
    hora = i // 4
    if 8 <= hora < 12:
        return 0.9
    if 12 <= hora < 14:
        return 0.3
    if 14 <= hora < 17:
        return 0.95
    return 0.05


def perfil_utilidades(i: int) -> float:
    """Utilidades: quase constante, leve variao dia/noite.

    Utilities: nearly constant, mild day/night variation.
    """
    return 0.55 + 0.10 * math.sin(2.0 * math.pi * i / N_INTERVALOS + 0.6)


def fator_fim_de_semana(dia: date, indice: int) -> dict[str, float]:
    """Fatores por grupo de carga; fim de semana reduz a planta.

    Per-load-group factors; weekends shrink the plant.
    """
    fim_de_semana = dia.weekday() >= 5
    return {
        "iluminacao": 0.5 if fim_de_semana else 1.0,
        "climatizacao": 0.3 if fim_de_semana else 1.0,
        "producao": 0.0 if fim_de_semana else 1.0,
    }


def fatores_dia(r: random.Random, indice: int, dia: date) -> dict[str, float]:
    """Fatores aleatorios por dia, com a onda de calor plantada.

    Random per-day factors, with the planted heat wave.
    """
    f_iluminacao = r.uniform(0.97, 1.03)
    f_climatizacao = r.uniform(0.90, 1.10)
    f_producao = r.uniform(0.94, 1.06)
    # Onda de calor: dias 20, 21 e 22 de janeiro (indice 19 a 21).
    # Heat wave: Jan 20, 21 and 22 (index 19 to 21).
    if indice in (19, 21) and dia.weekday() < 5:
        f_climatizacao = 1.45
    elif indice == 20 and dia.weekday() < 5:
        f_climatizacao = 1.90
        f_producao = 1.10
    return {
        "iluminacao": f_iluminacao,
        "climatizacao": f_climatizacao,
        "producao": f_producao,
    }


def grupo_da_carga(nome: str) -> str:
    """Grupo tarifario da carga (iluminacao/climatizacao/producao).

    Load tariff group (lighting/air conditioning/production).
    """
    if nome.startswith("Iluminacao"):
        return "iluminacao"
    if nome.startswith("Climatizacao"):
        return "climatizacao"
    return "producao"


def perfil_da_carga(nome: str, i: int) -> float:
    """Perfil horario (0 a ~1) da carga no intervalo.

    Load hourly profile (0 to ~1) at the interval.
    """
    if nome == "Iluminacao-Atendimento":
        return 0.8 * perfil_iluminacao(i)
    if nome == "Iluminacao-Operacional":
        return perfil_iluminacao(i)
    if nome == "Climatizacao-Comercial":
        return 1.0 * perfil_climatizacao(i)
    if nome == "Climatizacao-Servicos":
        return 0.95 * perfil_climatizacao(i)
    if nome == "Climatizacao-Deposito":
        return 0.85 * perfil_climatizacao(i)
    if nome == "Producao-Linha-A":
        return perfil_producao_a(i)
    if nome == "Producao-Linha-B":
        return perfil_producao_b(i)
    if nome == "Producao-Utilidades":
        return perfil_utilidades(i)
    raise ValueError(f"Carga desconhecida / unknown load: {nome}")


def gerar() -> tuple[list[tuple[str, int, str, str, float]], list[float]]:
    """Gera os registros e devolve (linhas, picos diarios em kW).

    Generate the rows and return (rows, daily peaks in kW).
    """
    r = random.Random(SEED)
    linhas: list[tuple[str, int, str, str, float]] = []
    picos: list[float] = []
    for indice in range(N_DIAS):
        dia = DIA_INICIAL + timedelta(days=indice)
        data = dia.isoformat()
        grupos = fator_fim_de_semana(dia, indice)
        fatores = fatores_dia(r, indice, dia)
        totais: list[float] = []
        for i in range(N_INTERVALOS):
            hora = f"{i // 4:02d}:{(i % 4) * 15:02d}"
            total = 0.0
            for nome in ORDEN_CARGAS:
                perfil = perfil_da_carga(nome, i)
                grupo = grupo_da_carga(nome)
                ruido = 1.0 + r.uniform(-0.025, 0.025)
                kw = BASE_KW[nome] * perfil * grupos[grupo] * fatores[grupo] * ruido
                kw = round(max(0.0, kw), 3)
                linhas.append((data, i, hora, nome, kw))
                total += kw
            totais.append(total)
        picos.append(max(totais))
    return linhas, picos


def main() -> int:
    """Ponto de entrada do gerador.

    Generator entry point.
    """
    raiz = Path(__file__).resolve().parent.parent
    destino = raiz / "dados" / "curva-de-carga.csv"
    destino.parent.mkdir(parents=True, exist_ok=True)

    linhas, pico = gerar()
    with destino.open("w", encoding="utf-8", newline="") as arq:
        escritor = csv.writer(arq, lineterminator="\n")
        escritor.writerow(["data", "intervalo", "hora", "carga", "potencia_kw"])
        for data, i, hora, nome, kw in linhas:
            escritor.writerow([data, i, hora, nome, f"{kw:.3f}"])

    # Checagem da planta / plant check
    melhor = max(range(N_DIAS), key=lambda k: pico[k])
    print(f"CSV gravado: {destino.relative_to(raiz)}")
    print(f"Registros: {len(linhas)} (esperado {N_DIAS * N_INTERVALOS * 8})")
    print(
        f"Pico do mes ({(DIA_INICIAL + timedelta(days=melhor)).isoformat()}): "
        f"{pico[melhor]:.2f} kW"
    )
    excede = [k for k in range(N_DIAS) if pico[k] > CONTRATADO_REF_KW]
    print(f"Dias acima de {CONTRATADO_REF_KW:.0f} kW: {len(excede)}")
    for k in excede:
        print(f"  {(DIA_INICIAL + timedelta(days=k)).isoformat()}: {pico[k]:.2f} kW")
    if not excede:
        print("AVISO: nenhum dia estoura a demanda contratada de referencia.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
