<div align="center">

<p>
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/tests-50%20passing-brightgreen?style=flat-square" alt="Tests">
  <img src="https://img.shields.io/badge/coverage-98%25-brightgreen-brightgreen?style=flat-square" alt="Coverage">
  <img src="https://img.shields.io/badge/license-MIT-yellow?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/platform-Windows-blue?style=flat-square" alt="Windows">
  <img src="https://img.shields.io/badge/deps-PyYAML%20only-blue?style=flat-square" alt="Deps">
</p>

# demand-limiting

**Simulacao de tarifacao horaria com corte de demanda dentro da demanda contratada.**

</div>

---

## PT-BR

### O que e

CLI que simula a fatura de um mes de baixa tensao com tarifacao horaria
(ponta / fora de ponta) e demanda contratada, planeja o corte das cargas em
ordem de prioridade (iluminacao nao corta, climatizacao corta parcialmente,
producao corta por ultimo) e compara o mes com e sem corte: demanda de pico,
energia, custo, multa de excedente. Nenhum numero sai de memoria: o relatorio
deixa a conta aberta para conferencia.

### Por que foi feito

Multa por excedente de demanda e a dor mais comum de industria e comercio em
conta de luz. A demanda e a media de kW dos 15 minutos mais alto do mes, e nao
o consumo em kWh: da para ter um mes de consumo "normal" e estourar o
contrato em um intervalo de 15 minutos. O calculo e o trabalho: quanto a
fatura custa com o pico, quanto custa com corte, e quais cargas entram no
corte primeiro.

### Como rodar

```powershell
# 1. Instalar
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. Validar
python -m pytest tests/ -v

# 3. Executar (o pacote mora em src/, entao aponte PYTHONPATH)
$env:PYTHONPATH = "src"
python -m demandlimit simular --curva dados\curva-de-carga.csv --contrato dados\contrato.yaml --saida exemplos\relatorio-corte.md
```

Saida real:

```
Simulacao concluida / simulation complete
- Demanda do mes (sem corte): 269.58 kW
- Demanda do mes (com corte): 260.00 kW
- Custo total sem corte: R$ 43,543.41
- Custo total com corte: R$ 43,142.82
- Economia: R$ 400.59 (0.92%)
- Multa evitada: R$ 90.24
AVISO: sem corte, a demanda estoura o contrato; a multa de excedente e evitada com o corte. WARNING: without the cut the demand exceeds the contract; the excess fine is avoided with the cut.
Relatorio gravado em: exemplos\relatorio-corte.md
```

O dado de entrada do exemplo tem um pico plantado (2026-01-21, 269.58 kW,
11:30), 9.58 kW acima dos 260 kW contratados; com corte, o pico fecha em
260.00 kW e a multa zera.

Outros comandos:

```powershell
python -m demandlimit --help
python -m demandlimit cargas                 # lista as 8 cargas e prioridades
python -m demandlimit simular --curva dados\curva-de-carga.csv --contrato dados\contrato.yaml --top 3   # so terminal, sem gravar
python tools\gerar_dados.py                  # regenera dados\curva-de-carga.csv (seed fixa)
```

O relatorio gerado inclui a conferencia aritmetica:

```
- custo_total_sem_corte: R$ 43,543.41
- custo_total_com_corte: R$ 43,142.82
- economia: R$ 400.59
- multa_evitada: R$ 90.24
```

### O que aprendi

- **Demanda nao e consumo.** O mes simulado consumiu 51.128,90 kWh, mas a
  multa nasceu de um unico intervalo de 15 min (269.58 kW). Quem so olha o
  kWh nao ve o pico que estourou os 260 kW do contrato. A conta esta em
  `docs/como-funciona-demanda-contratada.md`, com os numeros deste repositorio.
- **Tempo minimo de acionamento e um trade-off medido, nao intuitivo.** Sem a
  trava de 30 min, o corte no dia de calor deu 7 acoes e cortou 10.41 kWh;
  com a trava, 3 acoes e 12.85 kWh. A trava corta o numero de
  liga/desliga pela metade a custo de 2.44 kWh extras no mes - por isso o
  valor e parametro do contrato, nao do codigo.
