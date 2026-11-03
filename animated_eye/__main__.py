"""Execution directe : `python -m animated_eye`."""

from __future__ import annotations

import sys

from .app import App
from .config import DEFAULT_CONFIG_PATH, apply_cli, load_config


def main(argv: list[str] | None = None) -> int:
    cfg = load_config(DEFAULT_CONFIG_PATH)
    cfg, ns = apply_cli(cfg, argv)
    if getattr(ns, "list_displays", False):
        from .renderer import prepare_environment

        prepare_environment()
        import pygame

        pygame.init()
        from .renderer import desktop_sizes

        for i, (w, h) in enumerate(desktop_sizes()):
            print(f"ecran {i} : {w}x{h}")
        pygame.quit()
        return 0

    app = App(cfg)
    print(app.report())
    for note in app.notes:
        print(f"  ! {note}")
    sys.stdout.flush()
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
