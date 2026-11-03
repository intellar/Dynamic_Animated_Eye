"""Execution sans ecran : le pilote video SDL `dummy`.

`--selftest` charge les vraies images et rend quelques frames, mais ne doit
jamais ouvrir de fenetre : il tourne sur un Pi sans bureau ou derriere un ssh.
SDL lit ces variables au moment de son initialisation, donc elles doivent etre
posees **avant** d'importer pygame. D'ou un module separe, sans dependance,
importable en premier.
"""

from __future__ import annotations

import os
import sys

SELFTEST_FLAG = "--selftest"


def apply(argv: list[str] | None = None) -> bool:
    """Force le pilote `dummy` si `--selftest` est demande.

    Renvoie True si l'environnement a ete modifie.
    """
    args = sys.argv[1:] if argv is None else argv
    if SELFTEST_FLAG not in args:
        return False
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    return True
