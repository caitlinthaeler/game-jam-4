from config import SCREEN_WIDTH, SCREEN_HEIGHT, BORDER
from scene_manager import Scene
from assets_registry import Assets, Animation, Frame
from classes import AnimatedButton, get_clicked_button, format_background, scale_hover, tint_hover, draw_label
import pygame
from enum import Enum
from game_manager import game_data


def _invisible_anim(w: int, h: int) -> Animation:
    return Animation([Frame(color=(0, 0, 0, 0), size=(w, h))], ticks_per_frame=30)


# Where the selected artefact icon slides to on the desk.
ARTEFACT_TABLE_W, ARTEFACT_TABLE_H = 600, 150
ARTEFACT_POS = (50, SCREEN_HEIGHT-ARTEFACT_TABLE_H-50)
ARTEFACT_TABLE_CENTER = (SCREEN_WIDTH - 200, SCREEN_HEIGHT - 150)

# Relative to the artefact table
ARTEFACT_ORIGINS = [
    (0, 0),   # artefact 1 - blackadder
    (64, 0),   # arefact 2 - gask
    (128, 0),   # artefact 3 - lesmahagow
    (192, 0),   # artefact 4 - scone chartulary
]

ARTEFACT_ICON_SIZE = 64
ARTEFACT_FULL_SIZE = 192


class ArchiveState(Enum):
    MENU       = 0
    SCRIBE     = 1
    ARTEFACT   = 2
    IDLE       = 3
    QUIT       = 4
    BOOK_FLIP  = 5

class ArchiveScene(Scene):
    def __init__(self, screen: pygame.Surface, clock: pygame.time.Clock):
        super().__init__(screen, clock)
        self.state = ArchiveState.IDLE

        self.music    = Assets.background_music.church
        self.ambience = Assets.sounds.women_murmuring

        self.archive_background = format_background(self.screen, "archive_background.png")

        self.buttons = [
            AnimatedButton(
                surface=self.screen,
                next_state=ArchiveState.BOOK_FLIP,
                animation=Assets.animations.paint_icon,
                x=SCREEN_WIDTH - BORDER, y=BORDER,
                anchor="topright",
                text="scribe",
                text_offset=(-10, 40),
                text_colour=(255, 255, 255),
                hover_transforms=[ scale_hover(1.1)],
                sound=Assets.sounds.page_turning,
            ),
            AnimatedButton(
                surface=self.screen,
                next_state=ArchiveState.MENU,
                animation=Assets.animations.menu_icon,
                x=BORDER, y=BORDER,
                hover_transforms=[scale_hover(1.1)],
            ),
            # artefact icons — positions updated each frame in render().
            AnimatedButton(
                surface=self.screen,
                next_state=ArchiveState.ARTEFACT,
                animation=Assets.animations.blackadder_locked,
                x=ARTEFACT_ORIGINS[0][0], y=ARTEFACT_ORIGINS[0][1],
                # anchor="center",
                width=ARTEFACT_ICON_SIZE, height=ARTEFACT_ICON_SIZE,
                hover_transforms=[tint_hover((255, 255, 255))],
            ),
            AnimatedButton(
                surface=self.screen,
                next_state=ArchiveState.ARTEFACT,
                animation=Assets.animations.gask_locked,
                x=ARTEFACT_ORIGINS[1][0], y=ARTEFACT_ORIGINS[1][1],
                # anchor="center",
                width=ARTEFACT_ICON_SIZE, height=ARTEFACT_ICON_SIZE,
                hover_transforms=[tint_hover((255, 255, 255))],
            ),
            AnimatedButton(
                surface=self.screen,
                next_state=ArchiveState.ARTEFACT,
                animation=Assets.animations.lesmahagow_locked,
                x=ARTEFACT_ORIGINS[2][0], y=ARTEFACT_ORIGINS[2][1],
                # anchor="center",
                width=ARTEFACT_ICON_SIZE, height=ARTEFACT_ICON_SIZE,
                hover_transforms=[tint_hover((255, 255, 255))],
            ),
            AnimatedButton(
                surface=self.screen,
                next_state=ArchiveState.ARTEFACT,
                animation=Assets.animations.scone_chartulary_locked,
                x=ARTEFACT_ORIGINS[3][0], y=ARTEFACT_ORIGINS[3][1],
                # anchor="center",
                width=ARTEFACT_ICON_SIZE, height=ARTEFACT_ICON_SIZE,
                hover_transforms=[tint_hover((255, 255, 255))],
            ),
        ]

        self.artefact_buttons = self.buttons[2:]

    def update(self):
        if self.state == ArchiveState.MENU:
            self.state = ArchiveState.IDLE
            return "menu"
        elif self.state == ArchiveState.BOOK_FLIP:
            anim = Assets.animations.book_flip_animation
            if anim.current_frame_index >= len(anim.frames) - 1:
                anim.current_frame_index = 0
                anim.ticks_elapsed = 0
                self.state = ArchiveState.IDLE
                return "scribe"
        elif self.state == ArchiveState.SCRIBE:
            self.state = ArchiveState.IDLE
            return "scribe"
        elif self.state == ArchiveState.ARTEFACT:
            self.state = ArchiveState.IDLE
            return "artefact" if game_data.has_unlocked_artefact() else None
        elif self.state == ArchiveState.QUIT:
            self.state = ArchiveState.IDLE
            return "quit"
        return None

    def render(self):
        self.screen.blit(self.archive_background, (0, 0))
        for i, btn in enumerate(self.artefact_buttons):
            cx, cy = ARTEFACT_POS[0] + ARTEFACT_ORIGINS[i][0], ARTEFACT_POS[1] + ARTEFACT_ORIGINS[i][1]
            btn.base_rect.center = cx, cy
        for button in self.buttons:
            button.draw()
        draw_label(self, SCREEN_WIDTH // 2, BORDER * 2,
                   "Trust Points: " + str(game_data.total_trust_points),
                   Assets.animations.coin_animation)

        if self.state == ArchiveState.BOOK_FLIP:
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
                self.state = ArchiveState.QUIT
                return
            clicked_button = get_clicked_button(event, buttons)
            if clicked_button:
                self.state = clicked_button.action()
                yield clicked_button
                continue
            yield event
