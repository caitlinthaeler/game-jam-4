import os

from config import SCREEN_WIDTH, SCREEN_HEIGHT, BORDER, FONT, UI_PATH
from scene_manager import Scene
from assets_registry import Assets
from classes import AnimatedButton, get_clicked_button, format_background, scale_hover, draw_label
import pygame
from enum import Enum
from game_manager import game_data


ARTEFACT_TABLE_W   = 560
ARTEFACT_TABLE_H   = 150
ARTEFACT_TABLE_POS = (SCREEN_WIDTH // 2 - ARTEFACT_TABLE_W // 2,
                      SCREEN_HEIGHT - ARTEFACT_TABLE_H - 90)

ARTEFACT_ICON_SIZE = 64
ARTEFACT_FULL_SIZE = 192

_FILL_BAR_H   = 10
_FILL_BAR_GAP = 5          # gap between fill bar bottom and icon top
_FILL_TOP_PAD = 14         # padding from table top to fill bar top
_UNLOCK_W     = 72
_UNLOCK_H     = 26
_UNLOCK_GAP   = 5          # gap between icon bottom and unlock button top

_N      = 4                # number of artefacts
_SLOT_W = ARTEFACT_TABLE_W // _N   # 150 px per slot

# Modal panel dimensions
_PANEL_W = 480
_PANEL_H = 280
_PANEL_X = SCREEN_WIDTH  // 2 - _PANEL_W // 2
_PANEL_Y = SCREEN_HEIGHT // 2 - _PANEL_H // 2


_ARTEFACT_DEFS = [
    {
        "title": "Blackadder Prayerbook",
        "blurb": (
            "This prayerbook was made in Paris for Robert Blackadder, who became a "
            "bishop of Glasgow in the late 15th Century. Manuscripts were often tailored "
            "to fit the customs of the owner, and Blackadder’s prayerbook highlights multiple "
            "Scottish saints that would have felt more personally relevant to the area. "
            "Though contained within their own category of Saint, the Blackadder prayerbook "
            "contains prayers to a significant number of female saints - complete with a small "
            "illustration of them. After the completion of the manuscript, St. Kentigerna was "
            "added in the first page of the prayerbook as a patroness of Lochcailloch."
        ),
        "cost": 5,
    },
    {
        "title": "Gask Family Charters",
        "blurb": (
            "The Gask family (also known as the Oliphants of Gask) were jacobites, and are "
            "famous for their part in the 18th Century uprisings. These charters date back to "
            "their role in the medieval period and are found in various monastic records. The "
            "three Gask family charters in the National Library of Scotland highlight not only "
            "the ties the Gask family had to royalty, but also illuminate the involvement of "
            "aristocratic women in land transactions."
        ),
        "cost": 10,
    },
    {
        "title": "Chartulary of Scone Abbey (15th to 16th Century)",
        "blurb": (
            "These documents contain a collection of marginalia; sketch work completed in "
            "the margins. Such examples found are faces, animals - also found in proper illustration "
            "alongside richly decorated names of royal men. An earlier chartulary of Scone Abbey is "
            "present in the National Library of Scotland, and its contents reveal that the scribes "
            "were able to copy notable information down from it onto the later documents. Something "
            "that stands out in these documents is the complete, and possibly intentional, absence "
            "of women."
        ),
        "cost": 20,
    },
    {
        "title": "Lesmahagow Missal",
        "blurb": (
            "These documents contain a collection of marginalia; sketch work completed in "
            "the margins. Such examples found are faces, animals - also found in proper illustration "
            "alongside richly decorated names of royal men. An earlier chartulary of Scone Abbey is "
            "present in the National Library of Scotland, and its contents reveal that the scribes "
            "were able to copy notable information down from it onto the later documents. Something "
            "that stands out in these documents is the complete, and possibly intentional, absence "
            "of women."
        ),
        "cost": 20,
    },
]


def _icon_rect(i: int) -> pygame.Rect:
    """Screen-space rect for artefact icon i, positioned on the table."""
    cx     = ARTEFACT_TABLE_POS[0] + _SLOT_W * i + _SLOT_W // 2
    icon_y = ARTEFACT_TABLE_POS[1] + _FILL_TOP_PAD + _FILL_BAR_H + _FILL_BAR_GAP
    return pygame.Rect(cx - ARTEFACT_ICON_SIZE // 2, icon_y,
                       ARTEFACT_ICON_SIZE, ARTEFACT_ICON_SIZE)


class ArchiveState(Enum):
    MENU      = 0
    IDLE      = 3
    QUIT      = 4
    BOOK_FLIP = 5


