import os

from config import SOUNDS_DIR, UI_PATH, SCREEN_HEIGHT, SCREEN_WIDTH, FONT, BORDER
from scene_manager import Scene
from classes import Button, AnimatedButton, BackButton, get_clicked_button, format_background, scale_hover
from assets_registry import Assets
from game_manager import NewGame
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
        self.vhs_intensity = self._vhs.intensity if self._vhs else 0.8
        self.grain_slider_rect = pygame.Rect(BORDER*2, BORDER*7+24, SCREEN_WIDTH - BORDER*4, 24)
        self._slider_dragging = False

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
        overlay = pygame.Surface((SCREEN_WIDTH-BORDER*2, SCREEN_HEIGHT-BORDER*5), pygame.SRCALPHA)
        pygame.draw.rect(overlay, (255, 255, 255, 150), (overlay.get_rect()))
        self.screen.blit(overlay, (BORDER, BORDER*3+10))
        self.back_button.draw()

        # display text:
        text = [
            "No information here yet",
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
        self.screen.blit(self.main_background, (0, 0))
        overlay = pygame.Surface((SCREEN_WIDTH-BORDER*2, SCREEN_HEIGHT-BORDER*5), pygame.SRCALPHA)
        pygame.draw.rect(overlay, (255, 255, 255, 150), (overlay.get_rect()))
        self.screen.blit(overlay, (BORDER, BORDER*3+10))
        self.back_button.draw()

        label = FONT.render("Grain intensity", True, (0, 0, 0))
        self.screen.blit(label, (self.grain_slider_rect.left, self.grain_slider_rect.top - 32))

        # slider track and fill
        pygame.draw.rect(self.screen, (200, 200, 200), self.grain_slider_rect, border_radius=12)
        fill_rect = self.grain_slider_rect.copy()
        fill_rect.width = int(self.vhs_intensity * self.grain_slider_rect.width)
        pygame.draw.rect(self.screen, (120, 120, 120), fill_rect, border_radius=12)

        knob_x = self.grain_slider_rect.left + int(self.vhs_intensity * self.grain_slider_rect.width)
        knob_radius = self.grain_slider_rect.height // 2 + 4
        knob_center = (knob_x, self.grain_slider_rect.centery)
        pygame.draw.circle(self.screen, (255, 255, 255), knob_center, knob_radius)
        pygame.draw.circle(self.screen, (80, 80, 80), knob_center, knob_radius, 2)

        percent_label = FONT.render(f"{int(self.vhs_intensity * 100)}%", True, (0, 0, 0))
        self.screen.blit(percent_label, (self.grain_slider_rect.right + 16, self.grain_slider_rect.centery - percent_label.get_height() // 2))



    def _update_vhs_intensity(self, x: int):
        rel_x = max(0, min(x - self.grain_slider_rect.left, self.grain_slider_rect.width))
        self.vhs_intensity = rel_x / self.grain_slider_rect.width
        if self._vhs:
            self._vhs.set_intensity(self.vhs_intensity)

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
            # return button that was clicked, if there was one:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.grain_slider_rect.collidepoint(event.pos):
                    self._slider_dragging = True
                    self._update_vhs_intensity(event.pos[0])
            elif event.type == pygame.MOUSEMOTION and self._slider_dragging:
                self._update_vhs_intensity(event.pos[0])
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self._slider_dragging:
                self._slider_dragging = False

            clicked_button = get_clicked_button(event, buttons)
            if clicked_button:
                print(f"Clicked button: {clicked_button}")
                self.state = clicked_button.action() # go to new menu state
                yield clicked_button
                continue # process remaining events
            yield event # return remaining events, itteratively

    

    
