"""Animated_eye - oeil projete en 1080p, anime par saccades."""

import os

# pygame salue la communaute des son import, ce qui pollue la sortie d'une
# commande. La variable se pose avant tout import de pygame : le paquet est le
# premier module charge, c'est donc l'endroit sur.
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

__version__ = "0.1.0"

