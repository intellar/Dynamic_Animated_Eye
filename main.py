"""Point d'entree : `python -m animated_eye` ou `python main.py`."""

from __future__ import annotations

import os
import sys
import time

# Le selftest sert au deploiement (Pi sans X, CI) : il ne doit jamais ouvrir de
# fenetre. SDL lit ces variables a l'initialisation, donc les poser avant
# d'importer le paquet suffit.
if "--selftest" in sys.argv[1:]:
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"

from animated_eye.app import App
from animated_eye.config import DEFAULT_CONFIG_PATH, apply_cli, load_config
from animated_eye.renderer import desktop_sizes, prepare_environment


def _list_displays() -> int:
    prepare_environment()
    import pygame

    from animated_eye.renderer import open_window

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


def _selftest(frames: int = 120) -> int:
    """Charge les vraies images, rend quelques frames, verifie la geometrie.

    C'est ce que lance `scripts/deploy.ps1` apres la copie sur le Pi : si une
    image manque, si numpy ou pygame n'est pas le bon, ou si la fenetre n'est
    pas une decoupe de l'image, on le sait tout de suite.
    """
    from animated_eye.geometry import is_region_of_interest

    cfg = load_config(DEFAULT_CONFIG_PATH)
    cfg, _ = apply_cli(cfg, [])
    cfg.fullscreen = False
    cfg.auto_size = False
    cfg.debug = False

    app = App(cfg)
    print(app.report())
    for note in app.notes:
        print(f"  ! {note}")

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
        res = app.eyes.residual(pair[0], pair[1])
        if res is not None:
            print(f"  ecart pupille {pair[0]} <-> {pair[1]} : {res:.1f}/255")

    clock = app.renderer.clock
    start = time.perf_counter()
    for _ in range(frames):
        clock.tick(1000)
        app._frame(1.0 / 60.0)
        app.renderer.flip()
    elapsed = time.perf_counter() - start
    app.renderer.close()

    print(f"selftest : {frames} frames en {elapsed:.2f} s "
          f"({frames / elapsed:.0f} fps hors vsync)")
    for problem in problems:
        print(f"  ERREUR {problem}")
    return 1 if problems else 0


def main(argv: list[str] | None = None) -> int:
    cfg = load_config(DEFAULT_CONFIG_PATH)
    cfg, ns = apply_cli(cfg, argv)

    if getattr(ns, "list_displays", False):
        return _list_displays()
    if getattr(ns, "selftest", False):
        return _selftest()

    app = App(cfg)

    print(app.report())
    for note in app.notes:
        print(f"  ! {note}")
    print("  echap/q quitter   f plein ecran   b noir   d hud   espace saccade")
    keys = "/".join(str(i + 1) for i in range(len(app.cfg.images)))
    print(f"  {keys} image{'s' if len(app.cfg.images) > 1 else ''}       "
          "p pupille auto   r nouvelle graine")
    sys.stdout.flush()

    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
