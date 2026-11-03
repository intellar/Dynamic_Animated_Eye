"""Generateur de saccades.

Une vraie saccade n'est pas un glissement lineaire : c'est un mouvement
balistique de 30 a 60 ms, dont la duree augmente avec l'amplitude (« main
sequence »), et dont le profil de vitesse est asymetrique. On utilise le profil
**minimum-jerk**, qui est le modele classique du mouvement humain :

    s(t) = 10t^3 - 15t^4 + 6t^5

Entre deux saccades, l'oeil ne reste pas parfaitement immobile : il derive
lentement (Troxler drift) et fait de temps en temps de micro-saccades de
quelques pixels. C'est ce qui evite l'aspect « robot » d'un oeil fige.

La sortie est normalisee dans [-1, 1] : le controleur ne connait ni l'ecran ni
les pixels, ce qui le rend testable sans affichage.
"""

from __future__ import annotations

import math
import random
from enum import Enum

from .config import Config


class Phase(str, Enum):
    FIXATION = "fixation"
    SACCADE = "saccade"


def minimum_jerk(t: float) -> float:
    """Profil de position 0 -> 1, vitesse nulle aux deux bouts."""
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return t * t * t * (10.0 + t * (-15.0 + 6.0 * t))


def _clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return low if value < low else (high if value > high else value)


