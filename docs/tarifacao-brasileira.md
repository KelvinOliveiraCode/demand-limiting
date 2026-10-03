# Tarifacao horaria: o modelo deste simulador

Documento de referencia do modelo tarifario usado por `demandlimit`. Todos os
valores sao ficticios; a estrutura segue o regime de baixa tensao com
tarifacao horaria e demanda contratada.

## O que e modelado

- Unidade ficticia `UTA-DEMO-0001`, baixa tensao, periodo de 30 dias
  (2026-01-01 a 2026-01-30), medicao em intervalos de 15 min
  (96 intervalos por dia, 2.880 no periodo).
- Fatura mensal composta por tres parcelas:
  1. **Energia**: soma dos kWh de cada intervalo vezes a tarifa da faixa
     (ponta ou fora de ponta) do intervalo.
  2. **Demanda**: `max(demanda do mes, demanda contratada)` vezes a tarifa
     de demanda (R$/kW).
  3. **Multa de excedente**: se a demanda do mes passou da contratada,
     30% do valor do excedente (excedente em kW vezes tarifa de demanda
     vezes 30%).

A regra da multa e a mesma de sempre em fatura de demanda: ela incide sobre
o excedente do pico, nao sobre a energia do mes. Ver
`docs/como-funciona-demanda-contratada.md`.

## Faixas PONTA e FORA_PONTA

| Faixa | Janela | Tarifa de energia |
|---|---|---:|
| PONTA | 08:00-12:00 e 14:00-20:00 | R$ 0,742/kWh |
| FORA_PONTA | demais horarios | R$ 0,568/kWh |

Valores plausiveis, nao tarifas reais:

| Parametro | Valor | Onde |
|---|---:|---|
| Demanda contratada | 260,00 kW | `dados/contrato.yaml` |
| Tarifa de demanda | R$ 31,40/kW (mensal) | `dados/contrato.yaml` |
| Multa de excedente | 30% | `dados/contrato.yaml` |
| Tempo minimo de acionamento do corte | 30 min | `dados/contrato.yaml` |

## Porque duas faixas e nao tres (decisao documentada)

O regime de "todas as horas" do Brasil tem tres faixas: PONTA, MEIO
(12:00-14:00) e FORA_PONTA. Este modelo usa duas: o almoco (12:00-14:00)
entra em FORA_PONTA.

Consequencia medida: cortar energia no almoco economiza R$ 0,568/kWh no
modelo, e nao a tarifa de meio (que seria entre as duas). O efeito e
pequeno para este exercicio, porque a demanda depende so de kW, nao de
faixa. Mas o erro ficaria escondido em qualquer simulacao de "quanto
economiza desligar tal carga no meio do dia". Se o modelo precisar de
fidelidade, o caminho e adicionar a faixa MEIO em `dados/contrato.yaml`
(como uma terceira janela) e `faixa_do_intervalo` em `src/demandlimit/tarifa.py`;
o resto do fluxo nao muda.

## Numeros reais deste repositorio

Da execucao de `exemplos/relatorio-corte.md`:

- Energia do mes sem corte: 51.128,90 kWh (media de ~71 kW).
- Pico do mes sem corte: 269,58 kW, dia 2026-01-21, as 11:30 (faixa PONTA).
- Fatura sem corte: R$ 34.988,35 (energia) + R$ 8.464,81 (demanda) +
  R$ 90,24 (multa) = R$ 43.543,41.
- Fatura com corte: R$ 43.142,82. Economia: R$ 400,59 (0,92%), sendo
  R$ 90,24 de multa evitada.

## O que o modelo nao cobre

- Sem tarifa por faixa de consumo (regressao por classe de consumo).
- Sem fator de potencia nem reativo.
- Sem faixa MEIO (acima).
- Sem transferencia de carga para fora de ponta (este e um limitador de
  demanda, nao um otimizador de horario de consumo).
