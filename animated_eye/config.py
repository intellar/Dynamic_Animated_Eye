"""Configuration unique de l'application.

Trois sources, dans cet ordre de priorite croissante :
    valeurs par defaut  <  config.json  <  arguments de la ligne de commande
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = PROJECT_ROOT / "assets"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.json"


@dataclass
class Config:
    """Tous les reglages du programme. Les unites sont en px ou en ms."""

    # --- images et pupille ---------------------------------------------------
    # eye4 est l'image de reference : un oeil lumineux sur fond noir, entoure
    # d'une large marge noire. C'est cette marge qui permet un grand debattement
    # sans jamais couper l'oeil. eye2/eye3 restent accessibles (touches 2/3)
    # pour comparer sur la toile.
    images: list[str] = field(
        default_factory=lambda: ["eye4.jpg", "eye2.jpg", "eye3.jpg"]
    )
    # None -> images[0]. C'est l'image qui definit l'echelle commune.
    reference_image: str | None = "eye4.jpg"
    # Indices (dans `images`) de la paire utilisee pour l'animation de pupille.
    pupil_pair: list[int] = field(default_factory=lambda: [0, 1])
    normalize_luma: bool = True
    pupil_switch_chance: float = 0.12
    pupil_fade_ms: float = 150.0
    # Image affichee au demarrage (indice dans `images`).
    start_eye_index: int = 0
    # False -> l'image ne change que sur les touches 1/2.
    pupil_auto: bool = True

    # --- fenetre et projection ----------------------------------------------
    display: int = 0
    width: int = 1920
    height: int = 1080
    fullscreen: bool = True
    # En plein ecran, prendre la resolution native du moniteur cible.
    auto_size: bool = True
    fps: int = 60
    vsync: bool = True

    # --- cadrage -------------------------------------------------------------
    # Diametre de l'iris en fraction de la hauteur de la fenetre. L'image de
    # l'oeil est mise a l'echelle pour que son iris fasse cette taille ; comme
    # elle est carree, elle depasse alors la fenetre et n'en montre qu'une
    # decoupe (ROI).
    # 0.51 avec eye4 (disque lumineux = 25.8 % de son cadre) -> image affichee a
    # ~2136 px : plus grande que l'ecran 1920x1080, donc vraie decoupe (ROI), et
    # l'oeil fait 551 px de haut. Autour, ~790 px de noir dans l'image elle-meme.
    iris_fraction: float = 0.51
    # Amplitude de deplacement de la fenetre, en px, dans chaque direction.
    # L'oeil (551 px) peut parcourir la fenetre sans jamais toucher le bord :
    # 960 - 551/2 = 685 px en horizontal, 540 - 551/2 = 265 px en vertical.
    # On s'arrete juste avant ces limites.
    travel_x: int = 660
    travel_y: int = 250
    # Largeur de la rampe de fondu des bords du patch, en fraction de sa taille.
    feather: float = 0.12

    # --- saccades ------------------------------------------------------------
    fixation_min_ms: float = 250.0
    fixation_max_ms: float = 900.0
    saccade_min_ms: float = 30.0
    saccade_max_ms: float = 60.0
    micro_saccade_chance: float = 0.55
    micro_saccade_max_px: float = 10.0
    drift_px_per_s: float = 6.0
    max_amplitude: float = 1.0
    seed: int | None = None

    # --- divers --------------------------------------------------------------
    debug: bool = False

    # ------------------------------------------------------------------ utils
    def resolve_reference(self) -> str:
        """Nom de l'image de reference (defaut : la premiere)."""
        if self.reference_image and self.reference_image in self.images:
            return self.reference_image
        return self.images[0]

    def reference_index(self) -> int:
        return self.images.index(self.resolve_reference())

    def image_paths(self) -> list[Path]:
        return [ASSETS_DIR / name for name in self.images]

    def validate(self) -> list[str]:
        """Corrige les valeurs aberrantes et renvoie la liste des avertissements."""
        warnings: list[str] = []

        unknown = getattr(self, "_unknown_keys", ())
        if unknown:
            warnings.append(
                "cles inconnues dans la configuration, ignorees : "
                + ", ".join(unknown)
            )

        if not self.images:
            self.images = ["eye2.jpg"]
            warnings.append("aucune image fournie, retour a eye2.jpg")

        if self.reference_image is not None and self.reference_image not in self.images:
            warnings.append(
                f"reference_image {self.reference_image!r} absente de images, "
                "utilisation de la premiere image"
            )
            self.reference_image = None

        if not 0.02 <= self.iris_fraction <= 2.0:
            warnings.append(
                f"iris_fraction {self.iris_fraction} hors bornes, ramene a 0.51"
            )
            self.iris_fraction = 0.51

        if not 0.0 <= self.feather <= 0.45:
            warnings.append(f"feather {self.feather} hors bornes, ramene a 0.12")
            self.feather = 0.12

        if self.travel_x < 0 or self.travel_y < 0:
            warnings.append("travel negatif, ramene a 0")
            self.travel_x = max(0, self.travel_x)
            self.travel_y = max(0, self.travel_y)

        if self.fixation_min_ms > self.fixation_max_ms:
            warnings.append("fixation_min_ms > fixation_max_ms, inversion")
            self.fixation_min_ms, self.fixation_max_ms = (
                self.fixation_max_ms,
                self.fixation_min_ms,
            )

        if self.saccade_min_ms > self.saccade_max_ms:
            warnings.append("saccade_min_ms > saccade_max_ms, inversion")
            self.saccade_min_ms, self.saccade_max_ms = (
                self.saccade_max_ms,
                self.saccade_min_ms,
            )

        pair = [i for i in self.pupil_pair if 0 <= i < len(self.images)]
        if len(set(pair)) != len(pair) or len(pair) < 2:
            warnings.append(
                "pupil_pair invalide (il faut deux indices distincts), "
                "animation de pupille desactivee"
            )
            pair = []
        self.pupil_pair = pair

        if not 0 <= self.start_eye_index < len(self.images):
            warnings.append(
                f"start_eye_index {self.start_eye_index} hors bornes, ramene a 0"
            )
            self.start_eye_index = 0

        if self.fps <= 0:
            warnings.append(f"fps {self.fps} invalide, ramene a 60")
            self.fps = 60

        if self.width <= 0 or self.height <= 0:
            warnings.append("resolution invalide, retour a 1920x1080")
            self.width, self.height = 1920, 1080

        return warnings

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def config_from_dict(data: dict[str, Any]) -> Config:
    """Construit une Config en ignorant les cles inconnues (config.json)."""
    known = {f.name for f in fields(Config)}
    unknown = sorted(set(data) - known)
    kwargs = {k: v for k, v in data.items() if k in known}
    cfg = Config(**kwargs)
    if unknown:
        cfg._unknown_keys = unknown  # type: ignore[attr-defined]
    return cfg


