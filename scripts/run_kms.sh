#!/bin/sh
# Lance l'oeil sur l'ecran branche, sans bureau, avec le pilote SDL kmsdrm.
#
# Sur un Pi 4, la carte DRM qui porte les connecteurs HDMI est /dev/dri/card0.
# Sur un Pi 5, c'est /dev/dri/card1 : card0 y est le noeud de rendu v3d, sans
# connecteur. SDL kmsdrm ne prend que card0 quand SDL_VIDEO_KMSDRM_DEVICE n'est
# pas pose, et echoue alors avec « kmsdrm not available » (le programme retombe
# sur le pilote offscreen : ecran noir, aucune erreur visible). On choisit donc
# la carte qui a un connecteur `connected`, ce qui marche sur les deux modeles.
set -eu

APP_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$APP_DIR"

CARD=
for status in /sys/class/drm/card*-*/status; do
    [ -r "$status" ] || continue
    [ "$(cat "$status")" = connected ] || continue
    connector=${status#/sys/class/drm/}
    CARD=/dev/dri/${connector%%-*}
    break
done

if [ -z "$CARD" ]; then
    echo "no display connected: check the HDMI cable" >&2
    exit 1
fi

echo "display detected on $CARD"
export SDL_VIDEODRIVER=kmsdrm
export SDL_VIDEO_KMSDRM_DEVICE="$CARD"
exec .venv/bin/python main.py "$@"
