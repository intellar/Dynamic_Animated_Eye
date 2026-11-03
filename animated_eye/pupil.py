"""Gestion de l'etat de la pupille.

Les images en service (`eye4`, `eye2`, `eye3`) sont des rendus differents du meme
oeil. On les fait alterner de temps en temps pour que l'oeil paraisse vivant.

Mais un fondu n'est acceptable que si les deux images sont photometriquement
proches. On mesure cet ecart au chargement (`EyeSet.residual`) : si les images
divergent trop — c'est le cas de toutes les paires ici, 48 a 230/255 — on
remplace le fondu par une coupe franche pendant une saccade. Le cerveau ne voit
pas les changements qui ont lieu pendant un mouvement oculaire (suppression
saccadique).
"""

from __future__ import annotations

import random

import pygame

from .config import Config
from .eye_image import EyeSet

FADE_THRESHOLD = 15.0


class PupilState:
    def __init__(self, eyes: EyeSet, cfg: Config, rng: random.Random | None = None) -> None:
        self.eyes = eyes
        self.cfg = cfg
        self.rng = rng if rng is not None else random.Random(
            None if cfg.seed is None else cfg.seed + 1
        )

        count = len(eyes)
        self.index = min(max(cfg.start_eye_index, 0), count - 1)
        self.previous = self.index
        self.auto = cfg.pupil_auto

        self._fade_t = 0.0
        self._fade_duration = 0.0
        self.warnings: list[str] = []

        pair = [i for i in cfg.pupil_pair if 0 <= i < count]
        self.pair = pair if len(pair) >= 2 else [self.index]
        self._check_pair()

    # ------------------------------------------------------------------ setup
    def _check_pair(self) -> None:
        if len(self.pair) < 2:
            return
        residual = self.eyes.residual(self.pair[0], self.pair[1])
        if residual is None:
            return
        if residual > FADE_THRESHOLD:
            self.warnings.append(
                f"pupil_pair {self.pair} : ecart photometrique {residual:.1f}/255 > "
                f"{FADE_THRESHOLD:.0f}, fondu desactive (coupe pendant les saccades)"
            )
            self.pair = self.pair[:1]

    def _can_fade(self, a: int, b: int) -> bool:
        if self.cfg.pupil_fade_ms <= 0:
            return False
        residual = self.eyes.residual(a, b)
        return residual is None or residual <= FADE_THRESHOLD

    # ------------------------------------------------------------------ etats
    @property
    def fading(self) -> bool:
        return self._fade_duration > 0.0 and self._fade_t < self._fade_duration

    @property
    def fade_alpha(self) -> int:
        """Opacite (0-255) de l'image cible par-dessus l'image precedente."""
        if not self.fading:
            return 255 if self.previous != self.index else 0
        u = self._fade_t / self._fade_duration
        # lissage : evite une transition qui demarre trop brutalement
        u = u * u * (3.0 - 2.0 * u)
        return int(round(255.0 * min(1.0, max(0.0, u))))

    def blend(self) -> tuple[pygame.Surface, pygame.Surface | None, int]:
        """(image de fond, image en surimpression, opacite) pour le rendu."""
        base = self.eyes[self.previous].surface
        if not self.fading or self.previous == self.index:
            return self.eyes[self.index].surface, None, 0
        return base, self.eyes[self.index].surface, self.fade_alpha

    # --------------------------------------------------------------- actions
    def _switch_to(self, index: int, fade: bool) -> None:
        if index == self.index:
            return
        self.previous = self.index if fade else index
        self.index = index
        if fade:
            self._fade_t = 0.0
            self._fade_duration = self.cfg.pupil_fade_ms / 1000.0
        else:
            self._fade_t = 0.0
            self._fade_duration = 0.0

    def set_state(self, index: int) -> None:
        """Changement manuel (touches 1..9, Espace).

        Un choix manuel coupe l'animation automatique : sans ca, la saccade
        suivante pourrait ramener une autre image et contredire l'utilisateur.
        `P` la rallume.
        """
        index = min(max(index, 0), len(self.eyes) - 1)
        if index == self.index:
            return
        self.auto = False
        self._switch_to(index, fade=self._can_fade(self.index, index))

    def cycle(self) -> int:
        """Image suivante, en bouclant. Renvoie le nouvel index."""
        self.set_state((self.index + 1) % len(self.eyes))
        return self.index

    def toggle_auto(self) -> bool:
        self.auto = not self.auto
        return self.auto

    def on_saccade(self) -> None:
        """Appele au demarrage d'une saccade : peut declencher un changement."""
        if not self.auto or len(self.pair) < 2:
            return
        if self.index not in self.pair:
            return
        if self.rng.random() >= self.cfg.pupil_switch_chance:
            return
        target = self.pair[(self.pair.index(self.index) + 1) % len(self.pair)]
        self._switch_to(target, fade=self._can_fade(self.index, target))

    # ------------------------------------------------------------------ update
    def update(self, dt: float) -> None:
        if not self.fading:
            return
        self._fade_t += dt
        if self._fade_t >= self._fade_duration:
            self._fade_t = self._fade_duration
            self._fade_duration = 0.0
            self.previous = self.index
