from config import SCREEN_WIDTH, SCREEN_HEIGHT, BORDER, FONT
from scene_manager import Scene
from assets_registry import Assets
from classes import AnimatedButton, get_clicked_button, format_background, scale_hover, draw_label
import pygame
from enum import Enum
from game_manager import game_data


ARTEFACT_TABLE_W   = 600
ARTEFACT_TABLE_H   = 150
ARTEFACT_TABLE_POS = (200, SCREEN_HEIGHT - ARTEFACT_TABLE_H - 25)

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
        "title": "Blackadder Charter",
        "blurb": (
            "Granted in the reign of William the Lion, this charter records the gift "
            "of Blackadder lands to the monks of Coldingham Priory. Its faded ink "
            "bears witness to centuries of careful preservation in the archive."
        ),
        "cost": 5,
    },
    {
        "title": "Gask Inscription",
        "blurb": (
            "Recovered near the Gask Ridge in Perthshire, this stone fragment carries "
            "a Latin inscription marking the northern extent of Roman military "
            "operations in ancient Caledonia."
        ),
        "cost": 10,
    },
    {
        "title": "Lesmahagow Register",
        "blurb": (
            "A leaf from the thirteenth-century register of Lesmahagow Priory, "
            "recording teinds paid by local tenants. The hand is an elegant Caroline "
            "minuscule rarely seen elsewhere in Scottish records."
        ),
        "cost": 15,
    },
    {
        "title": "Scone Chartulary",
        "blurb": (
            "Compiled at Scone Abbey in the early fourteenth century, this chartulary "
            "preserves royal confirmations including one bearing the seal of "
            "Robert I, the Bruce."
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
            anim = Assets.animations.book_flip_animation
            if anim.current_frame_index >= len(anim.frames) - 1:
                anim.current_frame_index = 0
                anim.ticks_elapsed = 0
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

        # Semi-transparent dark overlay
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 185))
        self.screen.blit(overlay, (0, 0))

        # Panel background
        panel = pygame.Rect(_PANEL_X, _PANEL_Y, _PANEL_W, _PANEL_H)
        pygame.draw.rect(self.screen, (245, 235, 200), panel, border_radius=6)
        pygame.draw.rect(self.screen, (140, 110, 70), panel, 2, border_radius=6)

        # Artefact image — left side, vertically centred
        img_x = _PANEL_X + 18
        img_y = _PANEL_Y + (_PANEL_H - ARTEFACT_FULL_SIZE) // 2
        anim  = art["unlocked_anim"]
        img   = pygame.transform.scale(anim.current_frame.image,
                                        (ARTEFACT_FULL_SIZE, ARTEFACT_FULL_SIZE))
        self.screen.blit(img, (img_x, img_y))

        # Title + wrapped blurb — right of image
        tx = img_x + ARTEFACT_FULL_SIZE + 18
        tw = _PANEL_X + _PANEL_W - tx - 14
        ty = _PANEL_Y + 20
        title_surf = FONT.render(art["title"], True, (55, 28, 8))
        self.screen.blit(title_surf, (tx, ty))
        self._draw_wrapped(art["blurb"], tx, ty + title_surf.get_height() + 10, tw, (70, 45, 18))

        # Dismiss hint
        hint = FONT.render("Esc or click outside to close", True, (130, 105, 72))
        self.screen.blit(hint, hint.get_rect(centerx=panel.centerx, bottom=panel.bottom - 10))

    def _draw_wrapped(self, text: str, x: int, y: int, max_w: int, colour: tuple):
        line_h = FONT.get_height() + 3
        line   = ""
        for word in text.split():
            test = (line + " " + word).strip()
            if FONT.size(test)[0] <= max_w:
                line = test
            else:
                if line:
                    self.screen.blit(FONT.render(line, True, colour), (x, y))
                    y += line_h
                line = word
        if line:
            self.screen.blit(FONT.render(line, True, colour), (x, y))

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
