from abc import ABC, abstractmethod
from assets_registry import AudioChannel
import pygame

class Scene(ABC):
    def __init__(self, surface: pygame.Surface, clock: pygame.time.Clock):
        self.surface: pygame.Surface = surface
        self.screen: pygame.Surface = surface
        self.clock: pygame.time.Clock = clock

    @abstractmethod
    def update(self) -> str | None:
        pass

    @abstractmethod
    def render(self):
        pass


class Fade:
    def __init__(self, screen: pygame.Surface, clock: pygame.time.Clock, speed: int = 7, present=None):
        self.screen = screen
        self.clock = clock
        self.speed = speed
        self.present = present or pygame.display.flip
        self.overlay = pygame.Surface(screen.get_size())
        self.overlay.fill((0, 0, 0))

    def fade_out(self):
        frozen = self.screen.copy()
        alpha = 0

        while alpha < 255:
            self.screen.blit(frozen, (0, 0))
            self.overlay.set_alpha(alpha)
            self.screen.blit(self.overlay, (0, 0))
            self.present()
            self.clock.tick(60)
            alpha += self.speed

    def fade_in(self):
        frozen = self.screen.copy()
        alpha = 255

        while alpha > 0:
            self.screen.blit(frozen, (0, 0))
            self.overlay.set_alpha(alpha)
            self.screen.blit(self.overlay, (0, 0))
            self.present()
            self.clock.tick(60)
            alpha -= self.speed


class SceneManager:
    def __init__(self):
        self.scenes: dict[str, Scene] = {}
        self.current_scene: Scene = None

    def switch_scene(self, scene_name: str, fade: Fade = None):
        new_scene = self.scenes[scene_name]

        if self.current_scene is not None:
            old_music = getattr(self.current_scene, "music", None)
            old_ambience = getattr(self.current_scene, "ambience", None)
            if old_music and old_music != getattr(new_scene, "music", None):
                pygame.mixer.music.stop()
                old_music.__class__.current_track = None
            if old_ambience and old_ambience != getattr(new_scene, "ambience", None):
                old_ambience.stop()

        if fade and self.current_scene is not None:
            fade.fade_out()

        self.current_scene = new_scene

        if fade:
            self.current_scene.render()
            fade.fade_in()

        if music := getattr(self.current_scene, "music", None):
            music.play()
        if ambience := getattr(self.current_scene, "ambience", None):
            ambience.play(AudioChannel.BACKGROUND_AMBIENCE.value)


