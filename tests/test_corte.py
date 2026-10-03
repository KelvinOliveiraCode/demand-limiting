"""Testes do algoritmo de corte de demanda.

Tests for the demand-cut algorithm.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from demandlimit.corte import Carga, carregar_cargas, planejar_cortes
from demandlimit.demanda import N_INTERVALOS_POR_DIA, Curva, carregar_curva

RAIZ = Path(__file__).resolve().parents[1]

# Cargas sinteticas / synthetic loads
ILU = Carga("Ilu-1", "iluminacao", 1, 0)
CLIMA = Carga("Clima-1", "climatizacao", 2, 50)
PROD = Carga("Prod-1", "producao", 3, 100)
CARGAS = [ILU, CLIMA, PROD]


def _curva(por_carga: dict[str, list[float]]) -> Curva:
    """Curva de 1 dia com as series dadas.

    One-day curve with the given series.
    """
    potencias = {nome: [float(v) for v in serie] for nome, serie in por_carga.items()}
    return Curva(dias=[date(2026, 1, 1)], cargas=list(por_carga), potencia=potencias)


def _constante(valor: float) -> list[float]:
    """Serie constante de 96 intervalos.

    Constant series of 96 intervals.
    """
    return [valor] * N_INTERVALOS_POR_DIA


def _planejamento(contratada: float, min_on: int = 2) -> "PlanoCorte":
    """Plano de corte da planta sintetica constante.

    Cut plan for the constant synthetic plant.
    """
    curva = _curva({"Ilu-1": _constante(100.0), "Clima-1": _constante(80.0), "Prod-1": _constante(60.0)})
    return planejar_cortes(curva, CARGAS, contratada, min_on)


def test_corte_mantem_iluminacao_em_zero():
    """Iluminacao (prioridade 1) nunca e cortada.

    Lighting (priority 1) is never cut.
    """
    plano = _planejamento(contratada=200.0)
    assert plano.cortes["Ilu-1"] == [0.0] * N_INTERVALOS_POR_DIA


def test_corte_prioriza_climatizacao_antes_da_producao():
    """Excedente dentro da capacidade do clima: producao nao e tocada.

    Excess within the AC capacity: production is not touched.
    """
    plano = _planejamento(contratada=200.0)  # excedente = 40 kW
    assert plano.cortes["Clima-1"][0] == pytest.approx(40.0)
    assert plano.cortes["Prod-1"] == [0.0] * N_INTERVALOS_POR_DIA


def test_corte_estoura_clima_e_cai_na_producao():
    """Excedente maior que a capacidade do clima: producao cobre o resto.

    Excess above the AC capacity: production covers the rest.
    """
    plano = _planejamento(contratada=180.0)  # excedente = 60 kW
    assert plano.cortes["Clima-1"][0] == pytest.approx(40.0)
    assert plano.cortes["Prod-1"][0] == pytest.approx(20.0)


def test_corte_nao_excede_capacidade_por_carga():
    """Corte fica no teto: 50% do clima, nunca a mais.

    The cut stays at the ceiling: 50% of the AC, never more.
    """
    plano = _planejamento(contratada=100.0)  # excedente = 140 kW
    for i in range(N_INTERVALOS_POR_DIA):
        assert plano.cortes["Clima-1"][i] <= 40.0 + 1e-9
        assert plano.cortes["Prod-1"][i] <= 60.0 + 1e-9
        assert plano.cortes["Ilu-1"][i] == 0.0


def test_sem_excedente_nao_ha_corte():
    """Sem excedente, nenhuma acao.

    No excess, no action.
    """
    plano = _planejamento(contratada=300.0)
    for nome in ("Ilu-1", "Clima-1", "Prod-1"):
        assert sum(plano.cortes[nome]) == 0.0
    assert sum(plano.acoes.values()) == 0


def test_tempo_minimo_segura_corte_por_dois_intervalos():
    """Com min_on=2, o corte ativo em t segue em t+1 mesmo sem excedente.

    With min_on=2, a cut active at t stays at t+1 even with no excess.
    """
    serie = [200.0, 200.0, 100.0] + [100.0] * (N_INTERVALOS_POR_DIA - 3)
    curva = _curva({"Clima-1": serie})
    plano = planejar_cortes(curva, [CLIMA], 150.0, 2)
    assert plano.cortes["Clima-1"][0] == pytest.approx(50.0)
    assert plano.cortes["Clima-1"][1] == pytest.approx(50.0)  # segurado
    assert plano.cortes["Clima-1"][2] == 0.0  # liberado


def test_sem_tempo_minimo_libera_imediatamente():
    """Com min_on=1, o corte sai no intervalo seguinte.

    With min_on=1, the cut ends at the next interval.
    """
    serie = [200.0, 100.0] + [100.0] * (N_INTERVALOS_POR_DIA - 2)
    curva = _curva({"Clima-1": serie})
    plano = planejar_cortes(curva, [CLIMA], 150.0, 1)
    assert plano.cortes["Clima-1"][0] == pytest.approx(50.0)
    assert plano.cortes["Clima-1"][1] == 0.0


def test_reacionamento_corta_de_novo_apos_liberacao():
    """Excedente em t e t+3 gera duas acoes (liga/desliga/liga).

    Excess at t and t+3 yields two actuations (on/off/on).
    """
    serie = [200.0, 200.0, 100.0, 200.0] + [100.0] * (N_INTERVALOS_POR_DIA - 4)
    curva = _curva({"Clima-1": serie})
    plano = planejar_cortes(curva, [CLIMA], 150.0, 2)
    assert plano.acoes["Clima-1"] == 2
    assert plano.cortes["Clima-1"][3] == pytest.approx(50.0)


def test_tempo_minimo_invalido_levanta_erro():
    """Tempo minimo nulo e erro.

    A zero minimum time is an error.
    """
    curva = _curva({"Clima-1": _constante(80.0)})
    with pytest.raises(ValueError, match="positivo|positive"):
        planejar_cortes(curva, [CLIMA], 100.0, 0)


def test_carregar_cargas_rejeita_yml_invalido(tmp_path: Path):
    """YAML sem a lista de cargas e erro.

    A YAML without the loads list is an error.
    """
    caminho = tmp_path / "cargas.yaml"
    caminho.write_text("algo: 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid loads|cargas"):
        carregar_cargas(caminho)


def test_carregar_cargas_rejeita_duplicada_e_percentual_fora():
    """Nome duplicado ou recorte fora de 0-100 e erro.

    Duplicate name or cut share out of 0-100 is an error.
    """
    import tempfile

    import yaml

    texto_valido = """
