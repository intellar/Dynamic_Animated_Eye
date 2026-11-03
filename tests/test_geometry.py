"""Geometrie pure : plafond d'echelle, taille du monde, budget de debattement."""

from __future__ import annotations

from animated_eye.geometry import (
    MAX_SPRITE_EXTENT,
    MAX_WORLD_PIXELS,
    cap_scale,
    clamp_travel,
    is_region_of_interest,
    world_size,
)

VIEW = (1920, 1080)
TRAVEL = (560, 180)


def test_scale_is_kept_when_under_the_cap():
    scale, capped = cap_scale((2048, 2048), 0.9)
    assert capped is False
    assert scale == 0.9


def test_scale_is_capped_at_the_maximum_extent():
    scale, capped = cap_scale((2048, 2048), 4.0)
    assert capped is True
    assert abs(2048 * scale - MAX_SPRITE_EXTENT) < 1e-6


def test_scale_is_never_reduced_to_fit_the_window():
    """Contraire du modele precedent : l'image doit depasser de la fenetre."""
    scale, capped = cap_scale((2048, 2048), 0.95)
    assert capped is False
    assert scale * 2048 > VIEW[1]


def test_degenerate_scale_is_passed_through():
    assert cap_scale((0, 0), 0.5) == (0.5, False)
    assert cap_scale((2048, 2048), 0.0) == (0.0, False)


def test_world_contains_the_sprite_and_the_travel():
    assert world_size(*VIEW, *TRAVEL, (1978, 1978)) == (
        1978 + 2 * TRAVEL[0],
        1978 + 2 * TRAVEL[1],
    )


def test_world_contains_the_window_when_the_sprite_is_small():
    assert world_size(*VIEW, *TRAVEL, (710, 710)) == (
        VIEW[0] + 2 * TRAVEL[0],
        VIEW[1] + 2 * TRAVEL[1],
    )


def test_world_grows_by_exactly_the_travel():
    small = world_size(*VIEW, *TRAVEL, (1978, 1978))
    bigger = world_size(*VIEW, 0, 0, (1978, 1978))
    assert small[0] - bigger[0] == 2 * TRAVEL[0]
    assert small[1] - bigger[1] == 2 * TRAVEL[1]


def test_travel_is_kept_when_the_world_fits_the_budget():
    tx, ty, reduced = clamp_travel(*VIEW, *TRAVEL, (1978, 1978))
    assert reduced is False
    assert (tx, ty) == TRAVEL


def test_travel_is_reduced_when_the_world_is_too_big():
    huge = (4000, 4000)
    tx, ty, reduced = clamp_travel(*VIEW, 2000, 2000, huge)
    assert reduced is True
    assert tx < 2000 and ty < 2000
    assert world_size(*VIEW, tx, ty, huge)[0] * world_size(*VIEW, tx, ty, huge)[1] <= (
        MAX_WORLD_PIXELS
    )


def test_travel_reduction_preserves_the_direction():
    huge = (4000, 4000)
    tx, ty, reduced = clamp_travel(*VIEW, 800, 400, huge)
    assert reduced is True
    assert abs((tx / ty) - 2.0) < 0.05


def test_travel_reduction_can_go_to_zero():
    """Meme sans debattement le monde reste trop gros : on annule le mouvement."""
    tx, ty, reduced = clamp_travel(*VIEW, 10, 10, (5000, 5000))
    assert reduced is True
    assert tx == 0 and ty == 0


def test_region_of_interest_detects_an_image_bigger_than_the_window():
    assert is_region_of_interest(*VIEW, (1978, 1978)) is True
    assert is_region_of_interest(*VIEW, (1921, 1080)) is True
    assert is_region_of_interest(*VIEW, (1920, 1080)) is False
    assert is_region_of_interest(*VIEW, (710, 710)) is False
