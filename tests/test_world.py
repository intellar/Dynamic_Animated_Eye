"""Verifications du monde : la fenetre est une decoupe qui glisse sur l'image."""

from __future__ import annotations

import pygame

from animated_eye.config import Config
from animated_eye.geometry import is_region_of_interest
from animated_eye.world import build_world

VIEW = (1920, 1080)
TRAVEL = (560, 180)
SPRITE = (1978, 1978)


def test_world_is_large_enough_for_the_whole_travel():
    world = build_world(*VIEW, *TRAVEL, SPRITE)
    assert world.surface.get_width() >= VIEW[0] + 2 * TRAVEL[0]
    assert world.surface.get_height() >= VIEW[1] + 2 * TRAVEL[1]


def test_sprite_is_centred_in_the_world():
    world = build_world(*VIEW, *TRAVEL, SPRITE)
    assert world.sprite_rect.centerx * 2 == world.surface.get_width()
    assert world.sprite_rect.centery * 2 == world.surface.get_height()


def test_viewport_at_rest_is_centred():
    world = build_world(*VIEW, *TRAVEL, SPRITE)
    assert world.viewport(0.0, 0.0).center == (
        world.surface.get_width() // 2,
        world.surface.get_height() // 2,
    )


def test_window_is_a_crop_of_the_image():
    """Le coeur du modele : la fenetre ne montre qu'une partie de l'image."""
    world = build_world(*VIEW, *TRAVEL, SPRITE)
    assert not world.viewport(0.0, 0.0).contains(world.sprite_rect)
    assert is_region_of_interest(*VIEW, SPRITE) is True


def test_the_image_always_covers_the_window():
    """Ou que soit la fenetre, l'oeil est visible : jamais un ecran noir."""
    world = build_world(*VIEW, *TRAVEL, SPRITE)
    for nx in (-1.0, -0.5, 0.0, 0.5, 1.0):
        for ny in (-1.0, -0.5, 0.0, 0.5, 1.0):
            assert world.viewport(nx, ny).colliderect(world.sprite_rect), (nx, ny)


def test_viewport_stays_inside_the_world():
    world = build_world(*VIEW, *TRAVEL, SPRITE)
    for nx in (-1.0, 0.0, 1.0):
        for ny in (-1.0, 0.0, 1.0):
            assert world.surface.get_rect().contains(world.viewport(nx, ny))


def test_offsets_beyond_one_are_clamped():
    world = build_world(*VIEW, *TRAVEL, SPRITE)
    assert world.viewport(5.0, 5.0) == world.viewport(1.0, 1.0)
    assert world.viewport(-5.0, -5.0) == world.viewport(-1.0, -1.0)


def test_zero_travel_keeps_the_viewport_still():
    world = build_world(*VIEW, 0, 0, SPRITE)
    assert world.viewport(-1.0, 1.0) == world.viewport(0.0, 0.0)


def test_moving_the_viewport_moves_the_eye_on_screen():
    """La fenetre glisse dans le monde : l'oeil parait se deplacer a l'ecran."""
    world = build_world(*VIEW, *TRAVEL, SPRITE)
    rest = world.viewport(0.0, 0.0)
    right = world.viewport(1.0, 0.0)
    assert right.x - rest.x == TRAVEL[0]
    assert right.y == rest.y


def test_paint_is_skipped_when_nothing_changed():
    world = build_world(*VIEW, *TRAVEL, (710, 710))
    sprite = pygame.Surface((710, 710))
    sprite.fill((200, 200, 200))
    assert world.paint_sprite(sprite) is True
    assert world.paint_sprite(sprite) is False


def test_paint_replaces_the_previous_sprite():
    world = build_world(*VIEW, *TRAVEL, (710, 710))
    first = pygame.Surface((710, 710))
    first.fill((200, 200, 200))
    second = pygame.Surface((710, 710))
    second.fill((10, 10, 10))
    world.paint_sprite(first)
    world.paint_sprite(second)
    assert world.surface.get_at(world.sprite_rect.center)[:3] == (10, 10, 10)


def test_real_assets_cover_the_frame_at_rest():
    """Au repos la fenetre tombe entierement dans l'image : aucun raccord noir."""
    from animated_eye.eye_image import load_eyes

    cfg = Config()
    eyes = load_eyes(cfg, VIEW)
    for sprite in eyes:
        assert is_region_of_interest(*VIEW, sprite.size) is True
        world = build_world(*VIEW, cfg.travel_x, cfg.travel_y, sprite.size)
        world.paint_sprite(sprite.surface)
        assert world.viewport(0.0, 0.0).contains(world.sprite_rect) is False
        assert world.sprite_rect.contains(world.viewport(0.0, 0.0)) is True


def test_real_assets_show_black_at_the_edge_the_eye_leaves():
    """Quand la ROI sort de l'image, le bord correspondant passe au noir."""
    from animated_eye.eye_image import load_eyes

    cfg = Config()
    eyes = load_eyes(cfg, VIEW)
    sprite = eyes[0]
    world = build_world(*VIEW, cfg.travel_x, cfg.travel_y, sprite.size)
    world.paint_sprite(sprite.surface)
    frame = pygame.surfarray.array3d(world.surface)

    r = world.viewport(1.0, 0.0)
    assert frame[r.x + r.w - 1].max() == 0
    r = world.viewport(-1.0, 0.0)
    assert frame[r.x].max() == 0


def test_real_assets_never_cut_the_eye_at_the_travel_extremes():
    """Aux huit positions extremes, le coeur lumineux de l'oeil reste dans le cadre.

    C'est la contrainte qui borne `travel_x` / `travel_y` : le fond etant noir,
    un oeil coupe par le bord de l'ecran se verrait tout de suite.
    """
    from animated_eye.eye_image import load_eyes

    cfg = Config()
    eyes = load_eyes(cfg, VIEW)
    sprite = eyes[0]
    world = build_world(*VIEW, cfg.travel_x, cfg.travel_y, sprite.size)
    world.paint_sprite(sprite.surface)

    margin = 16
    for nx in (-1.0, 0.0, 1.0):
        for ny in (-1.0, 0.0, 1.0):
            rect = world.viewport(nx, ny)
            lum = pygame.surfarray.array3d(world.surface.subsurface(rect).copy())
            lum = lum.mean(axis=2).T
            ys, xs = (lum > 200).nonzero()
            assert len(ys) > 0, (nx, ny)
            assert ys.min() >= margin, (nx, ny)
            assert xs.min() >= margin, (nx, ny)
            assert lum.shape[0] - 1 - ys.max() >= margin, (nx, ny)
            assert lum.shape[1] - 1 - xs.max() >= margin, (nx, ny)