- **Prioridade deixou a producao de braco cruzado.** No pico plantado, a
  climatizacao (teto de 25% da potencia do intervalo) cobriu os 9.58 kW de
  excedente sozinha; producao ficou com corte de 0.00 kW. O teste
  `test_corte_estoura_clima_e_cai_na_producao` cobre o caso em que a
  climatizacao satura e a producao entra - por ultimo, como manda a regra.
- **Duas faixas em vez de tres foi uma decisao documentada.** O regime de
  "todas as horas" tem PONTA, MEIO (12:00-14:00) e FORA_PONTA; o modelo usa
  duas, e o almoco entra em FORA_PONTA. Consequencia: cortar energia ao meio
  dia fica barateado no calculo. A correcao e uma janela extra em
  `dados/contrato.yaml` + `tarifa.py`. Ver `docs/tarifacao-brasileira.md`.
- **Gerador deterministico e o que torna "dado real" conferivel.** Os
  23.040 registros (30 dias x 96 intervalos x 8 cargas) sao gerados por
  `tools/gerar_dados.py` com seed fixa; o pico que estoura a contratada esta
  plantado (2026-01-21, 269.58 kW). Rerodar a ferramenta reproduz o CSV
  identico - o que o teste `test_carregar_curva_real_23040_registros` usa.

### Limitacoes

- **Nao tem faixa MEIO (12:00-14:00).** Duas faixas em vez de tres; ver
  `docs/tarifacao-brasileira.md`.
- **Nao modela fator de potencia, reativo ou regressao por classe de
  consumo.** A fatura tem so energia, demanda e multa de excedente.
- **Nao tem cadeia de medicao real** (medidor, transformador de corrente):
  o CSV e tratado como a leitura do medidor.
- **So limita demanda; nao transfere carga.** Nao existe dessacador de pico
  para fora de ponta nem horizonte rolante de previsao.
- **Custo por dia de pico e estimativa.** O custo de demanda e mensal; no
  detalhamento por dia ele e aplicado ao pico daquele dia, como o proprio
  relatorio declara.

### Licenca

MIT. Ver [LICENSE](LICENSE).

---

## EN

### What it is

A CLI that simulates one month of low-voltage hourly-tariff billing
(on-peak / off-peak) with contracted demand, plans load curtailment in
priority order (lighting never, air conditioning partially, production
last) and compares the month with and without the cut: peak demand,
energy, cost, excess fine. No number comes from memory: the report leaves
the arithmetic open for manual checking.

### Why it was built

The fine for demand excess is the most common pain point in industry and
commerce electricity bills. Demand is the average kW of the highest
15-minute interval of the month, not the kWh consumption: you can have a
"normal" consumption month and still bust the contract in one 15-minute
interval. The calculation is the work: what the bill costs with the peak,
what it costs with the cut, and which loads get cut first.

### How to run

```powershell
# 1. Install
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. Validate
python -m pytest tests/ -v

# 3. Run (the package lives in src/, so point PYTHONPATH at it)
$env:PYTHONPATH = "src"
python -m demandlimit simular --curva dados\curva-de-carga.csv --contrato dados\contrato.yaml --saida exemplos\relatorio-corte.md
```

Real output:

```
Simulacao concluida / simulation complete
- Demanda do mes (sem corte): 269.58 kW
- Demanda do mes (com corte): 260.00 kW
- Custo total sem corte: R$ 43,543.41
- Custo total com corte: R$ 43,142.82
- Economia: R$ 400.59 (0.92%)
- Multa evitada: R$ 90.24
AVISO: sem corte, a demanda estoura o contrato; a multa de excedente e evitada com o corte. WARNING: without the cut the demand exceeds the contract; the excess fine is avoided with the cut.
Relatorio gravado em: exemplos\relatorio-corte.md
```

The example input has a planted peak (2026-01-21, 269.58 kW, 11:30),
9.58 kW above the 260 kW contracted; with the cut, the peak lands at
260.00 kW and the fine goes to zero.

