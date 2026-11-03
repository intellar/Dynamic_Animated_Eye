import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pytest


@pytest.fixture(scope="session", autouse=True)
def pygame_session():
    pygame.init()
    pygame.display.set_mode((64, 64))
    yield
    pygame.quit()
