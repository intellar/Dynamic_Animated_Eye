"""Geometrie de l'affichage : la fenetre est une ROI sur l'image de l'oeil.

Le modele est celui du projecteur :

    * la fenetre affichee fait exactement la taille de l'ecran (1920x1080) ;
    * cette fenetre est un **rectangle d'interet (ROI)** decoupe dans une image
      d'oeil plus grande qu'elle ;
    * deplacer la ROI dans l'image fait donc glisser l'oeil a l'ecran, alors que
      l'image, elle, ne bouge pas.

Consequence directe : l'image de l'oeil doit etre **plus grande que la fenetre**.
L'oeil remplit l'ecran et deborde, on n'en voit qu'une partie, et le noir
n'apparait qu'aux bords quand la ROI sort de l'image.

Le monde (surface noire) doit contenir l'image **et** tout le debattement :
`monde = image + 2 * debattement`. C'est le noir ajoute autour de l'image qui
donne a la ROI la place de sortir de l'oeil.

Ce module ne depend pas de pygame : tout est testable sans ecran.
"""

from __future__ import annotations

# Au-dela, le sprite coute trop cher a construire et a repeindre (et la source
# ne contient de toute facon plus de detail).
MAX_SPRITE_EXTENT = 4096

# Budget memoire du monde : 4 octets par pixel. 24 MP = 96 Mo, deja beaucoup
# pour un Raspberry Pi ; au-dela on reduit le debattement.
MAX_WORLD_PIXELS = 24_000_000

# Ecran pour lequel les reglages de `config.json` sont ecrits. Tout ce qui est
# exprime en fraction (`iris_fraction`, `feather`, `max_amplitude`) suit
# l'ecran de lui-meme ; le debattement, lui, est en pixels et doit etre remis a
# l'echelle (voir `scale_travel`).
REFERENCE_VIEW = (1920, 1080)


# Marge gardee entre l'iris et le bord de la fenetre, en fraction du diametre
# d'iris. Petite : les images n'ont pas le meme iris a l'echelle commune, et
# une marge trop large mangerait le debattement choisi pour l'image par defaut.
EDGE_MARGIN = 0.02


def fit_travel(
    travel_x: int,
    travel_y: int,
    view_w: int,
    view_h: int,
    iris_screen_d: float,
) -> tuple[int, int]:
    """Borne le debattement pour que l'oeil ne morde jamais le bord.

    Le centre de l'oeil peut s'ecarter de `view/2 - iris/2` au maximum avant que
    l'iris ne touche le bord de la fenetre. Sur un ecran 16/9 cale sur 1080p,
    `scale_travel` suffit ; sur un format plus etroit (4/3, 16/10) la marge
    laterale se reduit plus vite que la hauteur et ce garde-fou prend le relais.

    Les images n'ont pas toutes le meme diametre d'iris a l'echelle commune :
    l'oeil le plus large impose le debattement le plus court. Le reste de marge
    (`EDGE_MARGIN`) evite qu'un iris lumineux vienne s'aplatir contre le bord.
    """
    limit = iris_screen_d * (0.5 + EDGE_MARGIN)
    limit_x = max(0, int(round(view_w / 2.0 - limit)))
    limit_y = max(0, int(round(view_h / 2.0 - limit)))
    return min(travel_x, limit_x), min(travel_y, limit_y)


def scale_travel(
    travel_x: int,
    travel_y: int,
    view_w: int,
    view_h: int,
) -> tuple[int, int]:
    """Remet le debattement a l'echelle de l'ecran de projection.

    Les valeurs de `config.json` sont ecrites pour un ecran 1920x1080. Sur un
    projecteur 720p (1280x720), tout doit reduire dans la meme proportion :
    l'iris, le fondu et le debattement. Sans ca, l'oeil sort du cadre.

    On prend le plus petit des deux rapports : c'est la dimension la plus
    contrainte qui commande, donc la marge de securite de la reference est
    conservee sur les ecrans non 16/9.
    """
    ref_w, ref_h = REFERENCE_VIEW
    if view_w <= 0 or view_h <= 0:
        return travel_x, travel_y
    k = min(view_w / ref_w, view_h / ref_h)
    if abs(k - 1.0) < 1e-9:
        return travel_x, travel_y
    return int(round(travel_x * k)), int(round(travel_y * k))


def cap_scale(
    source_size: tuple[int, int],
    desired_scale: float,
    cap: int = MAX_SPRITE_EXTENT,
) -> tuple[float, bool]:
    """Plafonne l'echelle pour que l'image ne depasse pas `cap` pixels de cote.

    Renvoie (echelle retenue, a_ete_plafonnee). L'echelle n'est **jamais**
    reduite pour faire tenir l'oeil dans la fenetre : c'est le contraire qu'on
    veut, la fenetre doit etre une decoupe de l'image.
    """
    src_w, src_h = source_size
    extent = max(src_w, src_h)
    if extent <= 0 or desired_scale <= 0.0:
        return desired_scale, False
    if extent * desired_scale <= cap:
        return desired_scale, False
    return cap / extent, True


def world_size(
    view_w: int,
    view_h: int,
    travel_x: int,
    travel_y: int,
    sprite_size: tuple[int, int],
) -> tuple[int, int]:
    """Taille du monde noir : il contient l'image et tout le debattement."""
    sprite_w, sprite_h = sprite_size
    return (
        max(view_w, sprite_w) + 2 * max(0, travel_x),
        max(view_h, sprite_h) + 2 * max(0, travel_y),
    )


def clamp_travel(
    view_w: int,
    view_h: int,
    travel_x: int,
    travel_y: int,
    sprite_size: tuple[int, int],
    budget: int = MAX_WORLD_PIXELS,
) -> tuple[int, int, bool]:
    """Reduit le debattement si le monde depasserait le budget memoire.

    Renvoie (travel_x, travel_y, a_ete_reduit). Les deux axes sont reduits du
    meme facteur pour conserver la direction des saccades.
    """
    world_w, world_h = world_size(view_w, view_h, travel_x, travel_y, sprite_size)
    if world_w * world_h <= budget:
        return travel_x, travel_y, False

    base_w = max(view_w, sprite_size[0])
    base_h = max(view_h, sprite_size[1])
    low, high = 0.0, 1.0
    for _ in range(40):
        k = (low + high) / 2.0
        w = base_w + 2 * int(travel_x * k)
        h = base_h + 2 * int(travel_y * k)
        if w * h <= budget:
            low = k
        else:
            high = k
    return int(travel_x * low), int(travel_y * low), True


def is_region_of_interest(
    view_w: int, view_h: int, sprite_size: tuple[int, int]
) -> bool:
    """Vrai si la fenetre ne montre qu'une partie de l'image (le but recherche)."""
    return sprite_size[0] > view_w or sprite_size[1] > view_h