Other commands:

```powershell
python -m demandlimit --help
python -m demandlimit cargas                 # list the 8 loads and priorities
python -m demandlimit simular --curva dados\curva-de-carga.csv --contrato dados\contrato.yaml --top 3   # terminal only, no file
python tools\gerar_dados.py                  # regenerate dados\curva-de-carga.csv (fixed seed)
```

The generated report includes the arithmetic check:

```
- custo_total_sem_corte: R$ 43,543.41
- custo_total_com_corte: R$ 43,142.82
- economia: R$ 400.59
- multa_evitada: R$ 90.24
```

### What I learned

- **Demand is not consumption.** The simulated month consumed 51,128.90
  kWh, but the fine came from a single 15-minute interval (269.58 kW).
  Watching only kWh hides the peak that busted the 260 kW contract. The
  hand math is in `docs/como-funciona-demanda-contratada.md`, with this
  repository's numbers.
- **The minimum actuation time is a measured trade-off, not intuition.**
  Without the 30-min lock, the hot-day cut fired 7 times and cut 10.41
  kWh; with the lock, 3 times and 12.85 kWh. The lock halves the
  on/off cycles at a cost of 2.44 kWh extra for the month - which is why
  it is a contract parameter, not a constant in the code.
- **Priority kept production out of the planted case.** At the planted
  peak, the air conditioning (25% ceiling of the interval power) covered
  the whole 9.58 kW excess; production sat at a 0.00 kW cut. The test
  `test_corte_estoura_clima_e_cai_na_producao` covers the case where the
  AC saturates and production comes in - last, as the rule says.
- **Two bands instead of three was a documented decision.** The Brazilian
  "todas as horas" regime has PONTA, MEIO (12:00-14:00) and FORA_PONTA;
  the model uses two, and lunch lands in FORA_PONTA. Consequence: cutting
  energy at noon is undervalued in the math. The fix is one extra window
  in `dados/contrato.yaml` + `tarifa.py`. See `docs/tarifacao-brasileira.md`.
- **A deterministic generator is what makes "real data" checkable.** The
  23,040 records (30 days x 96 intervals x 8 loads) come from
  `tools/gerar_dados.py` with a fixed seed; the peak that busts the
  contract is planted (2026-01-21, 269.58 kW). Rerunning the tool
  reproduces the identical CSV - which the test
  `test_carregar_curva_real_23040_registros` relies on.

### Limitations

- **No MEIO band (12:00-14:00).** Two bands instead of three; see
  `docs/tarifacao-brasileira.md`.
- **No power factor, reactive or consumption-class regression.** The bill
  has only energy, demand and the excess fine.
- **No real metering chain** (meter, current transformer): the CSV is
  treated as the meter reading.
- **Demand limiting only; no load shifting.** There is no off-peak peak
  shifter nor a rolling forecast horizon.
- **Per-peak-day cost is an estimate.** The demand charge is monthly; the
  per-day detail applies it to that day's peak, as the report states.

### License

MIT. See [LICENSE](LICENSE).

---

## Estrutura / Structure

```
src/demandlimit/
  tarifa.py         faixas ponta/fora de ponta, tarifas e multa
  demanda.py        curva de carga (CSV) e contrato (YAML)
  corte.py          algoritmo de corte: prioridade + tempo minimo
  simulador.py      mes com e sem corte; comparacao
  relatorio.py      relatorio Markdown com conferencia aritmetica
  cli.py            interface de linha de comando
dados/             curva-de-carga.csv, contrato.yaml, cargas.yaml
docs/               tarifacao-brasileira, como-funciona-demanda-contratada
exemplos/           relatorio-corte.md e saida de terminal reais
tests/              50 testes
tools/              gerar_dados.py (gerador deterministico)
```

## Licenca / License

MIT &mdash; [LICENSE](LICENSE)

---

<div align="center">
  <sub>Por <a href="https://github.com/KelvinOliveiraCode">Kelvin Oliveira</a> &middot;
  <a href="https://kelvinoliveiracode.github.io/portfolio/">portfolio</a></sub>
</div>
