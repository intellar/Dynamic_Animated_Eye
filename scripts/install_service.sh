#!/bin/sh
# Installe et active le service systemd qui lance l'oeil au demarrage du Pi.
#
#   sudo sh scripts/install_service.sh           # installe, active, redemarre
#   sudo sh scripts/install_service.sh --remove  # arrete et desinstalle
#
# Le gabarit n'est pas recopie tel quel : @USER@ et @APP_DIR@ sont remplaces par
# l'utilisateur qui a lance sudo et par le dossier reel du projet. Rien n'est
# code en dur, donc le meme script marche pour n'importe quel compte (`pi`,
# `ubuntu`, ...), et quel que soit l'emplacement du depot sur le Pi.
set -eu

UNIT=animated-eye.service
APP_DIR=$(cd "$(dirname "$0")/.." && pwd)

if [ "$(id -u)" -ne 0 ]; then
    echo "run it with sudo: sudo sh $APP_DIR/scripts/install_service.sh" >&2
    exit 1
fi

if [ "${1:-}" = "--remove" ]; then
    systemctl disable --now "$UNIT" 2>/dev/null || true
    rm -f "/etc/systemd/system/$UNIT"
    systemctl daemon-reload
    echo "service $UNIT removed"
    exit 0
fi

RUN_USER=${SUDO_USER:-$(id -un)}
if [ "$RUN_USER" = root ]; then
    echo "cannot guess the account: run sudo from the Pi user account" >&2
    exit 1
fi

# `s/\r$//` au cas ou le fichier aurait garde des fins de ligne Windows :
# systemd ne sait pas lire une directive suivie d'un CR.
sed -e "s|@USER@|$RUN_USER|g" \
    -e "s|@APP_DIR@|$APP_DIR|g" \
    -e 's/\r$//' \
    "$APP_DIR/scripts/$UNIT" > "/etc/systemd/system/$UNIT.new"
chmod 644 "/etc/systemd/system/$UNIT.new"
mv "/etc/systemd/system/$UNIT.new" "/etc/systemd/system/$UNIT"

systemctl daemon-reload
systemctl enable "$UNIT"
systemctl restart "$UNIT"
sleep 2
systemctl --no-pager --lines=12 status "$UNIT" || true

echo
echo "boot start enabled: $UNIT (user $RUN_USER, directory $APP_DIR)"
echo "log     : journalctl -u $UNIT -f"
echo "stop    : sudo systemctl stop $UNIT"
echo "remove  : sudo sh $APP_DIR/scripts/install_service.sh --remove"
