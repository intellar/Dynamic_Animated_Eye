"""Boucle principale.

Chaque frame fait exactement trois choses : avancer la simulation, repeindre le
monde si necessaire, copier la fenetre a l'ecran. Rien d'autre.
"""

from __future__ import annotations

import random

import pygame

from .config import Config
from .eye_image import EyeSet, load_eyes
from .geometry import (
    MAX_SPRITE_EXTENT,
    clamp_travel,
    fit_travel,
    is_region_of_interest,
    scale_travel,
)
from .pupil import PupilState
from .renderer import Renderer
from .saccade import Phase, SaccadeController
from .world import World, build_world

MAX_DT = 0.05


class App:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.renderer = Renderer(cfg)
        self.eyes: EyeSet | None = None
        self.world: World | None = None
        self.pupil: PupilState | None = None
        self.saccade: SaccadeController | None = None
        self.blackout = False
        self.show_hud = cfg.debug
        self.running = False
        self.notes: list[str] = []
        self._last_dt = 0.0
        self.requested_travel = (cfg.travel_x, cfg.travel_y)

        self._build(self.renderer.size)

    # ------------------------------------------------------------------ setup
    def _guard_travel(self, sprite_size: tuple[int, int]) -> list[str]:
        """Reduit le debattement si le monde noir depasserait le budget memoire."""
        view_w, view_h = self.renderer.size
        tx, ty, reduced = clamp_travel(
            view_w, view_h, self.cfg.travel_x, self.cfg.travel_y, sprite_size
        )
        if not reduced:
            return []
        self.cfg.travel_x, self.cfg.travel_y = tx, ty
        return [
            f"debattement ramene a {tx} x {ty} px "
            f"(monde trop grand pour {view_w}x{view_h})"
        ]

    def _resolve_travel(self) -> list[str]:
        """Debattement effectif : mis a l'echelle de l'ecran puis borne au cadre.

        `config.json` est ecrit pour un ecran 1920x1080. Un projecteur 720p ou
        un moniteur 4/3 ne doit ni voir l'oeil sortir du cadre, ni perdre la
        composition choisie : on reduit d'abord dans la proportion de l'ecran,
        puis on plafonne a ce que la geometrie permet reellement pour l'iris de
        l'image affichee.
        """
        assert self.eyes is not None
        notes: list[str] = []
        view_w, view_h = self.renderer.size
        tx, ty = scale_travel(*self.requested_travel, view_w, view_h)
        if (tx, ty) != tuple(self.requested_travel):
            notes.append(
                f"debattement mis a l'echelle de l'ecran {view_w}x{view_h} : "
                f"{tx} x {ty} px (reference {self.requested_travel[0]} x "
                f"{self.requested_travel[1]} pour 1920x1080)"
            )

        iris = self.eyes[self.pupil.index].iris_diameter_screen
        fx, fy = fit_travel(tx, ty, view_w, view_h, iris)
        if (fx, fy) != (tx, ty):
            notes.append(
                f"debattement borne a {fx} x {fy} px pour que l'iris "
                f"({iris:.0f} px) reste dans le cadre {view_w}x{view_h}"
            )
        self.cfg.travel_x, self.cfg.travel_y = fx, fy

        notes.extend(self._guard_travel(self.eyes[self.pupil.index].size))
        return notes

    def _build(self, view_size: tuple[int, int]) -> None:
        view_w, view_h = view_size
        self.notes = list(self.cfg.validate()) + list(self.renderer.notes)

        self.eyes = load_eyes(self.cfg, view_size)
        if self.eyes.scale_capped:
            self.notes.append(
                f"oeil plafonne a l'echelle {self.eyes.scale:.3f} "
                f"(demande {self.eyes.requested_scale:.3f}) : image limitee a "
                f"{MAX_SPRITE_EXTENT} px de cote"
            )
        self.pupil = PupilState(self.eyes, self.cfg)
        self.notes.extend(self.pupil.warnings)

        sprite_size = self.eyes[self.pupil.index].size

        self.notes.extend(self._resolve_travel())
        self.saccade = SaccadeController(self.cfg)

        self.world = build_world(
            view_w,
            view_h,
            self.cfg.travel_x,
            self.cfg.travel_y,
            sprite_size,
        )
        if not is_region_of_interest(view_w, view_h, sprite_size):
            self.notes.append(
                f"l'oeil ({sprite_size[0]}x{sprite_size[1]} px) tient entierement "
                f"dans la fenetre ({view_w}x{view_h}) : augmenter iris_fraction "
                f"pour que la fenetre soit une decoupe de l'image"
            )

    def report(self) -> str:
        assert self.eyes is not None and self.pupil is not None
        sprite = self.eyes[self.pupil.index]
        travel = f"debattement  x +/-{self.cfg.travel_x} px   y +/-{self.cfg.travel_y} px"
        if (self.cfg.travel_x, self.cfg.travel_y) != tuple(self.requested_travel):
            travel += (
                f"  (reference {self.requested_travel[0]} x "
                f"{self.requested_travel[1]} pour 1920x1080)"
            )
        lines = [
            f"fenetre      {self.renderer.size[0]}x{self.renderer.size[1]}"
            f"  ecran {self.cfg.display}  pilote {self.renderer.driver or '?'}",
            f"monde        {self.world.surface.get_size()[0]}x"
            f"{self.world.surface.get_size()[1]}",
            f"oeil         {sprite.name}  {sprite.size[0]}x{sprite.size[1]} px"
            f"  iris {sprite.iris_diameter_screen:.0f} px"
            f" ({sprite.iris_diameter_screen / self.renderer.size[1]:.0%} de la hauteur)"
            f"  echelle {self.eyes.scale:.3f}",
            travel,
        ]
        roi = is_region_of_interest(
            self.renderer.size[0], self.renderer.size[1], sprite.size
        )
        lines.append(
            "cadrage      "
            + (
                "ROI : la fenetre montre une decoupe de l'image"
                if roi
                else "l'image tient dans la fenetre (pas de ROI)"
            )
        )
        for i, other in enumerate(self.eyes.sprites):
            r = self.eyes.residual(self.pupil.index, i)
            if r is not None and i != self.pupil.index:
                lines.append(f"ecart {sprite.name} <-> {other.name} : {r:.1f}/255")
        return "\n".join(lines)

    # ----------------------------------------------------------------- events
    def _handle_events(self) -> None:
        assert self.pupil is not None and self.saccade is not None
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self._handle_key(event.key)

    def _handle_key(self, key: int) -> None:
        assert self.pupil is not None and self.saccade is not None
        if key in (pygame.K_ESCAPE, pygame.K_q):
            self.running = False
        elif key == pygame.K_f:
            size_before = self.renderer.size
            self.renderer.toggle_fullscreen()
            if self.renderer.size != size_before:
                self._build(self.renderer.size)
        elif key == pygame.K_b:
            self.blackout = not self.blackout
        elif key == pygame.K_d:
            self.show_hud = not self.show_hud
        elif key == pygame.K_SPACE:
            self.pupil.cycle()
            self._adopt_sprite()
        elif key == pygame.K_s:
            self.saccade.force_saccade()
            self.pupil.on_saccade()
        elif key == pygame.K_p:
            self.pupil.toggle_auto()
        elif key == pygame.K_r:
            self.saccade = SaccadeController(
                self.cfg, random.Random(self.cfg.seed if self.cfg.seed else None)
            )
        elif pygame.K_1 <= key <= pygame.K_9:
            self.pupil.set_state(key - pygame.K_1)
            self._adopt_sprite()

    def _adopt_sprite(self) -> None:
        """Recale le monde si l'image affichee change de taille ou de debattement.

        L'iris n'a pas le meme diametre d'une image a l'autre : le debattement
        maximal change donc aussi, et le monde doit etre reconstruit pour rester
        une decoupe valide de l'image.
        """
        assert self.world is not None
        before = (self.cfg.travel_x, self.cfg.travel_y)
        self._resolve_travel()
        size = self.eyes[self.pupil.index].size
        if (
            tuple(size) == tuple(self.world.sprite_rect.size)
            and before == (self.cfg.travel_x, self.cfg.travel_y)
        ):
            return
        self.world = build_world(
            self.renderer.size[0],
            self.renderer.size[1],
            self.cfg.travel_x,
            self.cfg.travel_y,
            size,
        )

    # ------------------------------------------------------------------- frame
    def _frame(self, dt: float) -> None:
        assert self.pupil is not None and self.saccade is not None
        assert self.world is not None

        self._last_dt = dt
        self.saccade.update(dt)
        if self.saccade.saccade_started:
            self.pupil.on_saccade()
        self.pupil.update(dt)

        base, overlay, alpha = self.pupil.blend()
        self.world.paint_sprite(base, overlay, alpha)

        if self.blackout:
            self.renderer.blackout()
        else:
            self.renderer.present(
                self.world.surface, self.world.viewport(*self.saccade.pos)
            )

        if self.show_hud:
            self.renderer.draw_hud(self._hud_lines())

    def _hud_lines(self) -> list[str]:
        assert self.saccade is not None and self.pupil is not None
        s = self.saccade
        sprite = self.eyes[self.pupil.index]
        phase = "fixation" if s.phase is Phase.FIXATION else "saccade"
        return [
            f"{self.renderer.clock.get_fps():5.1f} fps   dt {1000 * self._last_dt:5.1f} ms",
            f"phase    {phase}",
            f"position {s.pos[0]:+.3f} {s.pos[1]:+.3f}",
            f"amplitude {s.saccade_amplitude_px:6.1f} px",
            f"oeil     {sprite.name}  {self.pupil.index + 1}/{len(self.eyes)}"
            f"   auto {'on' if self.pupil.auto else 'off'}",
            f"travel   {self.cfg.travel_x} x {self.cfg.travel_y}",
        ]

    # -------------------------------------------------------------------- run
    def run(self) -> int:
        self.running = True
        clock = self.renderer.clock
        while self.running:
            dt = min(clock.tick(self.cfg.fps) / 1000.0, MAX_DT)
            self._handle_events()
            if not self.running:
                break
            self._frame(dt)
            self.renderer.flip()
        self.renderer.close()
        return 0
