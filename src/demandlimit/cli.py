"""CLI do demandlimit - simulador de corte de demanda.

CLI entry point for demandlimit.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from . import __version__
from .corte import carregar_cargas, planejar_cortes
from .demanda import carregar_contrato, carregar_curva
from .relatorio import gerar_relatorio
from .simulador import comparar, simular

CAMINHO_CARGAS_PADRAO = "dados/cargas.yaml"


def _resumo_linhas(sem, com) -> list[str]:
    """Linhas de resumo para o terminal.

    Summary lines for the terminal.
    """
    comp = comparar(sem, com)
    linhas = [
        "Simulacao concluida / simulation complete",
        f"- Demanda do mes (sem corte): {sem.demanda_mensal_kw:.2f} kW",
        f"- Demanda do mes (com corte): {com.demanda_mensal_kw:.2f} kW",
        f"- Custo total sem corte: R$ {sem.custo_total:,.2f}",
        f"- Custo total com corte: R$ {com.custo_total:,.2f}",
        f"- Economia: R$ {comp.economia:,.2f} ({comp.percentual:.2f}%)",
        f"- Multa evitada: R$ {comp.multa_evitada:,.2f}",
    ]
    if comp.multa_evitada > 0:
        linhas.append(
            "AVISO: sem corte, a demanda estoura o contrato; a multa de excedente "
            "e evitada com o corte."
            " WARNING: without the cut the demand exceeds the contract; the "
            "excess fine is avoided with the cut."
        )
    return linhas


def _cmd_simular(args: argparse.Namespace) -> int:
    """Simula o mes com e sem corte e emite o relatorio.

    Simulate the month with and without cut and emit the report.
    """
    cargas = carregar_cargas(args.cargas)
    contrato = carregar_contrato(args.contrato)
    curva = carregar_curva(args.curva, cargas)

    plano = planejar_cortes(
        curva,
        cargas,
        contrato.demanda_contratada_kw,
        contrato.tempo_minimo_acionamento_minutos // 15,
    )

    sem = simular(curva, contrato, cargas, com_corte=False)
    com = simular(curva, contrato, cargas, com_corte=True)

    for linha in _resumo_linhas(sem, com):
        print(linha)

    relatorio = gerar_relatorio(
        curva, contrato, cargas, plano, sem, com, top_dias=args.top
    )
    if args.saida:
        caminho = Path(args.saida)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(relatorio, encoding="utf-8")
        print(f"Relatorio gravado em: {caminho}")
    else:
        print()
        print(relatorio.rstrip())
    return 0


def _cmd_cargas(args: argparse.Namespace) -> int:
    """Lista as cargas configuradas.

    List the configured loads.
    """
    cargas = carregar_cargas(args.arquivo)
    print(f"Cargas / loads ({args.arquivo}):")
    for carga in sorted(cargas, key=lambda c: (c.prioridade, c.nome)):
        print(
            f"  {carga.nome:<24} {carga.tipo:<14} prioridade {carga.prioridade} "
            f"corte max {carga.recorte_maximo_percent:.0f}%"
        )
    return 0


def construir_parser() -> argparse.ArgumentParser:
    """Monta o parser de argumentos.

    Build the argument parser.
    """
    parser = argparse.ArgumentParser(
        prog="demandlimit",
        description=(
            "Simula tarifacao horaria e corte de demanda dentro da demanda "
            "contratada. Simulates hourly tariffs and demand cut to stay "
            "within the contracted demand."
        ),
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    p_sim = sub.add_parser(
        "simular",
        help="Simula o mes com e sem corte e emite o relatorio.",
    )
    p_sim.add_argument("--curva", required=True, help="CSV da curva de carga.")
    p_sim.add_argument("--contrato", required=True, help="YAML do contrato.")
    p_sim.add_argument(
        "--cargas",
        default=CAMINHO_CARGAS_PADRAO,
        help=f"YAML das cargas (default: {CAMINHO_CARGAS_PADRAO}).",
    )
    p_sim.add_argument(
        "--saida",
        help="Grava o relatorio Markdown neste caminho (nao informado: terminal).",
    )
    p_sim.add_argument(
        "--top",
        type=int,
        default=5,
        help="Quantos dias de pico detalhar no relatorio (default: 5).",
    )
    p_sim.set_defaults(func=_cmd_simular)

    p_car = sub.add_parser("cargas", help="Lista as cargas configuradas.")
    p_car.add_argument(
        "--arquivo",
        default=CAMINHO_CARGAS_PADRAO,
        help=f"YAML das cargas (default: {CAMINHO_CARGAS_PADRAO}).",
    )
    p_car.set_defaults(func=_cmd_cargas)

    parser.add_argument(
        "--versao",
        action="version",
        version=f"demandlimit {__version__}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Ponto de entrada da CLI.

    CLI entry point.
    """
    parser = construir_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # --help e --versao encerram com codigo 0; erro de argumento, 2.
        # --help and --versao exit with code 0; argument error, 2.
        return int(exc.code) if exc.code is not None else 0
    try:
        return int(args.func(args))
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"Erro / error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
