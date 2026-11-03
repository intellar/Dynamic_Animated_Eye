"""Execution directe : `python -m animated_eye`.

Meme point d'entree que `main.py`, voir `animated_eye/cli.py`.
"""

from __future__ import annotations

from . import headless

headless.apply()

from .cli import main  # noqa: E402  (import apres le reglage SDL)

if __name__ == "__main__":
    raise SystemExit(main())
