"""Verifications du generateur de saccades."""

from __future__ import annotations

import math
import random

import pytest

from animated_eye.config import Config
from animated_eye.saccade import Phase, SaccadeController, minimum_jerk

DT = 1.0 / 60.0


def _run(cfg: Config, seconds: float, seed: int = 3) -> list[tuple[float, float]]:
    ctrl = SaccadeController(cfg, random.Random(seed))
    trace = []
    for _ in range(int(seconds / DT)):
        ctrl.update(DT)
        trace.append(tuple(ctrl.pos))
    return trace


def test_minimum_jerk_starts_and_ends_at_rest():
    assert minimum_jerk(0.0) == pytest.approx(0.0)
    assert minimum_jerk(1.0) == pytest.approx(1.0)


def test_minimum_jerk_is_monotonic():
    values = [minimum_jerk(i / 200) for i in range(201)]
    assert all(b >= a - 1e-12 for a, b in zip(values, values[1:]))


def test_minimum_jerk_is_symmetric_around_the_middle():
    for t in (0.1, 0.25, 0.4):
        assert minimum_jerk(t) + minimum_jerk(1.0 - t) == pytest.approx(1.0)


def test_minimum_jerk_is_clamped_outside_the_interval():
    assert minimum_jerk(-3.0) == 0.0
    assert minimum_jerk(4.0) == 1.0


def test_position_stays_normalized():
    for x, y in _run(Config(), 30.0):
        assert -1.0 <= x <= 1.0
        assert -1.0 <= y <= 1.0
        assert not math.isnan(x) and not math.isnan(y)


def test_position_never_jumps():
    """Deux frames consecutives ne doivent pas sauter plus loin que le debattement."""
    cfg = Config()
    trace = _run(cfg, 20.0)
    max_step = 0.0
    for (ax, ay), (bx, by) in zip(trace, trace[1:]):
        max_step = max(max_step, math.hypot(bx - ax, by - ay))
    # une saccade complete en 30 ms a 60 fps = 2 frames, donc jusqu'a ~2 unites
    assert max_step <= 2.0


def test_saccade_durations_respect_the_configured_range():
    cfg = Config()
    ctrl = SaccadeController(cfg, random.Random(11))
    durations = []
    for _ in range(60 * 120):
        ctrl.update(DT)
        if ctrl.saccade_started:
            durations.append(ctrl.duration_ms)
    assert durations
    assert min(durations) >= cfg.saccade_min_ms - 1e-6
    assert max(durations) <= cfg.saccade_max_ms + 1e-6


def test_larger_saccades_last_longer():
    cfg = Config()
    ctrl = SaccadeController(cfg, random.Random(5))
    small = ctrl.saccade_duration(0.05, 0.0)
    large = ctrl.saccade_duration(1.0, 0.0)
    assert large > small


def test_amplitude_stays_within_two_travels():
    """Une saccade relie deux points du disque : au pire un diametre."""
    cfg = Config()
    ctrl = SaccadeController(cfg, random.Random(23))
    max_px = math.hypot(cfg.travel_x, cfg.travel_y)
    for _ in range(60 * 120):
        ctrl.update(DT)
        if ctrl.saccade_started:
            assert ctrl.saccade_amplitude_px <= 2 * max_px + 1e-6


def test_small_saccades_are_the_most_common():
    cfg = Config()
    ctrl = SaccadeController(cfg, random.Random(31))
    max_px = math.hypot(cfg.travel_x, cfg.travel_y)
    amplitudes = []
    for _ in range(60 * 300):
        ctrl.update(DT)
        if ctrl.saccade_started:
            amplitudes.append(ctrl.saccade_amplitude_px)
    assert amplitudes
    amplitudes.sort()
    median = amplitudes[len(amplitudes) // 2]
    assert median < 0.6 * 2 * max_px


def test_the_eye_spends_most_of_its_time_fixating():
    cfg = Config()
    ctrl = SaccadeController(cfg, random.Random(2))
    fixations = 0
    frames = 60 * 60
    for _ in range(frames):
        ctrl.update(DT)
        if ctrl.phase is Phase.FIXATION:
            fixations += 1
    assert fixations / frames > 0.85


def test_there_are_several_saccades_per_second():
    cfg = Config()
    ctrl = SaccadeController(cfg, random.Random(4))
    count = 0
    for _ in range(60 * 30):
        ctrl.update(DT)
        if ctrl.saccade_started:
            count += 1
    assert 0.8 <= count / 30.0 <= 4.0


def test_force_saccade_moves_the_eye():
    cfg = Config()
    ctrl = SaccadeController(cfg, random.Random(9))
    before = tuple(ctrl.pos)
    ctrl.force_saccade()
    for _ in range(6):
        ctrl.update(DT)
    assert tuple(ctrl.pos) != before


def test_look_at_reaches_the_target():
    cfg = Config()
    ctrl = SaccadeController(cfg, random.Random(1))
    ctrl.look_at(0.8, -0.6)
    for _ in range(10):
        ctrl.update(DT)
    assert ctrl.pos[0] == pytest.approx(0.8, abs=0.02)
    assert ctrl.pos[1] == pytest.approx(-0.6, abs=0.02)


def test_zero_dt_does_nothing():
    cfg = Config()
    ctrl = SaccadeController(cfg, random.Random(6))
    before = (tuple(ctrl.pos), ctrl.phase)
    ctrl.update(0.0)
    assert (tuple(ctrl.pos), ctrl.phase) == before


def test_seed_makes_the_motion_reproducible():
    a = _run(Config(), 10.0, seed=42)
    b = _run(Config(), 10.0, seed=42)
    c = _run(Config(), 10.0, seed=43)
    assert a == b
    assert a != c
