"""Chargement des images d'oeil et fabrication des sprites.

Pipeline, une seule fois au demarrage :

1. lecture de l'image source (n'importe quelle resolution) ;
2. mesure du rayon de l'iris par profil radial (minimum du limbe) ;
3. egalisation de luminosite sur la bande de selere (pour que les changements
   d'etat ne fassent pas varier la brillance de l'oeil) ;
4. reduction a l'echelle commune calibree sur l'image de reference ;
5. masque alpha a bords fondus, pour que le patch carre disparaisse dans le noir.

Rien de tout cela n'est refait par frame : les sprites sont precalcules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pygame
from PIL import Image

from .config import Config
from .geometry import cap_scale

# Bornes de securite pour la mesure de l'iris, en fraction du demi-cote.
_IRIS_MIN_FRAC = 0.05
_IRIS_MAX_FRAC = 0.48
_IRIS_FALLBACK_FRAC = 0.30

# En dessous de ce niveau, la couronne a 0.55-0.80 du rayon est noire : l'image
# n'est pas un gros plan (pas de selere) mais un oeil lumineux sur fond noir.
_DARK_FIELD_LEVEL = 40.0
_DARK_FIELD_PEAK = 25.0
_DARK_FIELD_EDGE = 0.25


# --------------------------------------------------------------------------- #
# Mesure de l'iris
# --------------------------------------------------------------------------- #
def _radial_profile(gray: np.ndarray, step: int = 2):
    """Luminance moyenne par couronne de rayon `step`, depuis le centre."""
    h, w = gray.shape
    cy, cx = (h - 1) / 2.0, (w - 1) / 2.0
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.hypot(xx - cx, yy - cy)
    rmax = min(h, w) / 2.0
    nbins = int(rmax / step) + 1
    bins = np.minimum((r / step).astype(np.int32), nbins - 1)
    keep = r < rmax
    sums = np.bincount(bins[keep], weights=gray[keep], minlength=nbins)
    counts = np.bincount(bins[keep], minlength=nbins)
    prof = sums / np.maximum(counts, 1)
    radii = np.arange(nbins, dtype=np.float64) * step
    return prof, radii, rmax


def _smooth(values: np.ndarray, kernel: int = 5) -> np.ndarray:
    if kernel <= 1 or values.size < kernel:
        return values
    window = np.ones(kernel, dtype=np.float64) / kernel
    return np.convolve(values, window, mode="same")


@dataclass
class IrisMeasurement:
    iris_radius: float
    pupil_radius: float
    limbus_radius: float
    sclera_level: float
    profile: np.ndarray = field(repr=False)
    radii: np.ndarray = field(repr=False)
    rmax: float = 0.0

    @property
    def iris_diameter(self) -> float:
        return 2.0 * self.iris_radius

    @property
    def iris_fraction(self) -> float:
        return self.iris_diameter / (2.0 * self.rmax)


def measure_iris(rgb: np.ndarray) -> IrisMeasurement:
    """Rayon de l'iris, en pixels source.

    Deux familles d'images :

    - **gros plan** (`eye2`, `eye3`) : la selere touche les bords. On part de son
      plateau lumineux a mi-rayon, on descend vers la pupille, et le bord de
      l'iris est le premier rayon qui repasse au-dessus du milieu entre le minimum
      du limbe et la selere.
    - **oeil lumineux sur fond noir** (`eye4`) : il n'y a pas de selere, la
      couronne exterieure est noire. On mesure alors le disque lumineux, du pic
      radial vers l'exterieur jusqu'a ce que le profil retombe.
    """
    gray = rgb.mean(axis=2).astype(np.float64)
    prof, radii, rmax = _radial_profile(gray)
    prof_s = _smooth(prof, 5)

    sclera_level = float(
        np.median(prof_s[(radii > 0.55 * rmax) & (radii < 0.80 * rmax)])
    )
    fallback = _IRIS_FALLBACK_FRAC * rmax
    if sclera_level <= 1.0:
        return IrisMeasurement(fallback, 0.0, 0.0, sclera_level, prof_s, radii, rmax)

    if sclera_level < _DARK_FIELD_LEVEL:
        return _measure_dark_field(prof_s, radii, rmax, sclera_level)

    # Bord de la pupille : premier rayon ou l'on sort franchement du noir.
    above = np.flatnonzero(prof_s > 0.25 * sclera_level)
    pupil_radius = float(radii[above[0]]) if above.size else 0.0

    # Limbe : minimum local entre la pupille et la moitie du rayon.
    lo = max(pupil_radius * 1.2, 0.0)
    hi = 0.50 * rmax
    window = (radii >= lo) & (radii <= hi)
    if not window.any():
        window = (radii >= 0.10 * rmax) & (radii <= hi)
    if not window.any():
        return IrisMeasurement(fallback, pupil_radius, 0.0, sclera_level, prof_s, radii, rmax)

    masked = np.where(window, prof_s, np.inf)
    limbus_idx = int(np.argmin(masked))
    limbus_radius = float(radii[limbus_idx])
    limbus_value = float(prof_s[limbus_idx])

    # Bord de l'iris : on remonte au-dessus du milieu limbe/selere.
    midpoint = 0.5 * (limbus_value + sclera_level)
    beyond = np.flatnonzero((radii > limbus_radius) & (prof_s > midpoint))
    iris_radius = float(radii[beyond[0]]) if beyond.size else fallback

    if not (_IRIS_MIN_FRAC * rmax < iris_radius < _IRIS_MAX_FRAC * rmax):
        iris_radius = fallback

    return IrisMeasurement(
        iris_radius, pupil_radius, limbus_radius, sclera_level, prof_s, radii, rmax
    )


def _measure_dark_field(
    prof: np.ndarray, radii: np.ndarray, rmax: float, sclera_level: float
) -> IrisMeasurement:
    """Disque lumineux d'un oeil sur fond noir : du pic radial vers l'exterieur."""
    fallback = _IRIS_FALLBACK_FRAC * rmax
    peak = float(prof.max())
    if peak < _DARK_FIELD_PEAK:
        return IrisMeasurement(fallback, 0.0, 0.0, sclera_level, prof, radii, rmax)

    peak_idx = int(np.argmax(prof))
    # Bord de la pupille : premier rayon ou le centre sombre s'eclaire.
    lit = np.flatnonzero(prof > _DARK_FIELD_EDGE * peak)
    pupil_radius = float(radii[lit[0]]) if lit.size else 0.0

    # Bord de l'iris : premiere fois que le profil retombe apres le pic.
    outer = np.flatnonzero((radii > radii[peak_idx]) & (prof < _DARK_FIELD_EDGE * peak))
    iris_radius = float(radii[outer[0]]) if outer.size else fallback
    if not (_IRIS_MIN_FRAC * rmax < iris_radius < _IRIS_MAX_FRAC * rmax):
        iris_radius = fallback

    return IrisMeasurement(iris_radius, pupil_radius, 0.0, sclera_level, prof, radii, rmax)


def sclera_band(shape: tuple[int, int]) -> np.ndarray:
    """Masque booléen de la couronne de selere, hors iris et hors bords."""
    h, w = shape
    cy, cx = (h - 1) / 2.0, (w - 1) / 2.0
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.hypot(xx - cx, yy - cy)
    rmax = min(h, w) / 2.0
    return (r > 0.55 * rmax) & (r < 0.80 * rmax)


# --------------------------------------------------------------------------- #
# Egalisation de luminosite
# --------------------------------------------------------------------------- #
def photometric_gain(rgb: np.ndarray, ref_rgb: np.ndarray, band: np.ndarray) -> np.ndarray:
    """Gain par canal qui aligne la selere de `rgb` sur celle de `ref_rgb`.

    Sans objet quand l'image de reference n'a pas de selere (oeil lumineux sur
    fond noir) : il n'y a alors rien a aligner, et un gain calcule sur du noir
    eteindrait les autres images. Les gains restent a 1.
    """
    gains = np.ones(3, dtype=np.float32)
    for channel in range(3):
        target = float(ref_rgb[..., channel][band].mean())
        current = float(rgb[..., channel][band].mean())
        if target > _DARK_FIELD_LEVEL and current > 1.0:
            gains[channel] = target / current
    return np.clip(gains, 0.25, 4.0)


def photometric_residual(
    rgb_a: np.ndarray,
    rgb_b: np.ndarray,
    band: np.ndarray,
    gain_b: np.ndarray,
) -> float:
    """Ecart moyen (0-255) entre deux images sur la selere, apres gain."""
    a = rgb_a[band].astype(np.float32)
    b = np.clip(rgb_b[band].astype(np.float32) * gain_b, 0.0, 255.0)
    return float(np.abs(a - b).mean())


def apply_gain(rgb: np.ndarray, gain: np.ndarray) -> np.ndarray:
    if np.allclose(gain, 1.0):
        return rgb
    return np.clip(rgb.astype(np.float32) * gain, 0.0, 255.0).astype(np.uint8)


# --------------------------------------------------------------------------- #
# Masque alpha a bords fondus
# --------------------------------------------------------------------------- #
def _smoothstep(t: np.ndarray) -> np.ndarray:
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def feather_alpha(width: int, height: int, feather: float) -> np.ndarray:
    """Alpha flottant 0..1, en fondu depuis les quatre bords.

    Le produit des quatre rampes donne des coins arrondis : sur un bord, une seule
    rampe agit ; dans un coin, deux rampes se multiplient.
    """
    if feather <= 0.0:
        return np.ones((height, width), dtype=np.float32)

    band_x = max(1.0, feather * width)
    band_y = max(1.0, feather * height)

    x = np.arange(width, dtype=np.float32)
    y = np.arange(height, dtype=np.float32)
    ramp_x0 = _smoothstep(x / band_x)
    ramp_x1 = _smoothstep((width - 1 - x) / band_x)
    ramp_y0 = _smoothstep(y / band_y)
    ramp_y1 = _smoothstep((height - 1 - y) / band_y)

    return (
        ramp_x0[None, :] * ramp_x1[None, :] * ramp_y0[:, None] * ramp_y1[:, None]
    ).astype(np.float32)


def _to_surface(rgb: np.ndarray, alpha: np.ndarray) -> pygame.Surface:
    h, w = rgb.shape[:2]
    rgba = np.dstack([rgb, (alpha * 255.0).astype(np.uint8)])
    rgba = np.ascontiguousarray(rgba)
    surface = pygame.image.frombuffer(rgba.tobytes(), (w, h), "RGBA")
    return surface.copy()


def build_sprite(rgb: np.ndarray, scale: float, feather: float) -> pygame.Surface:
    """Reduit l'image et applique le masque a bords fondus."""
    h, w = rgb.shape[:2]
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    resized = np.asarray(
        Image.fromarray(rgb).resize((new_w, new_h), Image.LANCZOS)
    )
    alpha = feather_alpha(new_w, new_h, feather)
    return _to_surface(resized, alpha)


