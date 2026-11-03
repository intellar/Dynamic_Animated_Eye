"""Planches de controle rendues hors ecran, sans projecteur.

    python tools/preview.py

Genere dans `preview/` :

  * `world.png`       le monde complet, pour verifier la place du noir autour de l'oeil
  * `eyes.png`        chaque image d'oeil aux quatre coins du debattement
  * `saccade.png`     une planche temporelle de saccades (positions successives)
  * `feather.png`     le bord du patch sur fond rouge, pour voir la decoupe

Le rendu passe par le meme code que l'application (monde + viewport), donc ce
que montrent ces images est exactement ce que verra le projecteur.
"""

from __future__ import annotations

import argparse
import os
import random
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pygame  # noqa: E402

from animated_eye.config import Config  # noqa: E402
from animated_eye.eye_image import load_eyes  # noqa: E402
from animated_eye.pupil import PupilState  # noqa: E402
from animated_eye.saccade import Phase, SaccadeController  # noqa: E402
from animated_eye.world import build_world  # noqa: E402


def _label(surface: pygame.Surface, text: str) -> None:
    font = pygame.font.SysFont("consolas", 22)
    img = font.render(text, True, (255, 210, 60))
    surface.blit(img, (10, surface.get_height() - img.get_height() - 8))


def _sheet(tiles: list[pygame.Surface], cols: int, scale: float) -> pygame.Surface:
    tw = int(tiles[0].get_width() * scale)
    th = int(tiles[0].get_height() * scale)
    rows = (len(tiles) + cols - 1) // cols
    sheet = pygame.Surface((tw * cols, th * rows))
    sheet.fill((20, 20, 20))
    for i, tile in enumerate(tiles):
        sheet.blit(pygame.transform.smoothscale(tile, (tw, th)), ((i % cols) * tw, (i // cols) * th))
    return sheet


def render_world_views(
    world, size, positions, scale=0.5
) -> list[pygame.Surface]:
    tiles = []
    for nx, ny in positions:
        tile = pygame.Surface(size)
        tile.fill((0, 0, 0))
        tile.blit(world.surface, (0, 0), world.viewport(nx, ny))
        _label(tile, f"{nx:+.1f} {ny:+.1f}")
        tiles.append(pygame.transform.smoothscale(tile, (int(size[0] * scale), int(size[1] * scale))))
    return tiles


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="planches de controle")
    parser.add_argument("--out", type=Path, default=PROJECT_ROOT / "preview")
    parser.add_argument("--view", default="1920x1080")
    parser.add_argument("--travel", default=None, help="defaut: celui de la config")
    parser.add_argument("--iris-fraction", type=float, default=None)
    parser.add_argument("--feather", type=float, default=None)
    args = parser.parse_args(argv)

    view_w, view_h = (int(v) for v in args.view.lower().split("x"))

    cfg = Config()
    cfg.width, cfg.height = view_w, view_h
    if args.iris_fraction is not None:
        cfg.iris_fraction = args.iris_fraction
    if args.feather is not None:
        cfg.feather = args.feather
    if args.travel is not None:
        cfg.travel_x, cfg.travel_y = (int(v) for v in args.travel.lower().split("x"))
    travel_x, travel_y = cfg.travel_x, cfg.travel_y

    pygame.init()
    pygame.display.set_mode((64, 64))
    args.out.mkdir(parents=True, exist_ok=True)

    eyes = load_eyes(cfg, (view_w, view_h))
    print(f"echelle commune {eyes.scale:.4f}" + (" (plafonnee)" if eyes.scale_capped else ""))
    for sprite in eyes.sprites:
        m = sprite.measurement
        print(
            f"  {sprite.name:10s} iris {m.iris_diameter:6.1f} px source"
            f" ({m.iris_fraction:.1%}) -> {sprite.iris_diameter_screen:6.1f} px ecran"
            f"  sclera {m.sclera_level:.0f}"
        )
    for (i, j), r in sorted(eyes.residuals.items()):
        print(f"  ecart {eyes.sprites[i].name} <-> {eyes.sprites[j].name} : {r:.1f}/255")

    # --- monde complet ------------------------------------------------------
    pupil = PupilState(eyes, cfg)
    sprite = eyes[pupil.index]
    world = build_world(view_w, view_h, travel_x, travel_y, sprite.size)
    world.paint_sprite(sprite.surface)
    print(
        f"monde {world.surface.get_size()}  image {sprite.size}"
        f"  marge {world.rest_origin}  viewport {world.viewport(0, 0)}"
    )
    scale = min(1.0, 900 / max(world.surface.get_size()))
    full = pygame.transform.smoothscale(
        world.surface, (int(world.surface.get_width() * scale), int(world.surface.get_height() * scale))
    )
    border = pygame.Rect(0, 0, *world.viewport(0, 0).size)
    border.size = (int(border.width * scale), int(border.height * scale))
    border.center = (full.get_width() // 2, full.get_height() // 2)
    pygame.draw.rect(full, (60, 200, 90), border, 2)
    _label(full, "monde complet, cadre vert = fenetre au repos")
    pygame.image.save(full, str(args.out / "world.png"))

    # --- chaque oeil, quatre coins -----------------------------------------
    corners = [(0, 0), (-1, -1), (1, -1), (-1, 1), (1, 1)]
    for index, s in enumerate(eyes.sprites):
        world.paint_sprite(s.surface)
        tiles = render_world_views(world, (view_w, view_h), corners, scale=0.25)
        pygame.image.save(_sheet(tiles, 5, 1.0), str(args.out / f"{s.name}_corners.png"))

    # --- bord du patch sur fond rouge --------------------------------------
    world.paint_sprite(sprite.surface)
    probe = pygame.Surface((view_w, view_h))
    probe.fill((160, 0, 0))
    probe.blit(world.surface, (0, 0), world.viewport(0, 0))
    pygame.image.save(
        pygame.transform.smoothscale(probe, (view_w // 2, view_h // 2)),
        str(args.out / "feather.png"),
    )

    # --- planche temporelle de saccades ------------------------------------
    ctrl = SaccadeController(cfg, random.Random(7))
    dt = 1.0 / 60.0
    tiles = []
    for step in range(180):
        ctrl.update(dt)
        if step % 6 == 0:
            tile = pygame.Surface((view_w, view_h))
            tile.blit(world.surface, (0, 0), world.viewport(*ctrl.pos))
            _label(tile, f"t={step * dt * 1000:4.0f}ms {ctrl.phase.value}")
            tiles.append(tile)
    pygame.image.save(_sheet(tiles, 6, 0.16), str(args.out / "saccade.png"))

    # --- statistiques de mouvement ----------------------------------------
    ctrl = SaccadeController(cfg, random.Random(7))
    amps, durs, fixes = [], [], []
    for _ in range(60 * 30):
        before = ctrl.phase
        ctrl.update(dt)
        if ctrl.saccade_started:
            amps.append(ctrl.saccade_amplitude_px)
            durs.append(ctrl.duration_ms)
        if before is Phase.SACCADE and ctrl.phase is Phase.FIXATION:
            fixes.append(ctrl.duration_ms)
    if amps:
        print(
            f"\n30 s de simulation : {len(amps)} saccades, "
            f"amplitude moyenne {sum(amps) / len(amps):.0f} px "
            f"(max {max(amps):.0f}), duree {sum(durs) / len(durs):.0f} ms "
            f"({min(durs):.0f}-{max(durs):.0f})"
        )
        print(f"fixations : {sum(fixes) / len(fixes):.0f} ms moyenne ({len(fixes)} mesures)")
        print(f"saccades par seconde : {len(amps) / 30:.1f}")

    pygame.quit()
    print(f"\nplanches ecrites dans {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