def load_config(path: Path | None = None) -> Config:
    """Charge config.json s'il existe, sinon renvoie les valeurs par defaut."""
    path = DEFAULT_CONFIG_PATH if path is None else path
    if path and path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        return config_from_dict(data)
    return Config()


def save_config(cfg: Config, path: Path | None = None) -> Path:
    path = DEFAULT_CONFIG_PATH if path is None else path
    path.write_text(
        json.dumps(cfg.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def _csv_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _csv_ints(value: str) -> list[int]:
    return [int(item) for item in _csv_list(value)]


def build_parser() -> argparse.ArgumentParser:
    """Chaque option vaut SUPPRESS : seules celles reellement passees ecrasent."""
    parser = argparse.ArgumentParser(
        prog="animated_eye",
        description="Oeil anime projete en plein ecran, avec saccades.",
    )
    parser.add_argument("--config", type=Path, help="chemin d'un config.json")
    parser.add_argument("--list-displays", action="store_true",
                        help="afficher les moniteurs disponibles puis quitter")
    parser.add_argument("--selftest", action="store_true",
                        help="charger les images et rendre quelques frames hors "
                             "ecran, puis quitter (verification apres deploiement)")

    def opt(name: str, **kwargs: Any) -> None:
        parser.add_argument(name, default=argparse.SUPPRESS, **kwargs)

    # images / pupille
    opt("--images", type=_csv_list, metavar="A.jpg,B.jpg",
        help="liste des images d'oeil (defaut : les trois de assets/)")
    opt("--reference-image", dest="reference_image", metavar="NOM",
        help="image qui definit l'echelle commune")
    opt("--pupil-pair", dest="pupil_pair", type=_csv_ints, metavar="I,J",
        help="indices de la paire pour l'animation de pupille (defaut 0,1)")
    opt("--no-normalize", dest="normalize_luma", action="store_false",
        help="desactiver l'egalisation de luminosite entre images")
    opt("--pupil-switch-chance", dest="pupil_switch_chance", type=float,
        metavar="P", help="probabilite de changer de pupille a chaque saccade")
    opt("--pupil-fade-ms", dest="pupil_fade_ms", type=float, metavar="MS",
        help="duree du fondu de pupille")
    opt("--start-eye", dest="start_eye_index", type=int, metavar="N",
        help="indice de l'image affichee au demarrage")
    opt("--no-pupil-auto", dest="pupil_auto", action="store_false",
        help="desactiver l'animation automatique de la pupille")

    # fenetre
    opt("--display", type=int, metavar="N", help="index du moniteur (0 = principal)")
    opt("--width", type=int, metavar="PX")
    opt("--height", type=int, metavar="PX")
    opt("--window", dest="fullscreen", action="store_false",
        help="lancer en fenetre (developpement)")
    opt("--no-auto-size", dest="auto_size", action="store_false",
        help="ne pas prendre la resolution native du moniteur")
    opt("--fps", type=int, metavar="N")
    opt("--no-vsync", dest="vsync", action="store_false")

    # cadrage
    opt("--iris-fraction", dest="iris_fraction", type=float, metavar="F",
        help="diametre de l'iris en fraction de la hauteur (defaut 0.51)")
    opt("--travel-x", dest="travel_x", type=int, metavar="PX")
    opt("--travel-y", dest="travel_y", type=int, metavar="PX")
    opt("--feather", type=float, metavar="F",
        help="largeur du fondu des bords du patch (defaut 0.12)")

    # saccades
    opt("--fixation-min-ms", dest="fixation_min_ms", type=float, metavar="MS")
    opt("--fixation-max-ms", dest="fixation_max_ms", type=float, metavar="MS")
    opt("--saccade-min-ms", dest="saccade_min_ms", type=float, metavar="MS")
    opt("--saccade-max-ms", dest="saccade_max_ms", type=float, metavar="MS")
    opt("--micro-saccade-chance", dest="micro_saccade_chance", type=float,
        metavar="P")
    opt("--micro-saccade-max-px", dest="micro_saccade_max_px", type=float,
        metavar="PX")
    opt("--drift-px-per-s", dest="drift_px_per_s", type=float, metavar="PX")
    opt("--max-amplitude", dest="max_amplitude", type=float, metavar="F")
    opt("--seed", type=int, metavar="N", help="graine aleatoire (reproductible)")

    # divers
    opt("--debug", action="store_true", help="afficher le HUD au demarrage")
    return parser


# Options qui pilotent le programme sans etre des cles de configuration.
_CLI_ONLY = {"config", "list_displays", "selftest"}


def load_from_argv(
    argv: list[str] | None = None,
) -> tuple[Config, argparse.Namespace]:
    """Charge la configuration puis applique les arguments de la ligne de commande.

    `--config` choisit le fichier ; sans lui, `config.json` a la racine du
    projet. Le namespace est renvoye tel quel : `list_displays` et `selftest`
    sont des modes d'execution, pas des reglages.
    """
    ns = build_parser().parse_args(argv)
    cfg = load_config(getattr(ns, "config", None) or DEFAULT_CONFIG_PATH)
    for key, value in vars(ns).items():
        if key in _CLI_ONLY:
            continue
        setattr(cfg, key, value)
    return cfg, ns
