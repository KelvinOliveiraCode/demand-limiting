# Como funciona a demanda contratada

Este documento explica o conceito de demanda (kW medio nos 15 min mais
alto), por que demanda nao e consumo (kWh) e por que a multa incide sobre
o pico, nao sobre o total do mes. Todos os numeros sao da simulacao
deste repositorio (`exemplos/relatorio-corte.md`).

## Demanda nao e consumo

Consumo e energia: a integral da potencia ao longo do tempo, medida em
kWh. Demanda e potencia: a media de kW de um intervalo de 15 minutos,
repetida 96 vezes por dia.

No dado deste repositorio:

| Grandeza | Valor do mes | Unidade |
|---|---:|---|
| Energia (consumo) | 51.128,90 | kWh |
| Demanda do mes | 269,58 | kW |

Os dois numeros medem coisas diferentes. Dois consumidores com o mesmo
kWh no mes podem ter demandas muito distintas se um concentra a carga em
poucas horas e o outro a espalha. A fatura cobra os dois: energia em
R$/kWh e demanda em R$/kW. Errar a distincao é o erro que gera fatura
surpresa: quem olha so o kWh ve um mes "normal" e nao ve o pico que
estourou o contrato.

## Como o medidor define a demanda do mes

O medidor calcula a media de kW de cada intervalo de 15 minutos. A
demanda do mes e o MAIOR desses 2.880 valores (30 dias x 96 intervalos),
nao a media deles. No dado deste repositorio, o maior intervalo foi
269,58 kW, dia 2026-01-21, as 11:30.

## Por que a multa e sobre o pico, nao sobre o total

O contrato desta unidade e de 260,00 kW. A fatura de demanda usa:

1. `demanda faturada = max(demanda do mes, contratada)`;
2. `multa = 30% do excedente` (quando ha excedente).

No caso deste mes:

- Excedente: 269,58 - 260,00 = 9,58 kW.
- Custo de demanda sem corte: 269,58 x R$ 31,40 = R$ 8.464,81.
- Multa: 9,58 x R$ 31,40 x 0,30 = R$ 90,24.
- Custo de demanda com corte: 260,00 x R$ 31,40 = R$ 8.164,00 (multa zero).

A multa nasce de UM intervalo de 15 minutos (as 11:30 de 21/01), nao do
total de 51.128,90 kWh do mes. E por isso que "cortar demanda" tem
efeito desproporcional: cada kW que sai do pico elimina R$ 31,40 de
demanda mais 30% do excedente, todo mes, enquanto 1 kWh a menos de
energia custa so R$ 0,57-0,74.

## O algoritmo de corte e o tempo minimo de acionamento

A cada intervalo, o `src/demandlimit/corte.py` compara a soma das cargas
com os 260,00 kW. Se ha excedente, corta em ordem de prioridade:

1. Iluminacao (prioridade 1): nunca cortada.
2. Climatizacao (prioridade 2): ate 25% da potencia do intervalo.
3. Producao (prioridade 3): por ultimo, ate 100%.

Uma carga cortada fica cortada por pelo menos o tempo minimo de
acionamento (30 min = 2 intervalos) antes de poder ligar de novo. Sem
essa trava, um excedente de um intervalo gera corte de um intervalo e
ligada na hora seguinte: liga/desliga a cada 15 minutos e desgaste de
equipamento (inversor, compressor, partida de motor).

Trade-off medido no dado deste repositorio, para a mesma curva:

| Tempo minimo | Acoes no mes | kWh cortados |
|---|---:|---:|
| 15 min (sem trava) | 7 | 10,41 |
| 30 min (contrato) | 3 | 12,85 |
| 60 min | 2 | 19,62 |

A trava corta o numero de acoes pela metade (7 para 3) mas aumenta a
energia cortada (10,41 para 12,85 kWh): enquanto a trava esta vigente, o
corte continua mesmo depois que o excedente sumiu. Escolher 30 min foi a
decisao do contrato: menos ciclos de ligada/desligada, com custo
energético limitado (2,44 kWh a mais no mes).

No dia plantado (21/01), a climatizacao sozinha cobriu os 9,58 kW de
excedente; producao ficou com corte de 0,00 kW. O teste
`tests/test_corte.py::test_corte_estoura_clima_e_cai_na_producao` prova o
caso em que a capacidade da climatizacao nao chega e a producao entra.

## O que o teste de aceite confere

`tests/test_aceite.py` verifica, com o dado do repositorio:

1. Sem corte, a demanda mensal (269,58 kW) estoura a contratada (260,00 kW) e a multa sai positiva.
2. Com corte, a demanda mensal fica em 260,00 kW ou menos e a multa zera.
3. A economia do relatorio confere: `economia == custo_total_sem_corte - custo_total_com_corte` (R$ 400,59).
