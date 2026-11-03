"""Quel pilote video ce pygame sait-il ouvrir ?

    .venv/bin/python scripts/video_check.py

Utile sur le Pi : `kmsdrm not available` ne dit pas si le probleme vient des
droits sur la carte DRM ou du pygame installe. Ce script essaie chaque pilote
et rend la main.

A savoir : le wheel pygame de PyPI embarque une SDL2 **sans KMSDRM**, donc
incapable de piloter un ecran depuis une console. Sur un Pi sans bureau, il
faut le pygame d'apt (`python3-pygame`), qui utilise la SDL2 du systeme.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# pygame affiche un message de bienvenue a l'import : inutile dans un diagnostic.
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

DRIVERS = ("kmsdrm", "x11", "wayland", "dummy")
HINTS = {
    "kmsdrm": "no accessible DRM card (video group) or SDL without KMSDRM",
    "x11": "no reachable X session (desktop)",
    "wayland": "no reachable Wayland compositor",
    "dummy": "always available, but draws nothing",
}


def kms_card() -> str | None:
    """Carte DRM qui porte un connecteur branche, ou None.

    Sur un Pi 4 c'est /dev/dri/card0. Sur un Pi 5, card0 est le noeud de rendu
    v3d (aucun connecteur) et l'ecran est sur /dev/dri/card1. SDL kmsdrm ne
    prend que card0 tant que SDL_VIDEO_KMSDRM_DEVICE n'est pas pose, il faut donc
    la designer explicitement pour que la sonde soit honnete.
    """
    for status in sorted(Path("/sys/class/drm").glob("card*-*/status")):
        try:
            if status.read_text().strip() != "connected":
                continue
        except OSError:
            continue
        return "/dev/dri/" + status.parent.name.split("-")[0]
    return None


def probe(driver: str) -> tuple[bool, str]:
    """Ouvre une petite fenetre avec ce pilote. Renvoie (succes, detail)."""
    import pygame

    os.environ["SDL_VIDEODRIVER"] = driver
    pygame.display.quit()
    try:
        pygame.display.init()
        surface = pygame.display.set_mode((320, 240))
    except pygame.error as exc:
        return False, str(exc)
    size = "x".join(str(v) for v in surface.get_size())
    real = pygame.display.get_driver()
    return True, f"{size}, driver in use {real}"


def main() -> int:
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    card = kms_card()
    if card:
        os.environ["SDL_VIDEO_KMSDRM_DEVICE"] = card
        print(f"DRM card with a connected display: {card}")
    else:
        print("no `connected` connector in /sys/class/drm")

    import pygame

    print(f"pygame {pygame.version.ver}  SDL {pygame.get_sdl_version()}")
    print(f"file {pygame.__file__}")

    usable: list[str] = []
    for driver in DRIVERS:
        ok, detail = probe(driver)
        mark = "ok  " if ok else "no  "
        print(f"  {mark} {driver:<8} {detail}")
        if ok and driver != "dummy":
            usable.append(driver)

    pygame.quit()
    os.environ.pop("SDL_VIDEODRIVER", None)

    if usable:
        if usable[0] == "kmsdrm":
            print("\nto project: sh scripts/run_kms.sh   (kmsdrm on the right card)")
        else:
            print(f"\nto project: SDL_VIDEODRIVER={usable[0]} python main.py")
        return 0

    print("\nno real display driver:")
    for driver in DRIVERS[:-1]:
        print(f"  {driver:<8} {HINTS[driver]}")
    print(
        "\nif kmsdrm is missing while /dev/dri/card0 is accessible, the pygame\n"
        "installed is the culprit: sudo apt install -y python3-pygame then\n"
        ".venv/bin/python -m pip uninstall -y pygame (the venv is created with\n"
        "--system-site-packages, so it will pick up the system pygame)."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
