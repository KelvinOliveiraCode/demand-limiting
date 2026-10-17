<div align="center">

<p>
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/tests-50%20passing-brightgreen?style=flat-square" alt="Tests">
  <img src="https://img.shields.io/badge/coverage-98%25-brightgreen?style=flat-square" alt="Coverage">
  <img src="https://img.shields.io/badge/license-MIT-yellow?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/platform-Windows-blue?style=flat-square" alt="Windows">
  <img src="https://img.shields.io/badge/deps-PyYAML%20only-blue?style=flat-square" alt="Deps">
</p>

# demand-limiting

**Hourly-tariff billing simulation with demand curtailment within contracted demand.**

</div>

---

## What it is

CLI that simulates one month of low-voltage hourly-tariff billing
(on-peak / off-peak) with contracted demand, plans load curtailment in
priority order (lighting never cut, air conditioning cut partially,
production cut last) and compares the month with and without the cut:
peak demand, energy, cost, excess fine. No number comes from memory: the
report leaves the arithmetic open for checking.

## Why it was built

The fine for demand excess is the most common pain point in industry and
commerce electricity bills. Demand is the average kW of the highest
15-minute interval of the month, not kWh consumption: you can have a
"normal" consumption month and still bust the contract in one 15-minute
interval. The calculation is the work: what the bill costs with the
peak, what it costs with the cut, and which loads get cut first.

## How to run

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
Simulation complete
- Monthly demand (without cut): 269.58 kW
- Monthly demand (with cut): 260.00 kW
- Total cost without cut: R$ 43,543.41
- Total cost with cut: R$ 43,142.82
- Savings: R$ 400.59 (0.92%)
- Excess fine avoided: R$ 90.24
Without the cut, demand exceeds the contract; the excess fine is avoided with the cut.
Report saved to exemplos\relatorio-corte.md
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

## What I learned

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

## Limitations

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

## License

MIT. See [LICENSE](LICENSE).

---

## Structure

```
src/demandlimit/
  tarifa.py         on-peak / off-peak bands, tariffs and fine
  demanda.py        load curve (CSV) and contract (YAML)
  corte.py          curtailment algorithm: priority + minimum time
  simulador.py      month with and without cut; comparison
  relatorio.py      Markdown report with arithmetic check
  cli.py            command-line interface
dados/             curva-de-carga.csv, contrato.yaml, cargas.yaml
docs/               tarifacao-brasileira, como-funciona-demanda-contratada
exemplos/           relatorio-corte.md and real terminal output
tests/              50 tests
tools/              gerar_dados.py (deterministic generator)
```

## License

MIT — [LICENSE](LICENSE)

---

<div align="center">
  <sub>By <a href="https://github.com/KelvinOliveiraCode">Kelvin Oliveira</a> &
  <a href="https://kelvinoliveiracode.github.io/portfolio/">portfolio</a></sub>
</div>