cargas:
  - nome: "A"
    tipo: "climatizacao"
    prioridade: 2
    recorte_maximo_percent: 50
"""
    doc = yaml.safe_load(texto_valido)
    doc["cargas"].append(dict(doc["cargas"][0]))
    with tempfile.NamedTemporaryFile(
        "w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as arq:
        yaml.safe_dump(doc, arq)
        duplicado = arq.name
    with pytest.raises(ValueError, match="duplicada|duplicate"):
        carregar_cargas(duplicado)

    doc["cargas"] = [dict(doc["cargas"][0])]
    doc["cargas"][0]["recorte_maximo_percent"] = 150
    with tempfile.NamedTemporaryFile(
        "w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as arq:
        yaml.safe_dump(doc, arq)
        caminho_fora = arq.name
    with pytest.raises(ValueError, match="out of range|fora de 0-100"):
        carregar_cargas(caminho_fora)


def test_dado_real_dentro_do_contrato_ao_cortar():
    """No dado real, o pico com corte fica dentro da contratada.

    On the real data, the peak with cut stays within the contract.
    """
    cargas = carregar_cargas(RAIZ / "dados" / "cargas.yaml")
    curva = carregar_curva(RAIZ / "dados" / "curva-de-carga.csv", cargas)
    plano = planejar_cortes(curva, cargas, 260.0, 2)
    for idx in range(curva.n_intervalos):
        total_corte = sum(plano.corte_no(idx).values())
        assert curva.total_no_intervalo(idx) - total_corte <= 260.0 + 1e-6
