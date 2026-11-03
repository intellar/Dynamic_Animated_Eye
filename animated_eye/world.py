"""Le « monde » : une grande surface noire sur laquelle glisse la fenetre.

C'est le coeur de l'illusion. L'oeil ne bouge pas : il est pose une fois pour
toutes au centre d'une surface plus grande que l'ecran. Chaque frame, on ne
copie que le rectangle correspondant a la fenetre du projecteur. Deplacer ce
rectangle donne l'impression que l'oeil se deplace.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pygame

from .geometry import world_size


@dataclass
class World:
    surface: pygame.Surface
    view_width: int
    view_height: int
    travel_x: int
    travel_y: int
    sprite_rect: pygame.Rect
    rest_origin: tuple[int, int]
    _sprite_key: tuple = field(default=(), repr=False)

    # ---------------------------------------------------------------- rendu
    def paint_sprite(
        self,
        base: pygame.Surface,
        overlay: pygame.Surface | None = None,
        overlay_alpha: int = 0,
    ) -> bool:
        """(Re)peint le sprite dans le monde. Renvoie True si quelque chose a change.

        Pendant un fondu de pupille, on repeint uniquement le rectangle du sprite
        (une zone de la taille du patch, pas de l'ecran), et seulement quand l'opacite
        a bouge d'au moins un niveau.
        """
        key = (id(base), id(overlay), overlay_alpha)
        if key == self._sprite_key:
            return False
        self._sprite_key = key

        self.surface.fill((0, 0, 0), self.sprite_rect)
        self.surface.blit(base, self.sprite_rect.topleft)
        if overlay is not None and overlay_alpha > 0:
            overlay.set_alpha(overlay_alpha)
            self.surface.blit(overlay, self.sprite_rect.topleft)
            overlay.set_alpha(None)
        return True

    def viewport(self, nx: float, ny: float) -> pygame.Rect:
        """Rectangle source a copier vers l'ecran pour un decalage normalise."""
        max_x = self.surface.get_width() - self.view_width
        max_y = self.surface.get_height() - self.view_height

        nx = min(max(nx, -1.0), 1.0)
        ny = min(max(ny, -1.0), 1.0)
        ox = self.rest_origin[0] + nx * self.travel_x
        oy = self.rest_origin[1] + ny * self.travel_y

        ox = int(round(min(max(ox, 0), max_x)))
        oy = int(round(min(max(oy, 0), max_y)))
        return pygame.Rect(ox, oy, self.view_width, self.view_height)


def build_world(
    view_width: int,
    view_height: int,
    travel_x: int,
    travel_y: int,
    sprite_size: tuple[int, int],
) -> World:
    """Construit la surface noire et y place le sprite au centre."""
    sprite_w, sprite_h = sprite_size

    world_w, world_h = world_size(
        view_width, view_height, travel_x, travel_y, sprite_size
    )

    surface = pygame.Surface((world_w, world_h))
    surface.fill((0, 0, 0))

    sprite_rect = pygame.Rect(
        (world_w - sprite_w) // 2,
        (world_h - sprite_h) // 2,
        sprite_w,
        sprite_h,
    )
    rest_origin = ((world_w - view_width) // 2, (world_h - view_height) // 2)

    return World(
        surface=surface,
        view_width=view_width,
        view_height=view_height,
        travel_x=travel_x,
        travel_y=travel_y,
        sprite_rect=sprite_rect,
        rest_origin=rest_origin,
    )