# --------------------------------------------------------------------------- #
# Chargement
# --------------------------------------------------------------------------- #
@dataclass
class EyeSprite:
    name: str
    path: Path
    source_size: tuple[int, int]
    measurement: IrisMeasurement
    sclera_level: float
    gain: np.ndarray
    scale: float
    surface: pygame.Surface

    @property
    def iris_diameter_screen(self) -> float:
        return self.measurement.iris_diameter * self.scale

    @property
    def size(self) -> tuple[int, int]:
        return self.surface.get_size()


@dataclass
class EyeSet:
    """Les sprites charges + de quoi verifier qu'ils sont melangeables."""

    sprites: list[EyeSprite]
    reference_index: int
    scale: float
    residuals: dict[tuple[int, int], float] = field(default_factory=dict)
    # Taille de l'oeil plafonnee a MAX_SPRITE_EXTENT (jamais reduite pour tenir
    # dans la fenetre : c'est le contraire qui est recherche).
    scale_capped: bool = False
    requested_scale: float = 0.0

    def __len__(self) -> int:
        return len(self.sprites)

    def __getitem__(self, index: int) -> EyeSprite:
        return self.sprites[index]

    def residual(self, i: int, j: int) -> float | None:
        if i == j:
            return 0.0
        return self.residuals.get((min(i, j), max(i, j)))


