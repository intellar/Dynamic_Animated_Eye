"""Ligne de commande : `python main.py` et `python -m animated_eye`.

Le point d'entree vit ici plutot que dans `main.py` : les deux facons de lancer
le programme partagent ainsi exactement le meme comportement, et le paquet reste
importable sans effet de bord (`import animated_eye` n'ouvre aucune fenetre).
"""

from __future__ import annotations

import sys
import time

from .app import App
from .config import Config, load_from_argv
from .geometry import is_region_of_interest


def _report(app: App) -> None:
    """Cadrage, echelle et ecarts photometriques, puis les avertissements."""
    print(app.report())
    for note in app.notes:
        print(f"  ! {note}")


def list_displays() -> int:
    """Liste le pilote video et les moniteurs disponibles, puis quitte."""
    from .renderer import desktop_sizes, open_window, prepare_environment

    prepare_environment()
    import pygame

    pygame.init()
    try:
        _surface, driver, notes = open_window(320, 240, False)
    except RuntimeError as exc:
        print(exc)
        return 1
    for note in notes:
        print(f"  ! {note}")
    print(f"pilote video : {driver}")
    sizes = desktop_sizes()
    if not sizes:
        print("aucun ecran detecte")
    for i, (w, h) in enumerate(sizes):
        print(f"ecran {i} : {w}x{h}")
    pygame.quit()
    return 0


def selftest(cfg: Config, frames: int = 120) -> int:
    """Charge les vraies images, rend quelques frames hors ecran, verifie la geometrie.

    C'est ce que lance `scripts/deploy.ps1` apres la copie sur le Pi : si une
    image manque, si numpy ou pygame n'est pas le bon, ou si la fenetre n'est
    pas une decoupe de l'image, on le sait tout de suite, sans projecteur.
    """
    cfg.fullscreen = False
    cfg.auto_size = False
    cfg.debug = False

    app = App(cfg)
    _report(app)

    view_w, view_h = app.renderer.size
    problems: list[str] = []
    for eye in app.eyes:
        if not is_region_of_interest(view_w, view_h, eye.size):
            problems.append(
                f"{eye.name} ({eye.size[0]}x{eye.size[1]} px) tient entierement "
                f"dans la fenetre {view_w}x{view_h} : la fenetre doit etre une "
                f"decoupe de l'image (augmenter iris_fraction)"
            )
        elif not app.world.sprite_rect.colliderect(app.world.viewport(1.0, 1.0)):
            problems.append(f"{eye.name} sort completement du cadre a +1,+1")

    pair = tuple(app.cfg.pupil_pair)
    if len(pair) == 2:
        residual = app.eyes.residual(pair[0], pair[1])
        if residual is not None:
            print(f"  ecart pupille {pair[0]} <-> {pair[1]} : {residual:.1f}/255")

    clock = app.renderer.clock
    start = time.perf_counter()
    for _ in range(frames):
        clock.tick(1000)
        app.step(1.0 / 60.0)
        app.renderer.flip()
    elapsed = time.perf_counter() - start
    app.renderer.close()

    print(
        f"selftest : {frames} frames en {elapsed:.2f} s "
        f"({frames / elapsed:.0f} fps hors vsync)"
    )
    for problem in problems:
        print(f"  ERREUR {problem}")
    return 1 if problems else 0


def main(argv: list[str] | None = None) -> int:
    cfg, ns = load_from_argv(argv)

    if ns.list_displays:
        return list_displays()
    if ns.selftest:
        return selftest(cfg)

    app = App(cfg)
    _report(app)
    print("  echap/q quitter   f plein ecran   b noir   d hud   espace saccade")
    keys = "/".join(str(i + 1) for i in range(len(app.cfg.images)))
    print(
        f"  {keys} image{'s' if len(app.cfg.images) > 1 else ''}       "
        "p pupille auto   r nouvelle graine"
    )
    sys.stdout.flush()
    return app.run()
