"""Fenetre de projection.

Tout ce qui touche a SDL et a Windows est isole ici : selection de l'ecran,
plein ecran sans bordure, anti-veille, DPI. Le reste du programme ne connait
qu'une surface `screen` et une methode `present()`.

Le rendu tient en une seule operation par frame : copier le rectangle de la
fenetre depuis la grande surface du monde. C'est ce qui garantit un cout
constant et un vsync propre, quelle que soit la position de l'oeil.
"""

from __future__ import annotations

import ctypes
import os
import sys

import pygame

from .config import Config

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002

CAPTION = "Animated eye"

# Pilotes essayes en dernier recours quand `SDL_VIDEODRIVER` force un pilote que
# ce pygame ne connait pas. Sur un Pi avec bureau, x11/wayland est de toute
# facon le bon choix : kmsdrm exige une carte DRM libre (aucun bureau actif) et
# un utilisateur dans le groupe `video`.
FALLBACK_DRIVERS = ("x11", "wayland", "kmsdrm")


def prepare_environment() -> None:
    """DPI et anti-veille, a appeler avant `pygame.init()`."""
    if sys.platform != "win32":
        return
    try:
        # Sans ca, Windows met l'application a l'echelle et le plein ecran
        # n'occupe qu'une partie du projecteur.
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_DISPLAY_REQUIRED | ES_SYSTEM_REQUIRED
        )
    except Exception:
        pass


def release_environment() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
    except Exception:
        pass


def desktop_sizes() -> list[tuple[int, int]]:
    try:
        return list(pygame.display.get_desktop_sizes())
    except Exception:
        return []


def _set_mode(
    width: int, height: int, flags: int, display: int, vsync: bool
) -> pygame.Surface:
    if vsync:
        try:
            return pygame.display.set_mode(
                (width, height), flags, display=display, vsync=1
            )
        except TypeError:
            # pygame ancien : le parametre vsync n'existe pas
            pass
        except pygame.error:
            # certains pilotes refusent vsync : on retente sans
            pass
    return pygame.display.set_mode((width, height), flags, display=display)


def open_window(
    width: int,
    height: int,
    fullscreen: bool,
    display: int = 0,
    vsync: bool = True,
) -> tuple[pygame.Surface, str, list[str]]:
    """Ouvre la fenetre en essayant les pilotes SDL un par un.

    Renvoie `(surface, pilote, notes)`. `SDL_VIDEODRIVER` peut avoir ete force
    par l'utilisateur (le script de deploiement suggerait `kmsdrm`) : si ce
    pilote n'est pas compile dans le pygame installe, on retombe sur la
    detection automatique au lieu de mourir sur `kmsdrm not available`.
    """
    flags = pygame.DOUBLEBUF | (pygame.FULLSCREEN if fullscreen else 0)
    requested = os.environ.get("SDL_VIDEODRIVER")
    attempts: list[str | None] = [requested or None]
    if requested:
        attempts.append(None)
        attempts.extend(d for d in FALLBACK_DRIVERS if d != requested)

    errors: list[str] = []
    for driver in attempts:
        if driver is None:
            os.environ.pop("SDL_VIDEODRIVER", None)
        else:
            os.environ["SDL_VIDEODRIVER"] = driver
        try:
            pygame.display.quit()
            pygame.display.init()
            surface = _set_mode(width, height, flags, display, vsync)
        except pygame.error as exc:
            errors.append(f"{driver or 'auto'} : {exc}")
            continue

        pygame.display.set_caption(CAPTION)
        active = pygame.display.get_driver()
        notes: list[str] = []
        if errors:
            notes.append(
                f"video driver {active} (fallback after "
                + " / ".join(errors)
                + ")"
            )
        return surface, active, notes

    raise RuntimeError(
        "no usable window: "
        + " ; ".join(errors)
        + "\n  try without SDL_VIDEODRIVER, then from the Pi desktop, "
        "and check that the user is in the video group"
    )


class Renderer:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.fullscreen = cfg.fullscreen
        self.screen: pygame.Surface | None = None
        self.size = (cfg.width, cfg.height)
        self.driver = ""
        self.hud_font: pygame.font.Font | None = None
        self.clock = pygame.time.Clock()
        self.notes: list[str] = []

        prepare_environment()
        pygame.init()
        pygame.display.set_caption(CAPTION)
        if cfg.fullscreen and cfg.auto_size:
            start_w, start_h = self.target_size()
        else:
            start_w, start_h = cfg.width, cfg.height
        self._open(start_w, start_h, cfg.fullscreen)
        if cfg.fullscreen and cfg.auto_size:
            # La resolution de l'ecran n'est connue qu'une fois un pilote video
            # ouvert : on recale si la premiere ouverture s'est faite au hasard.
            want = self.target_size()
            if want != self.size:
                self._open(*want, cfg.fullscreen)

        pygame.mouse.set_visible(False)
        if cfg.debug:
            self.hud_font = pygame.font.SysFont("consolas", 20)

    # ------------------------------------------------------------------ setup
    def _open(self, width: int, height: int, fullscreen: bool) -> None:
        self.fullscreen = fullscreen
        self.screen, self.driver, notes = open_window(
            width,
            height,
            fullscreen,
            display=self.cfg.display,
            vsync=self.cfg.vsync,
        )
        self.notes.extend(n for n in notes if n not in self.notes)
        self.size = self.screen.get_size()

    def target_size(self) -> tuple[int, int]:
        """Resolution de rendu : celle de l'ecran cible si `auto_size`."""
        if not self.cfg.auto_size:
            return self.cfg.width, self.cfg.height
        sizes = desktop_sizes()
        if 0 <= self.cfg.display < len(sizes):
            return sizes[self.cfg.display]
        return self.cfg.width, self.cfg.height

    def reopen(self, width: int, height: int, fullscreen: bool) -> None:
        self._open(width, height, fullscreen)
        pygame.mouse.set_visible(False)

    def toggle_fullscreen(self) -> bool:
        width, height = self.target_size()
        self.reopen(width, height, not self.fullscreen)
        return self.fullscreen

    # ------------------------------------------------------------------ rendu
    def present(self, world_surface: pygame.Surface, area: pygame.Rect) -> None:
        self.screen.blit(world_surface, (0, 0), area)

    def blackout(self) -> None:
        self.screen.fill((0, 0, 0))

    def draw_hud(self, lines: list[str]) -> None:
        if self.hud_font is None:
            return
        y = 12
        for line in lines:
            surf = self.hud_font.render(line, True, (255, 210, 60))
            self.screen.blit(surf, (14, y))
            y += surf.get_height() + 4

    def flip(self) -> None:
        pygame.display.flip()

    def close(self) -> None:
        release_environment()
        pygame.quit()
