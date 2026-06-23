
import pygame
from pygame.locals import *
pygame.init()
try:
    pygame.mixer.init()
except Exception:
    raise Exception("An audio output is required to run this game!")
from config import SCREEN_WIDTH, SCREEN_HEIGHT
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
from scene_manager import Fade, SceneManager
from vhs_effect import VHSEffect
from assets.scenes.menu import MenuScene
from assets.scenes.office import OfficeScene
from assets.scenes.scribe import ScribeScene
from assets.scenes.introduction import IntroductionScene
from game_manager import NewGame

clock = pygame.time.Clock()
vhs = VHSEffect(screen.get_size(), intensity=0.8)

def _present():
    vhs.apply(screen)
    pygame.display.flip()

fade = Fade(screen, clock, present=_present)

game = NewGame()
scene_manager = SceneManager()
scene_manager.scenes["menu"] = MenuScene(screen, clock, game, vhs=vhs)
scene_manager.scenes["office"] = OfficeScene(screen, clock)
scene_manager.scenes["scribe"] = ScribeScene(screen, clock, game)
scene_manager.scenes["introduction"] = IntroductionScene(screen, clock, game)

scene_manager.switch_scene("menu")

while game.is_running():
    next_scene = scene_manager.current_scene.update()
    if next_scene == "quit":
        game.quit()
    elif next_scene:
        scene_manager.switch_scene(next_scene, fade=fade)
    else:
        scene_manager.current_scene.render()
        vhs.apply(screen)
    pygame.display.flip()
    clock.tick(60)
