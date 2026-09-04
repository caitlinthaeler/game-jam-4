import os

from config import SOUNDS_DIR, UI_PATH, SCREEN_HEIGHT, SCREEN_WIDTH, FONT, BORDER
from scene_manager import Scene
from classes import Button, AnimatedButton, BackButton, get_clicked_button, format_background, scale_hover
from assets_registry import Assets
from game_manager import NewGame
from slider import Slider
from enum import Enum
import pygame

class MenuState(Enum):
    CHOICES = 0 # main start screen
    NEW_GAME = 1 # player enters name
    INFO = 2
    LAUNCH_GAME = 3 # exit menu
    QUIT = 4
    CONTINUE = 5
    SETTINGS = 6


class MenuScene(Scene):
    def __init__(self, screen: pygame.Surface, clock: pygame.time.Clock, game, vhs=None):
        super().__init__(screen, clock)
        self._game = game
        self._vhs = vhs
        self.state = MenuState.CHOICES

        # scene actions
        self.state_actions = {
            MenuState.CHOICES: self.render_start_screen,
            MenuState.NEW_GAME: self.start_new_game,
            MenuState.INFO: self.render_info_screen,
            MenuState.QUIT: self.render_quit_screen,
            MenuState.CONTINUE: self.continue_game,
            MenuState.SETTINGS: self.render_settings_screen,
        }

        # music and ambience
        self.music = Assets.background_music.menu
       
        # sound effecrts:
        self.start_sound = pygame.mixer.Sound(os.path.join(SOUNDS_DIR, "game_start.mp3"))
        self.start_sound.set_volume(0.5)

        # backgrounds
        self.main_background = format_background(self.screen, "main_menu.png")
        self.info_background = format_background(self.screen, "main_menu.png")

        # adjust these parameters ONLY, to reposition buttons and popup:
        btn_w, btn_h = int(Button.default_button_width * 1.1), Button.default_button_height
        button_x, button_y, button_y_buffer = 240, 406 - btn_h // 2, 58
        self.buttons = [
            Button(self.screen, MenuState.NEW_GAME, button_x, button_y, "Start", width=btn_w, height=btn_h),
            Button(self.screen, MenuState.CONTINUE, SCREEN_WIDTH-button_x-btn_w, button_y, "Continue", width=btn_w, height=btn_h, sound=self.start_sound),
            Button(self.screen, MenuState.INFO, button_x, button_y+button_y_buffer, "Info", width=btn_w, height=btn_h),
            Button(self.screen, MenuState.QUIT, SCREEN_WIDTH-button_x-btn_w, button_y+button_y_buffer, "Quit", width=btn_w, height=btn_h),
            Button(self.screen, MenuState.SETTINGS, button_x, button_y+(button_y_buffer)*2, "Settings", width=btn_w, height=btn_h),
        ]

        self.back_button = BackButton(self.screen, MenuState.CHOICES) # defaults only
        self.grain_slider = Slider(
            pygame.Rect(BORDER*4, BORDER*7+24, SCREEN_WIDTH // 2, 24),
            value=self._vhs.intensity if self._vhs else 0.65,
            on_change=self._vhs.set_intensity if self._vhs else None,
            label_font=FONT,
        )

        self.spacebar = pygame.image.load(os.path.join(UI_PATH, "spacebar.png")).convert_alpha()
        self.spacebar = pygame.transform.scale(self.spacebar, (200, 70))
        self.info = pygame.image.load(os.path.join(UI_PATH, "info.png")).convert()
        self.info = pygame.transform.scale(self.main_background, self.screen.get_size())


    def update(self) -> str | None:
        if self.state == MenuState.NEW_GAME:
            self.state = MenuState.CHOICES
            self._game.save()
            return "introduction"
        elif self.state == MenuState.CONTINUE:
            self.state = MenuState.CHOICES
            self._game.load()
            return "archive"
        elif self.state == MenuState.QUIT:
            return "quit"
        return None

    def render(self):
        if self.state != MenuState.LAUNCH_GAME:
            self.state_actions[self.state]()
        


    def render_start_screen(self):
        self.buttons[1].enabled = NewGame.has_save()
        self.screen.blit(self.main_background, (0, 0))
        for button in self.buttons: button.draw()
        for _ in self.handle_events(self.buttons): pass

    def render_info_screen(self):
        for _ in self.handle_events([self.back_button]): pass
        self.screen.blit(self.info, (0, 0))
        overlay = pygame.Surface((SCREEN_WIDTH-BORDER*2, SCREEN_HEIGHT-BORDER*2), pygame.SRCALPHA)
        pygame.draw.rect(overlay, (255, 255, 255, 150), (overlay.get_rect()))
        self.screen.blit(overlay, (BORDER, BORDER))
        self.back_button.draw()

        # display text:
        text = [
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "Click the PAINTBRUSH icon to start the levels.",
            "",
            "Use the < > arrow keys to rotate illumination tiles.",
            "",
            "The number of TRUST POINTS awarded decreases with each incorrect answer.",
            "",
            "To spend your TRUST POINTS, click the BOOK icon to return to the archive."
        ]
        for i, line in enumerate(text):
            self.screen.blit(FONT.render(line,
                True, (0, 0, 0)), (BORDER*2, BORDER*7+25*i)
            )
        
        # display key graphics:
        space_x, space_y = 572, 260
        # self.screen.blit(self.spacebar, (space_x, space_y))
        # self.screen.blit(FONT.render("space", False, (0, 0, 0)), (space_x+30, space_y+20))

    def render_settings_screen(self):
        for _ in self.handle_events([self.back_button]): pass
        self.screen.blit(self.info, (0, 0))
        overlay = pygame.Surface((SCREEN_WIDTH-BORDER*2, SCREEN_HEIGHT-BORDER*2), pygame.SRCALPHA)
        pygame.draw.rect(overlay, (255, 255, 255, 150), (overlay.get_rect()))
        self.screen.blit(overlay, (BORDER, BORDER))
        self.back_button.draw()

        label = FONT.render("Grain intensity", True, (0, 0, 0))
        self.screen.blit(label, (self.grain_slider.rect.left, self.grain_slider.rect.top - 32))

        self.grain_slider.draw(self.screen)

    def launch_game(self):
        self.state = MenuState.LAUNCH_GAME
        self.start_sound.play()

    def render_quit_screen(self):
        # Draw the quit confirmation screen
        pass

    def start_new_game(self):
        self.state = MenuState.NEW_GAME
        self.start_sound.play()

    def continue_game(self):
        self.state = MenuState.CONTINUE

    def handle_events(self, buttons):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.state = MenuState.QUIT
                return # exit immediately
            if self.state == MenuState.SETTINGS:
                self.grain_slider.handle_event(event)

            # return button that was clicked, if there was one:
            clicked_button = get_clicked_button(event, buttons)
            if clicked_button:
                print(f"Clicked button: {clicked_button}")
                self.state = clicked_button.action() # go to new menu state
                yield clicked_button
                continue # process remaining events
            yield event # return remaining events, itteratively

    

    
