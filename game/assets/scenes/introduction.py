import pygame
from classes import format_background
from scene_manager import Scene
from dialogue_manager import DialogueManager


class IntroductionScene(Scene):

    def __init__(self, screen: pygame.Surface, clock: pygame.time.Clock, game, vhs=None):
        super().__init__(screen, clock)
        self._game = game
        self._dialogue = DialogueManager(screen, clock, vhs=vhs)
        self.main_background = format_background(self.screen, "archive_background.png")


    def update(self) -> str | None:
        self.render()
        return self._dialogue.run("player", self._game)

    def render(self):
        self.screen.blit(self.main_background, (0, 0))  