class SaccadeController:
    """Machine a etats FIXATION / SACCADE pilotee par le temps."""

    def __init__(self, cfg: Config, rng: random.Random | None = None) -> None:
        self.cfg = cfg
        self.rng = rng if rng is not None else random.Random(cfg.seed)

        self.pos: list[float] = [0.0, 0.0]
        self.phase: Phase = Phase.FIXATION
        self.saccade_started: bool = False
        self.saccade_amplitude_px: float = 0.0

        self._t = 0.0
        self._duration = self._draw_fixation_duration()
        self._hold: list[float] = [0.0, 0.0]
        self._drift: list[float] = [0.0, 0.0]
        self._seg_start: list[float] = [0.0, 0.0]
        self._seg_end: list[float] = [0.0, 0.0]
        self._resume_fixation: float = 0.0
        self._micro_times: list[float] = self._schedule_micro_saccades(self._duration)

    # ------------------------------------------------------------------ etats
    @property
    def progress(self) -> float:
        if self._duration <= 0.0:
            return 1.0
        return min(1.0, self._t / self._duration)

    @property
    def fixation_remaining_ms(self) -> float:
        if self.phase is not Phase.FIXATION:
            return 0.0
        return max(0.0, (self._duration - self._t) * 1000.0)

    # ---------------------------------------------------------------- tirage
    def _draw_fixation_duration(self) -> float:
        """Duree de fixation en secondes, tirage log-normal borne."""
        low = self.cfg.fixation_min_ms / 1000.0
        high = self.cfg.fixation_max_ms / 1000.0
        if high <= low:
            return low
        median = math.sqrt(low * high)
        sigma = 0.35
        value = self.rng.lognormvariate(math.log(median), sigma)
        return min(max(value, low), high)

    def _schedule_micro_saccades(self, duration: float) -> list[float]:
        """Instants (relatifs a la fixation) des micro-saccades a venir."""
        times: list[float] = []
        chance = self.cfg.micro_saccade_chance
        while len(times) < 3 and self.rng.random() < chance:
            times.append(self.rng.uniform(0.15, 0.85) * duration)
        times.sort()
        return times

    def _draw_target(self) -> tuple[float, float]:
        """Point de visee dans le disque de deplacement.

        Rayon biaise vers les petites amplitudes (beaucoup de petits coups d'oeil,
        quelques grands balayages), direction uniforme.
        """
        amplitude = self.cfg.max_amplitude * (self.rng.random() ** 1.7)
        theta = self.rng.uniform(0.0, 2.0 * math.pi)
        return (
            _clamp(amplitude * math.cos(theta)),
            _clamp(amplitude * math.sin(theta)),
        )

    def _saccade_duration(self, dx: float, dy: float) -> float:
        """Duree en secondes : croissante avec l'amplitude en pixels."""
        amp_px = math.hypot(dx * self.cfg.travel_x, dy * self.cfg.travel_y)
        max_px = max(math.hypot(self.cfg.travel_x, self.cfg.travel_y), 1.0)
        frac = min(1.0, amp_px / max_px)
        low = self.cfg.saccade_min_ms / 1000.0
        high = self.cfg.saccade_max_ms / 1000.0
        return low + (high - low) * math.sqrt(frac)

    # --------------------------------------------------------------- actions
    def _begin_saccade(
        self, target: tuple[float, float], resume_fixation: float, duration: float | None = None
    ) -> None:
        self._seg_start = list(self.pos)
        self._seg_end = [_clamp(target[0]), _clamp(target[1])]
        dx = self._seg_end[0] - self._seg_start[0]
        dy = self._seg_end[1] - self._seg_start[1]
        self._duration = (
            duration if duration is not None else self._saccade_duration(dx, dy)
        )
        self._duration = max(self._duration, 0.001)
        self._resume_fixation = resume_fixation
        self._t = 0.0
        self.phase = Phase.SACCADE
        self.saccade_amplitude_px = math.hypot(
            dx * self.cfg.travel_x, dy * self.cfg.travel_y
        )
        self.saccade_started = True

    def force_saccade(self) -> None:
        """Demarre immediatement une saccade vers un nouveau point de visee."""
        if self.phase is Phase.SACCADE:
            return
        self._begin_saccade(self._draw_target(), resume_fixation=0.0)

    def look_at(self, nx: float, ny: float) -> None:
        """Vise un point donne (prevu pour un futur suivi de cible)."""
        self._begin_saccade((nx, ny), resume_fixation=0.0)

    def _start_micro_saccade(self) -> None:
        scale = max(self.cfg.travel_x, 1)
        radius = self.cfg.micro_saccade_max_px / scale
        theta = self.rng.uniform(0.0, 2.0 * math.pi)
        magnitude = radius * math.sqrt(self.rng.random())
        target = (
            _clamp(self._hold[0] + self._drift[0] + magnitude * math.cos(theta)),
            _clamp(self._hold[1] + self._drift[1] + magnitude * math.sin(theta)),
        )
        duration = self.rng.uniform(0.018, 0.030)
        self._begin_saccade(
            target, resume_fixation=max(0.0, self._duration - self._t), duration=duration
        )
        self.saccade_started = False  # une micro-saccade ne declenche pas de pupille

    # ------------------------------------------------------------------ update
    def update(self, dt: float) -> None:
        if dt <= 0.0:
            return
        self.saccade_started = False

        if self.phase is Phase.FIXATION:
            self._update_fixation(dt)
        else:
            self._update_saccade(dt)

        self.pos[0] = _clamp(self.pos[0])
        self.pos[1] = _clamp(self.pos[1])

    def _update_fixation(self, dt: float) -> None:
        self._t += dt

        # Derive de Troxler : marche aleatoire a rappel, quelques px/s.
        sigma = self.cfg.drift_px_per_s / max(self.cfg.travel_x, 1)
        decay = math.exp(-dt / 0.35)
        self._drift[0] = self._drift[0] * decay + self.rng.gauss(0.0, sigma * math.sqrt(dt))
        self._drift[1] = self._drift[1] * decay + self.rng.gauss(0.0, sigma * math.sqrt(dt))

        self.pos[0] = _clamp(self._hold[0] + self._drift[0])
        self.pos[1] = _clamp(self._hold[1] + self._drift[1])

        if self._micro_times and self._t >= self._micro_times[0]:
            self._micro_times.pop(0)
            self._start_micro_saccade()
            return

        if self._t >= self._duration:
            self._begin_saccade(self._draw_target(), resume_fixation=0.0)

    def _update_saccade(self, dt: float) -> None:
        self._t += dt
        u = self.progress
        s = minimum_jerk(u)
        self.pos[0] = self._seg_start[0] + (self._seg_end[0] - self._seg_start[0]) * s
        self.pos[1] = self._seg_start[1] + (self._seg_end[1] - self._seg_start[1]) * s

        if u >= 1.0:
            self._hold = list(self._seg_end)
            self._drift = [0.0, 0.0]
            self.phase = Phase.FIXATION
            self._t = 0.0
            self._duration = (
                self._resume_fixation
                if self._resume_fixation > 0.0
                else self._draw_fixation_duration()
            )
            self._duration = max(self._duration, 0.05)
            self._micro_times = self._schedule_micro_saccades(self._duration)
