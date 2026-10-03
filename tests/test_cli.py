"""Testes da CLI.

Tests for the CLI.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from demandlimit.cli import main

RAIZ = Path(__file__).resolve().parents[1]
CURVA_REAL = str(RAIZ / "dados" / "curva-de-carga.csv")
CONTRATO_REAL = str(RAIZ / "dados" / "contrato.yaml")
CARGAS_REAL = str(RAIZ / "dados" / "cargas.yaml")


def test_cli_help_mostra_uso():
    """--help sai com codigo 0 e mostra os comandos.

    --help exits with code 0 and shows the commands.
    """
    assert main(["--help"]) == 0


def test_cli_versao():
    """--versao sai com codigo 0.

    --versao exits with code 0.
    """
    assert main(["--versao"]) == 0


def test_cli_cargas_lista_cargas(capsys: pytest.CaptureFixture[str]):
    """O comando cargas lista as 8 cargas.

    The cargas command lists the 8 loads.
    """
    assert main(["cargas", "--arquivo", CARGAS_REAL]) == 0
    saida = capsys.readouterr().out
    for nome in (
        "Iluminacao-Atendimento",
        "Climatizacao-Comercial",
        "Producao-Linha-A",
    ):
        assert nome in saida


def test_cli_simular_escreve_relatorio(tmp_path: Path):
    """O comando simular grava o relatorio e sai com 0.

    The simular command writes the report and exits with 0.
    """
    destino = tmp_path / "relatorio.md"
    codigo = main(
        [
            "simular",
            "--curva", CURVA_REAL,
            "--contrato", CONTRATO_REAL,
            "--cargas", CARGAS_REAL,
            "--saida", str(destino),
        ]
    )
    assert codigo == 0
    texto = destino.read_text(encoding="utf-8")
    assert "## Conferencia aritmetica" in texto
    assert "## Dias de pico" in texto


def test_cli_simular_sem_saida_imprime_no_terminal(capsys: pytest.CaptureFixture[str]):
    """Sem --saida, o relatorio vai para o terminal.

    Without --saida, the report goes to the terminal.
    """
    codigo = main(
        [
            "simular",
            "--curva", CURVA_REAL,
            "--contrato", CONTRATO_REAL,
            "--cargas", CARGAS_REAL,
        ]
    )
    assert codigo == 0
    saida = capsys.readouterr().out
    assert "## Resumo mensal" in saida
    assert "Relatorio gravado em:" not in saida


def test_cli_curva_inexistente_retorna_2(capsys: pytest.CaptureFixture[str]):
    """CSV ausente devolve erro bilingue e codigo 2.

    A missing CSV returns a bilingual error and code 2.
    """
    codigo = main(
        [
            "simular",
            "--curva", str(Path(CURVA_REAL).parent / "nao-existe.csv"),
            "--contrato", CONTRATO_REAL,
            "--cargas", CARGAS_REAL,
        ]
    )
    assert codigo == 2
    erro = capsys.readouterr().err
    assert "Erro / error" in erro


def test_cli_contrato_invalido_retorna_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """YAML de contrato sem campos devolve codigo 2.

    A contract YAML without the fields returns code 2.
    """
    contrato_ruim = tmp_path / "contrato.yaml"
    contrato_ruim.write_text("unidade: X\n", encoding="utf-8")
    codigo = main(
        [
            "simular",
            "--curva", CURVA_REAL,
            "--contrato", str(contrato_ruim),
            "--cargas", CARGAS_REAL,
        ]
    )
    assert codigo == 2
    assert "Erro / error" in capsys.readouterr().err


def test_cli_sem_comando_retorna_2(capsys: pytest.CaptureFixture[str]):
    """Sem subcomando, argparse devolve erro de uso e codigo 2.

    Without a subcommand, argparse returns a usage error and code 2.
    """
    assert main([]) == 2
