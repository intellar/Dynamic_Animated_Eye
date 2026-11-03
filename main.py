"""Point d'entree principal : `python main.py`.

Le code vit dans `animated_eye/cli.py` : ce fichier ne fait que choisir le pilote
SDL quand on demande le selftest, puis deleguer.
"""

from __future__ import annotations

from animated_eye import headless

headless.apply()

from animated_eye.cli import main  # noqa: E402  (import apres le reglage SDL)

if __name__ == "__main__":
    raise SystemExit(main())
