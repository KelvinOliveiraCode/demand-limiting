"""Permite executar como ``python -m demandlimit``.

Enables running as ``python -m demandlimit``.
"""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
