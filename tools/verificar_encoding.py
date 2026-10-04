"""Confere encoding dos arquivos de texto versionados.

Check the encoding of every text file under the repository root.

Um BOM UTF-8 no inicio, um caractere de substituicao (U+FFFD) ou um bloco
CJK dentro de um arquivo de codigo indica que alguma passagem de texto
corrompeu a escrita. No GitHub o resultado aparece como lixo no diff, entao
e mais barato falhar aqui.

Um U+FFFD e um caractere de substituicao. Um bloco CJK e um texto em japonês,
chines ou coreano. Nenhum dos dois pertence a este repositorio.
"""

from __future__ import annotations

import sys
from pathlib import Path

#: Raiz do repositorio.
RAIZ = Path(__file__).resolve().parent.parent

#: Extensoes varridas. Binarios ficam de fora de proposito.
EXTENSOES = {
    ".py",
    ".md",
    ".txt",
    ".json",
    ".yml",
    ".yaml",
    ".toml",
    ".cfg",
    ".ini",
    ".ps1",
}

#: Diretorios e arquivos ignorados.
IGNORADOS = {".git", "__pycache__", ".pytest_cache", ".coverage"}

#: Sufixos binarios ignorados de forma explicita.
BINARIOS = {".png", ".jpg", ".mp4", ".woff", ".woff2"}

#: BOM UTF-8 como caractere (U+FEFF no inicio do arquivo).
BOM = "\ufeff"

#: Caractere de substituicao.
SUBSTITUICAO = 0xFFFD

#: Intervalo de ideogramas CJK.
CJK = range(0x3000, 0x9FFF + 1)


def varrer(raiz: Path = RAIZ) -> tuple[list[tuple[str, int, str]], int]:
    """Procura arquivo de texto com caractere invalido.

    Find text files holding an invalid character.

    Args:
        raiz: Diretorio a varrer.

    Returns:
        Lista de ``(caminho, linha, motivo)`` e contador de arquivos.
    """
    problemas: list[tuple[str, int, str]] = []
    conferidos = 0
    for caminho in sorted(raiz.rglob("*")):
        if not caminho.is_file():
            continue
        if any(parte in IGNORADOS for parte in caminho.parts):
            continue
        if caminho.suffix.lower() in BINARIOS:
            continue
        if caminho.suffix.lower() not in EXTENSOES:
            continue
        conferidos += 1
        try:
            texto = caminho.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            problemas.append((
                str(caminho.relative_to(raiz)),
                0,
                f"nao decodifica como UTF-8: {exc}",
            ))
            continue
        if texto.startswith(BOM):
            problemas.append((
                str(caminho.relative_to(raiz)),
                1,
                "BOM UTF-8 no inicio",
            ))
        for numero, linha in enumerate(texto.splitlines(), 1):
            for caractere in linha:
                ponto = ord(caractere)
                if ponto == SUBSTITUICAO:
                    problemas.append((
                        str(caminho.relative_to(raiz)),
                        numero,
                        "caractere de substituicao U+FFFD",
                    ))
                    break
                if ponto in CJK:
                    problemas.append((
                        str(caminho.relative_to(raiz)),
                        numero,
                        f"ideograma CJK U+{ponto:04X}",
                    ))
                    break
    return problemas, conferidos


def main() -> int:
    """Executa a varredura e reporta.

    Run the sweep and report.
    """
    problemas, conferidos = varrer()
    print(f"arquivos conferidos: {conferidos}")
    if not problemas:
        print(
            "encoding ok: nenhum BOM, U+FFFD ou ideograma CJK"
        )
        return 0
    print(f"encoding FALHOU: {len(problemas)} ocorrencia(s)")
    for caminho, linha, motivo in problemas:
        onde = f"{caminho}:{linha}" if linha else caminho
        print(f"  {onde}: {motivo}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
