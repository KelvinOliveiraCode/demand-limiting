"""demandlimit - simulador de tarifacao horaria e corte de demanda.

Demandlimit - hourly tariff and demand-cut simulator.

Simula a tarifacao horaria de baixa tensao (ponta / fora de ponta) com
demanda contratada, planeja o corte de cargas por prioridade e compara
o mes com e sem corte. Funciona offline, so com a biblioteca padrao do
Python e PyYAML para leitura de arquivos.
Simulates low-voltage hourly tariffs (on/off-peak) with contracted
demand, plans load cuts by priority and compares the month with and
without cuts. Runs offline using only the Python standard library and
PyYAML for file parsing.
"""

from .corte import Carga, PlanoCorte, carregar_cargas, planejar_cortes
from .demanda import Contrato, Curva, carregar_contrato, carregar_curva
from .relatorio import gerar_relatorio
from .simulador import Comparacao, ResultadoSimulacao, comparar, simular
from .tarifa import FORA_PONTA, PONTA, Tarifa

__all__ = [
    "Carga",
    "PlanoCorte",
    "carregar_cargas",
    "planejar_cortes",
    "Contrato",
    "Curva",
    "carregar_contrato",
    "carregar_curva",
    "gerar_relatorio",
    "Comparacao",
    "ResultadoSimulacao",
    "comparar",
    "simular",
    "FORA_PONTA",
    "PONTA",
    "Tarifa",
]

__version__ = "1.0.0"