def load_eyes(cfg: Config, view_size: tuple[int, int] | int) -> EyeSet:
    """Charge toutes les images, les met a la meme echelle et fabrique les sprites.

    `view_size` peut etre la hauteur seule ou (largeur, hauteur). L'echelle est
    deduite de `iris_fraction` : l'image de l'oeil est volontairement **plus
    grande** que la fenetre, qui n'en montre qu'une decoupe (ROI).
    """
    if isinstance(view_size, int):
        view_w, view_h = cfg.width, view_size
    else:
        view_w, view_h = view_size

    paths = cfg.image_paths()
    missing = [str(p) for p in paths if not p.exists()]
    if missing:
        raise FileNotFoundError(
            "images introuvables : " + ", ".join(missing)
        )

    sources = [np.asarray(Image.open(p).convert("RGB")) for p in paths]
    measurements = [measure_iris(src) for src in sources]

    ref_index = cfg.reference_index()
    ref_measure = measurements[ref_index]
    if ref_measure.iris_radius <= 0.0:
        raise ValueError(
            f"impossible de mesurer l'iris dans {paths[ref_index].name}"
        )

    src_h, src_w = sources[ref_index].shape[:2]
    desired = (cfg.iris_fraction * view_h) / ref_measure.iris_diameter
    scale, reduced = cap_scale((src_w, src_h), desired)
    ref_src = sources[ref_index]
    band = sclera_band(ref_src.shape[:2])

    gains: list[np.ndarray] = []
    for index, src in enumerate(sources):
        if index == ref_index or not cfg.normalize_luma:
            gains.append(np.ones(3, dtype=np.float32))
        else:
            gains.append(photometric_gain(src, ref_src, band))

    residuals: dict[tuple[int, int], float] = {}
    for i in range(len(sources)):
        for j in range(i + 1, len(sources)):
            residuals[(i, j)] = photometric_residual(
                sources[i], sources[j], band, gains[j]
            )

    sprites: list[EyeSprite] = []
    for index, (path, src, measure, gain) in enumerate(
        zip(paths, sources, measurements, gains)
    ):
        normalized = apply_gain(src, gain)
        surface = build_sprite(normalized, scale, cfg.feather)
        sprites.append(
            EyeSprite(
                name=path.stem,
                path=path,
                source_size=(src.shape[1], src.shape[0]),
                measurement=measure,
                sclera_level=measure.sclera_level,
                gain=gain,
                scale=scale,
                surface=surface,
            )
        )

    return EyeSet(
        sprites=sprites,
        reference_index=ref_index,
        scale=scale,
        residuals=residuals,
        scale_capped=reduced,
        requested_scale=desired,
    )