class ArchiveScene(Scene):
    def __init__(self, screen: pygame.Surface, clock: pygame.time.Clock):
        super().__init__(screen, clock)
        self.state = ArchiveState.IDLE

        self.music    = Assets.background_music.church
        self.ambience = Assets.sounds.women_murmuring

        self.archive_background = format_background(self.screen, "archive_background.png")

        _locked_anims = [
            Assets.animations.blackadder_locked,
            Assets.animations.gask_locked,
            Assets.animations.lesmahagow_locked,
            Assets.animations.scone_chartulary_locked,
        ]
        _unlocked_anims = [
            Assets.animations.blackadder_unlocked,
            Assets.animations.gask_unlocked,
            Assets.animations.lesmahagow_unlocked,
            Assets.animations.scone_chartulary_unlocked,
        ]
        self._artefacts = [
            {**d, "locked_anim": la, "unlocked_anim": ua}
            for d, la, ua in zip(_ARTEFACT_DEFS, _locked_anims, _unlocked_anims)
        ]

        self._icon_rects = [_icon_rect(i) for i in range(_N)]

        # Index of artefact currently shown in the detail modal, or None
        self._modal_idx: int | None = None

        self.buttons = [
            AnimatedButton(
                surface=self.screen,
                next_state=ArchiveState.BOOK_FLIP,
                animation=Assets.animations.paint_icon,
                x=SCREEN_WIDTH - BORDER, y=BORDER,
                anchor="topright",
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
        ]

    # ── update ────────────────────────────────────────────────────────────────

    def update(self):
        if self.state == ArchiveState.MENU:
            self.state = ArchiveState.IDLE
            return "menu"
        if self.state == ArchiveState.BOOK_FLIP:
            # anim = Assets.animations.book_flip_animation
            # if anim.current_frame_index >= len(anim.frames) - 1:
            #     anim.current_frame_index = 0
            #     anim.ticks_elapsed = 0
            self.state = ArchiveState.IDLE
            return "scribe"
        if self.state == ArchiveState.QUIT:
            self.state = ArchiveState.IDLE
            return "quit"
        return None

    # ── render ────────────────────────────────────────────────────────────────

    def render(self):
        self.screen.blit(self.archive_background, (0, 0))

        self._draw_artefacts()

        for btn in self.buttons:
            btn.draw()

        draw_label(self, SCREEN_WIDTH // 2, BORDER * 2,
                   "Trust Points: " + str(game_data.total_trust_points),
                   Assets.animations.coin_animation)

        if self.state == ArchiveState.BOOK_FLIP:
            anim = Assets.animations.book_flip_animation
            anim.update()
            img = anim.current_frame.image
            self.screen.blit(img, (SCREEN_WIDTH // 2 - img.get_width() // 2,
                                   SCREEN_HEIGHT // 2 - img.get_height() // 2))
        else:
            self._handle_events()

        # Modal drawn last so it sits above everything
        if self._modal_idx is not None:
            self._draw_modal(self._modal_idx)

    # ── artefact drawing ──────────────────────────────────────────────────────

    def _draw_artefacts(self):
        pts   = game_data.total_trust_points
        mouse = pygame.mouse.get_pos()

        for i, art in enumerate(self._artefacts):
            icon_rect = self._icon_rects[i]
            cost      = art["cost"]
            unlocked  = game_data.is_artefact_unlocked(i)

            # Icon
            anim = art["unlocked_anim"] if unlocked else art["locked_anim"]
            img  = pygame.transform.scale(anim.current_frame.image,
                                          (ARTEFACT_ICON_SIZE, ARTEFACT_ICON_SIZE))
            anim.update()
            self.screen.blit(img, icon_rect.topleft)

            # Fill bar
            bar_rect = pygame.Rect(
                icon_rect.x,
                icon_rect.top - _FILL_BAR_GAP - _FILL_BAR_H,
                ARTEFACT_ICON_SIZE, _FILL_BAR_H,
            )
            fill_frac = 1.0 if unlocked else min(pts / cost, 1.0)
            pygame.draw.rect(self.screen, (55, 40, 25), bar_rect, border_radius=3)
            if fill_frac > 0:
                filled_w = max(1, int(bar_rect.w * fill_frac))
                fill_col = (65, 155, 65) if (unlocked or fill_frac >= 1.0) else (195, 150, 45)
                pygame.draw.rect(self.screen, fill_col,
                                 pygame.Rect(bar_rect.x, bar_rect.y, filled_w, bar_rect.h),
                                 border_radius=3)
            pygame.draw.rect(self.screen, (185, 165, 130), bar_rect, 1, border_radius=3)

            # Progress label above bar  e.g. "3/5"
            lbl = FONT.render(f"{min(pts, cost)}/{cost}", True, (210, 195, 160))
            self.screen.blit(lbl, (bar_rect.x, bar_rect.top - lbl.get_height() - 2))

            # Unlock button — shown only when the player can afford it
            if not unlocked and pts >= cost:
                btn_rect = pygame.Rect(
                    icon_rect.centerx - _UNLOCK_W // 2,
                    icon_rect.bottom + _UNLOCK_GAP,
                    _UNLOCK_W, _UNLOCK_H,
                )
                hover = btn_rect.collidepoint(mouse) and self._modal_idx is None
                bg    = (135, 105, 60) if hover else (90, 65, 35)
                pygame.draw.rect(self.screen, bg, btn_rect, border_radius=4)
                pygame.draw.rect(self.screen, (185, 165, 130), btn_rect, 1, border_radius=4)
                ul = FONT.render("Unlock", True, (245, 230, 195))
                self.screen.blit(ul, ul.get_rect(center=btn_rect.center))

    # ── modal ─────────────────────────────────────────────────────────────────

    def _draw_modal(self, idx: int):
        art = self._artefacts[idx]

        panel_w = min(720, SCREEN_WIDTH - BORDER * 6)
        text_area_width = panel_w - (ARTEFACT_FULL_SIZE + 18 + 14 + 18)
        title_font = pygame.font.Font(os.path.join(UI_PATH, "pixelfont.ttf"), 24)
        body_font = self._choose_modal_font(art["blurb"], text_area_width)
        hint_font = pygame.font.Font(os.path.join(UI_PATH, "pixelfont.ttf"), 14)

        body_lines = self._wrap_text(art["blurb"], body_font, text_area_width)
        title_surf = title_font.render(art["title"], True, (55, 28, 8))

        title_h = title_font.get_height()
        body_line_h = body_font.get_height() + 3
        hint_h = hint_font.get_height()
        text_height = title_h + 10 + len(body_lines) * body_line_h + 38 + hint_h
        panel_h = max(ARTEFACT_FULL_SIZE + 50, text_height + 52)
        panel_x = (SCREEN_WIDTH - panel_w) // 2
        panel_y = max((SCREEN_HEIGHT - panel_h) // 2, BORDER * 2)

        # Semi-transparent dark overlay
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 185))
        self.screen.blit(overlay, (0, 0))

        # Panel background
        panel = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
        pygame.draw.rect(self.screen, (245, 235, 200), panel, border_radius=6)
        pygame.draw.rect(self.screen, (140, 110, 70), panel, 2, border_radius=6)

        # Artefact image — left side, vertically centred
        img_x = panel_x + 18
        img_y = panel_y + (panel_h - ARTEFACT_FULL_SIZE) // 2
        anim = art["unlocked_anim"]
        img = pygame.transform.scale(anim.current_frame.image,
                                      (ARTEFACT_FULL_SIZE, ARTEFACT_FULL_SIZE))
        self.screen.blit(img, (img_x, img_y))

        # Title + wrapped blurb — right of image
        tx = img_x + ARTEFACT_FULL_SIZE + 18
        tw = panel_x + panel_w - tx - 14
        ty = panel_y + 20
        self.screen.blit(title_surf, (tx, ty))
        self._draw_wrapped(art["blurb"], tx, ty + title_h + 10, tw, (70, 45, 18), body_font)

        # Dismiss hint
        hint = hint_font.render("Esc or click outside to close", True, (130, 105, 72))
        self.screen.blit(hint, hint.get_rect(centerx=panel.centerx, bottom=panel.bottom - 10))

    def _wrap_text(self, text: str, font: pygame.font.Font, max_w: int) -> list[str]:
        lines = []
        line = ""
        for word in text.split():
            test = (line + " " + word).strip()
            if font.size(test)[0] <= max_w:
                line = test
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
        return lines

    def _choose_modal_font(self, text: str, max_w: int) -> pygame.font.Font:
        sizes = [20, 18, 16, 14]
        for size in sizes:
            font = pygame.font.Font(os.path.join(UI_PATH, "pixelfont.ttf"), size)
            lines = self._wrap_text(text, font, max_w)
            needed_height = len(lines) * (font.get_height() + 3) + 140
            if needed_height <= SCREEN_HEIGHT - BORDER * 8:
                return font
        return font

    def _draw_wrapped(self, text: str, x: int, y: int, max_w: int, colour: tuple, font: pygame.font.Font = FONT):
        line_h = font.get_height() + 3
        for line in self._wrap_text(text, font, max_w):
            self.screen.blit(font.render(line, True, colour), (x, y))
            y += line_h

    # ── events ────────────────────────────────────────────────────────────────

    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.state = ArchiveState.QUIT
                return

            # Modal dismissal has priority over everything
            if self._modal_idx is not None:
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self._modal_idx = None
                    continue
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    panel = pygame.Rect(_PANEL_X, _PANEL_Y, _PANEL_W, _PANEL_H)
                    if not panel.collidepoint(event.pos):
                        self._modal_idx = None
                continue  # block all other input while modal is open

            # Nav buttons
            clicked = get_clicked_button(event, self.buttons)
            if clicked:
                clicked.play_sound()
                self.state = clicked.action()
                continue

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                pts = game_data.total_trust_points
                for i, art in enumerate(self._artefacts):
                    icon_rect = self._icon_rects[i]
                    cost      = art["cost"]
                    unlocked  = game_data.is_artefact_unlocked(i)

                    # Unlock button click — deduct points and unlock
                    if not unlocked and pts >= cost:
                        btn_rect = pygame.Rect(
                            icon_rect.centerx - _UNLOCK_W // 2,
                            icon_rect.bottom + _UNLOCK_GAP,
                            _UNLOCK_W, _UNLOCK_H,
                        )
                        if btn_rect.collidepoint(mx, my):
                            game_data.unlock_artefact(i, cost)
                            Assets.sounds.coins_added.play()
                            break

                    # Click unlocked icon → open detail modal
                    if unlocked and icon_rect.collidepoint(mx, my):
                        self._modal_idx = i
                        Assets.sounds.bookpage.play()
                        break
