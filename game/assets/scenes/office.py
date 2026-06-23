from config import SCREEN_WIDTH, SCREEN_HEIGHT, BORDER
from scene_manager import Scene
from assets_registry import Assets, Animation, Frame
from classes import AnimatedButton, get_clicked_button, format_background, scale_hover, tint_hover, draw_label
import pygame
from enum import Enum
from game_manager import game_data


def _invisible_anim(w: int, h: int) -> Animation:
    return Animation([Frame(color=(0, 0, 0, 0), size=(w, h))], ticks_per_frame=30)


# Original centres for the 3 surveyor map icons — adjust to match your artwork.
ARTEFACT_ORIGINS = [
    (50, 100),   # artefact 1 top left
    (200, 250),   # arefact 2 top right
    (50, 100),   # artefact 3 bottom left
    (200, 250),   # artefact 4 bottom right
]
# Where the selected artefact icon slides to on the desk.
ARTEFACT_TABLE_CENTER = (SCREEN_WIDTH - 200, SCREEN_HEIGHT - 150)


class OfficeState(Enum):
    MENU       = 0
    SCRIBE     = 1
    ARTEFACT   = 2
    IDLE       = 3
    QUIT       = 4
    BOOK_FLIP  = 5

class OfficeScene(Scene):
    def __init__(self, screen: pygame.Surface, clock: pygame.time.Clock):
        super().__init__(screen, clock)
        self.state = OfficeState.IDLE

        self.music    = Assets.background_music.church
        self.ambience = Assets.sounds.women_murmuring

        self.office_background = format_background(self.screen, "office_main.png")

        self.buttons = [
            AnimatedButton(
                surface=self.screen,
                next_state=OfficeState.BOOK_FLIP,
                animation=Assets.animations.scribe_icon,
                x=SCREEN_WIDTH - BORDER, y=BORDER,
                anchor="topright",
                text="scribe",
                text_offset=(-10, 40),
                text_colour=(255, 255, 255),
                hover_transforms=[tint_hover((0, 87, 72)), scale_hover(1.1)],
                sound=Assets.sounds.page_turning,
            ),
            AnimatedButton(
                surface=self.screen,
                next_state=OfficeState.MENU,
                animation=Assets.animations.menu_icon,
                x=BORDER, y=BORDER,
                text="menu",
                hover_transforms=[tint_hover((87, 0, 72)), scale_hover(1.1)],
            ),
            # artefact icons — positions updated each frame in render().
            AnimatedButton(
                surface=self.screen,
                next_state=OfficeState.ARTEFACT,
                animation=Assets.animations.artefact_icon_1,
                x=ARTEFACT_ORIGINS[0][0], y=ARTEFACT_ORIGINS[0][1],
                anchor="center",
                width=120, height=80,
                hover_transforms=[tint_hover((255, 255, 255))],
            ),
            AnimatedButton(
                surface=self.screen,
                next_state=OfficeState.ARTEFACT,
                animation=Assets.animations.artefact_icon_2,
                x=ARTEFACT_ORIGINS[1][0], y=ARTEFACT_ORIGINS[1][1],
                anchor="center",
                width=100, height=90,
                hover_transforms=[tint_hover((255, 255, 255))],
            ),
            AnimatedButton(
                surface=self.screen,
                next_state=OfficeState.ARTEFACT,
                animation=Assets.animations.artefact_icon_3,
                x=ARTEFACT_ORIGINS[2][0], y=ARTEFACT_ORIGINS[2][1],
                anchor="center",
                width=200, height=60,
                hover_transforms=[tint_hover((255, 255, 255))],
            ),
            AnimatedButton(
                surface=self.screen,
                next_state=OfficeState.ARTEFACT,
                animation=Assets.animations.artefact_icon_4,
                x=ARTEFACT_ORIGINS[2][0], y=ARTEFACT_ORIGINS[2][1],
                anchor="center",
                width=200, height=60,
                hover_transforms=[tint_hover((255, 255, 255))],
            ),
        ]

        self.artefact_buttons = self.buttons[2:]

    def update(self):
        if self.state == OfficeState.MENU:
            self.state = OfficeState.IDLE
            return "menu"
        elif self.state == OfficeState.BOOK_FLIP:
            anim = Assets.animations.book_flip_animation
            if anim.current_frame_index >= len(anim.frames) - 1:
                anim.current_frame_index = 0
                anim.ticks_elapsed = 0
                self.state = OfficeState.IDLE
                return "scribe"
        elif self.state == OfficeState.SCRIBE:
            self.state = OfficeState.IDLE
            return "scribe"
        elif self.state == OfficeState.ARTEFACT:
            self.state = OfficeState.IDLE
            return "artefact" if game_data.has_unlocked_artefact() else None
        elif self.state == OfficeState.QUIT:
            self.state = OfficeState.IDLE
            return "quit"
        return None

    def render(self):
        self.screen.blit(self.office_background, (0, 0))
        for i, btn in enumerate(self.artefact_buttons):
            cx, cy = ARTEFACT_TABLE_CENTER[0] + ARTEFACT_ORIGINS[i][0], ARTEFACT_TABLE_CENTER[1] + ARTEFACT_ORIGINS[i][1]
            btn.base_rect.center = cx, cy
        for button in self.buttons:
            button.draw()
        draw_label(self, SCREEN_WIDTH // 2, BORDER * 2,
                   "Trust Points: " + str(game_data.total_trust_points),
                   Assets.animations.coin_animation)

        if self.state == OfficeState.BOOK_FLIP:
            anim = Assets.animations.book_flip_animation
            anim.update()
            img = anim.current_frame.image
            cx = SCREEN_WIDTH // 2 - img.get_width() // 2
            cy = SCREEN_HEIGHT // 2 - img.get_height() // 2
            self.screen.blit(img, (cx, cy))
        else:
            for _ in self.handle_events(list(self.buttons)):
                pass

    def handle_events(self, buttons):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.state = OfficeState.QUIT
                return
            clicked_button = get_clicked_button(event, buttons)
            if clicked_button:
                self.state = clicked_button.action()
                yield clicked_button
                continue
            yield event
