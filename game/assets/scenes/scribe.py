import os
import pygame
from enum import Enum

from scene_manager import Scene
from assets_registry import Assets, Animation, MarginPiece
from classes import (
    AnimatedButton, Button, get_clicked_button,
    scale_hover, tint_hover, format_background, draw_label,
    CellState, PuzzleData,
)
from config import BORDER, SCREEN_WIDTH, SCREEN_HEIGHT, FONT, BASE_TILE_SIZE, SPRITES_DIR, UI_PATH
from game_manager import game_data, SubmitResult

# ── layout constants ────────────────────────────────────────────────────────


# Book is 2×PAGE_W wide; centre it on screen.
BOOK_POS = (SCREEN_WIDTH//2 - 350, -160)

# grid dimensions
PAGE_W, PAGE_H = 350, 448
PAGE_LEFT_POS  = (BOOK_POS[0]+10, BOOK_POS[1]+130)
PAGE_RIGHT_POS = (BOOK_POS[0]+5+ PAGE_W, BOOK_POS[1]+130)

HINT_PAGE_W, HINT_PAGE_H = 24*5, 32*5
HINT_PAGE_LEFT_POS = (-5, SCREEN_HEIGHT - HINT_PAGE_H - 50)
HINT_PAGE_RIGHT_POS = (SCREEN_WIDTH - HINT_PAGE_W + 5, SCREEN_HEIGHT - HINT_PAGE_H - 50)
HINT_FADE_SPEED  = 8
SLIDE_SPEED = 7

PAGE_TEXT_LEFT = (PAGE_LEFT_POS[0]+140,  PAGE_LEFT_POS[1]+170)
PAGE_TEXT_RIGHT = (PAGE_RIGHT_POS[0]+20,  PAGE_RIGHT_POS[1]+170)
PAGE_TEXT_BOX_SIZE = (180, 180)

LEVEL_COMPLETE_TEXT_SPEED = .5
LEVEL_COMPLETE_FONT_SIZE = 22
LEVEL_COMPLETE_FONT_COLOR = (0, 0, 0)

# Final "you beat the book" overlay (see ScribeMode.COMPLETE)
COMPLETE_MESSAGE = "Congratulations! You've completed all the levels. Click ok to return to the main room."
COMPLETE_MESSAGE_BOX = (SCREEN_WIDTH // 2 - 250, SCREEN_HEIGHT // 2 - 160, 500, 100)
COMPLETE_MESSAGE_COLOUR = (255, 255, 255)

# ── drag / tray constants ───────────────────────────────────────────────────
# Grid is drawn inset from the page origin by this many pixels.
GRID_OFFSET = (0, 40)
# Piece tray sits below the book area.
TRAY_Y = 475
TRAY_PIECE_SIZE = 64  # display size of each tray thumbnail (px)
TRAY_SPACING = 75  # centre-to-centre horizontal gap in tray
# Tint colours for drag feedback
_COL_VALID = (130, 200, 130, 160)
_COL_INVALID = (220, 60,  60,  160)


def _scale_to_fit(surface: pygame.Surface, max_size: int) -> pygame.Surface:
    """Scale surface down to fit within a max_size x max_size box, preserving aspect ratio."""
    w, h = surface.get_size()
    scale = min(max_size / w, max_size / h)
    return pygame.transform.smoothscale(surface, (max(1, round(w * scale)), max(1, round(h * scale))))


def _wrap_text(text: str, font, max_width: int) -> list:
    """Word-wrap text into lines that each fit within max_width."""
    words = text.split(" ")
    lines = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if not current or font.size(candidate)[0] <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def _layout_text_block(text: str, box: tuple, font) -> list:
    """Word-wrap text to box's width, then centre the whole block (both axes)
    inside box = (x, y, w, h). Returns [(line, (x, y)), ...] top-left positions,
    each line individually centred horizontally."""
    box_x, box_y, box_w, box_h = box
    lines = _wrap_text(text, font, box_w)
    line_height = font.get_height()
    total_h = line_height * len(lines)
    start_y = box_y + (box_h - total_h) // 2
    layout = []
    for i, line in enumerate(lines):
        line_w, _ = font.size(line)
        x = box_x + (box_w - line_w) // 2
        y = start_y + i * line_height
        layout.append((line, (x, y)))
    return layout


# ── tiny per-frame effect objects ───────────────────────────────────────────

class _DropEffect:
    """Slides a surface in from the top of the screen to target_y."""
    def __init__(self, surface: pygame.Surface, x: int, target_y: int, speed: int = SLIDE_SPEED):
        self.surf     = surface
        self.x        = x
        self.y        = float(-surface.get_height())
        self.target_y = float(target_y)
        self.speed    = speed
        self.done     = False

    def update(self, screen: pygame.Surface):
        if self.done:
            return
        self.y = min(self.y + self.speed, self.target_y)
        screen.blit(self.surf, (self.x, int(self.y)))
        if self.y >= self.target_y:
            self.done = True


class _FadeEffect:
    """Cross-fades from old_surf to new_surf in place."""
    def __init__(self, old_surf: pygame.Surface, new_surf: pygame.Surface,
                 pos: tuple, speed: int = HINT_FADE_SPEED):
        self.old  = old_surf
        self.new  = new_surf.copy()
        self.pos  = pos
        self.alpha = 0
        self.speed = speed
        self.done  = False

    def update(self, screen: pygame.Surface):
        if self.done:
            return
        screen.blit(self.old, self.pos)
        self.new.set_alpha(self.alpha)
        screen.blit(self.new, self.pos)
        self.alpha = min(self.alpha + self.speed, 255)
        if self.alpha >= 255:
            self.done = True


class _TextRevealEffect:
    """Reveals a block of text character by character (stub — fill in yours)."""
    def __init__(self, text: str, pos: tuple, font, colour, chars_per_frame: int = 2):
        self.text   = text
        self.pos    = pos
        self.font   = font
        self.colour = colour
        self.cpf    = chars_per_frame
        self.shown  = 0
        self.done   = False

    def update(self, screen: pygame.Surface):
        if self.done:
            return
        self.shown = min(self.shown + self.cpf, len(self.text))
        label = self.font.render(self.text[:self.shown], True, self.colour)
        screen.blit(label, self.pos)
        if self.shown >= len(self.text):
            self.done = True


class _TextFadeInEffect:
    """Reveals word-wrapped text letter by letter inside a box (x, y, w, h):
    wrapped to the box's width, the whole block centred vertically, each
    line centred horizontally. Each new letter eases in via alpha.
    Completes in duration_frames regardless of text length."""
    def __init__(self, text: str, box: tuple, font, colour, duration_frames: int = 60):
        self.text     = text
        self.layout   = _layout_text_block(text, box, font)   # [(line, (x, y)), ...]
        self.font     = font
        self.colour   = colour
        self.duration = max(1, duration_frames)
        self.total_chars = sum(len(line) for line, _ in self.layout)
        self.frame    = 0
        self.done     = False

    def update(self, screen: pygame.Surface):
        if self.done:
            return
        self.frame += 1
        progress = min(1.0, self.frame / self.duration)
        shown = progress * self.total_chars
        remaining_full = int(shown)
        partial = shown - remaining_full

        for line, (x, y) in self.layout:
            if remaining_full >= len(line):
                if line:
                    label = self.font.render(line, True, self.colour)
                    screen.blit(label, (x, y))
                remaining_full -= len(line)
                continue

            next_x = x
            full_part = line[:remaining_full]
            if full_part:
                label = self.font.render(full_part, True, self.colour)
                screen.blit(label, (x, y))
                next_x += label.get_width()

            if remaining_full < len(line) and partial > 0:
                char_surf = self.font.render(line[remaining_full], True, self.colour)
                char_surf.set_alpha(int(255 * partial))
                screen.blit(char_surf, (next_x, y))

            break   # lines after the currently-revealing one stay hidden

        if self.frame >= self.duration:
            self.done = True


# ── scene modes ─────────────────────────────────────────────────────────────

class ScribeMode(Enum):
    INTERACTIVE = 1   # player can drag/drop on current-level page
    TRANSITION = 2   # effects running; all input locked
    REVIEW = 3   # browsing old pages; no drag/drop
    COMPLETE = 4 # shows ok buton on dark overlay


# ── main scene ──────────────────────────────────────────────────────────────

class ScribeScene(Scene):
    def __init__(self, screen: pygame.Surface, clock: pygame.time.Clock, game):
        super().__init__(screen, clock)
        self.game = game

        self.music    = Assets.background_music.gameplay
        self.ambience = Assets.sounds.women_murmuring
        self.background = format_background(screen, "office_desk.png")
        self._cursor_img = pygame.image.load(SPRITES_DIR + "items/arm.png").convert_alpha()
        # self._cursor_img = pygame.transform.scale(self._cursor_img, (32, 32))

        # ── mode & transition ──
        self.mode: ScribeMode     = ScribeMode.INTERACTIVE
        self.active_effects: list = []   # updated each frame; cleared when all done
        # Captured snapshots of completed book pages (grid+pieces), keyed by level.
        self._book_snapshots: dict[int, pygame.Surface] = {}

        # ── page-view state ──
        # Which level's page is the player currently viewing (for review mode).
        self.viewed_level: int = game_data.current_level

        # Cache rendered hint surfaces so we don't recreate them every frame.
        # keyed by level number.
        self._hint_surfs: dict[int, pygame.Surface] = {}

        # ── drag state ──
        # Unique piece types — one slot per piece_id regardless of how many times
        # it appears in the solution.  This list never changes during play.
        raw_pieces = game_data.current_puzzle.pieces or []
        seen: set[str] = set()
        self._tray_types: list[MarginPiece] = []
        for p in raw_pieces:
            if p.piece_id not in seen:
                seen.add(p.piece_id)
                self._tray_types.append(p)

        # Pieces currently placed on the grid.
        self._placed_pieces: list[MarginPiece] = []
        # The piece currently being dragged (None when idle).
        self._dragging_piece: MarginPiece | None = None
        # Pixel offset from the piece's top-left to the mouse click point.
        self._drag_mouse_offset: tuple[int, int] = (0, 0)
        # Current top-left pixel position of the dragged piece.
        self._drag_pixel_pos: tuple[int, int] = (0, 0)
        # Original grid cells saved when lifting a piece from the grid.
        self._drag_origin_cells: set = set()
        # Grid cells the dragged piece would occupy at the current mouse position.
        self._hover_cells: set = set()
        # True when piece is floating after a click (no mouse held).
        self._click_mode: bool = False
        # Mouse position at the moment the piece was picked up (for click detection).
        self._mouse_down_pos: tuple[int, int] = (0, 0)
        # Set True during a level-advance transition; triggers tray rebuild when done.
        self._level_advance_pending: bool = False
        # Level whose completion message should be stamped onto its snapshot
        # once the current transition's reveal effect finishes.
        self._pending_complete_text_level: int | None = None
        # When True, the transition currently playing is the final-level
        # completion — once it finishes, land on COMPLETE instead of
        # INTERACTIVE so the dark overlay + ok button show up.
        self._pending_complete_mode: bool = False
        # Screen-space rects for each tray slot — fixed, never rebuilt.
        self._tray_rects: list[pygame.Rect] = []
        # Cached scaled-down images, one per tray slot, rebuilt alongside rects.
        self._tray_images: list[pygame.Surface] = []
        self._rebuild_tray_rects()

        # ── nav buttons ──
        self.nav_buttons = [
            AnimatedButton(
                surface=self.screen,
                next_state="menu",
                animation=Assets.animations.menu_icon,
                x=BORDER, y=BORDER,
                hover_transforms=[scale_hover(1.1)],
            ),
            AnimatedButton(
                surface=self.screen,
                next_state="archive",
                animation=Assets.animations.archive_icon,
                x=SCREEN_WIDTH - 64, y=BORDER,
                hover_transforms=[scale_hover(1.1)],
            ),
        ]

        # Page-flip review buttons (< prev / next >)
        self.prev_page_btn = Button(
            surface=self.screen,
            next_state="prev_page",
            x=PAGE_LEFT_POS[0], y=SCREEN_HEIGHT - 60,
            width=80, height=35,
            text="< prev",
        )
        self.next_page_btn = Button(
            surface=self.screen,
            next_state="next_page",
            x=PAGE_RIGHT_POS[0] + PAGE_W - 80, y=SCREEN_HEIGHT - 60,
            width=80, height=35,
            text="next >",
        )

        self.submit_button = AnimatedButton(
            surface=self.screen,
            next_state="submit",
            animation=Assets.animations.default_button,
            x=SCREEN_WIDTH // 2 -100, y=SCREEN_HEIGHT - 50,
            width=200, height=40,
            text="submit solution",
            hover_transforms=[tint_hover((5, 5, 5)), scale_hover(1.1)],
        )

        self.dark_overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        self.dark_overlay.fill((0, 0, 0, 128))

        self.ok_button = AnimatedButton(
            surface=self.screen,
            next_state="ok",
            animation=Assets.animations.default_button,
            x=SCREEN_WIDTH // 2 -100, y=SCREEN_HEIGHT // 2 - 50,
            width=200, height=40,
            text="ok",
            hover_transforms=[tint_hover((5, 5, 5)), scale_hover(1.1)],
        )

        # Kick off the opening text-reveal for level 0
        self._start_level_intro()

    # ── public loop interface ────────────────────────────────────────────────

    def update(self) -> str | None:
        # Advance all running effects; switch back to INTERACTIVE (or
        # COMPLETE, for the final level) when done
        if self.mode == ScribeMode.TRANSITION:
            if all(e.done for e in self.active_effects):
                self.active_effects.clear()
                if self._pending_complete_mode:
                    self.mode = ScribeMode.COMPLETE
                    self._pending_complete_mode = False
                else:
                    self.mode = ScribeMode.INTERACTIVE
                if self._pending_complete_text_level is not None:
                    self._stamp_complete_text(self._pending_complete_text_level)
                    self._pending_complete_text_level = None
                if self._level_advance_pending:
                    self._on_level_loaded()
                    self._level_advance_pending = False

        for event in self._poll_events():
            result = self._handle_event(event)
            if result:
                pygame.mouse.set_visible(True)
                return result
        return None

    def render(self):
        self.screen.blit(self.background, (0, 0))
        self._draw_book()
        self._draw_pages()
        self._draw_page_text()
        self._draw_grid()
        self._draw_placed_pieces()
        self._draw_effects()           # transition effects on top of static content
        self._draw_dragging_piece()    # always on top
        self._draw_margin_pieces_options()
        self._draw_ui()

        if self.mode == ScribeMode.COMPLETE:
            self.screen.blit(self.dark_overlay, (0, 0))
            for line, pos in _layout_text_block(COMPLETE_MESSAGE, COMPLETE_MESSAGE_BOX, FONT):
                if line:
                    label = FONT.render(line, True, COMPLETE_MESSAGE_COLOUR)
                    self.screen.blit(label, pos)
            self.ok_button.draw()

        # xl, yl = PAGE_TEXT_LEFT
        # xr, yr = PAGE_TEXT_RIGHT
        # width, height = PAGE_TEXT_BOX_SIZE

        # pygame.draw.rect(self.screen, (180, 165, 130), (xl, yl, width, height), 2)
        # pygame.draw.rect(self.screen, (180, 165, 130), (xr, yr, width, height), 2)

        #self.screen.blit(rect_surf, (xl, yl))
        #self.screen.blit(rect_surf, (xr, yr),  pygame.draw.rect(self.screen, (180, 165, 130), (xr, yr, width, height), 2))


        pygame.mouse.set_visible(False)
        mx, my = pygame.mouse.get_pos()
        self.screen.blit(self._cursor_img, (mx-2, my-150))

    # ── event handling ───────────────────────────────────────────────────────

    def _poll_events(self):
        for event in pygame.event.get():
            yield event

    def _handle_event(self, event) -> str | None:
        if event.type == pygame.QUIT:
            return "quit"

        # Nav buttons always active
        clicked = get_clicked_button(event, self._current_clickables())
        if clicked:
            clicked.play_sound()
            return self._dispatch(clicked.action())

        # Input-gated interactions
        if self.mode == ScribeMode.INTERACTIVE:
            self._handle_drag(event)

        return None

    def _prev_flip_target(self) -> int | None:
        """Level to land on if 'prev page' is clicked, or None if there's no
        earlier spread to flip back to (two levels share one visible spread,
        so this always jumps by a full spread — see _next_flip_target)."""
        new_level = self.viewed_level - 2
        return new_level if new_level >= 0 else None

    def _next_flip_target(self) -> int | None:
        """Level to land on if 'next page' is clicked, or None if there's no
        later spread unlocked yet."""
        max_unlocked = max(game_data.level_snapshots.keys(), default=-1)
        max_page = max(max_unlocked, game_data.current_level)
        new_level = self.viewed_level + 2
        return new_level if new_level <= max_page else None

    def _current_clickables(self) -> list:
        btns = list(self.nav_buttons)
        # Page-flip buttons only shown when clicking them would actually
        # flip to a different spread — not just switch focus within the
        # currently-open one (both its pages are already on screen).
        if self.mode != ScribeMode.TRANSITION:
            if self._prev_flip_target() is not None:
                btns.append(self.prev_page_btn)
            if self._next_flip_target() is not None:
                btns.append(self.next_page_btn)
        # Submit only when on current level page and interactive
        if (self.mode == ScribeMode.INTERACTIVE
                and self.viewed_level == game_data.current_level):
            btns.append(self.submit_button)
        if (self.mode == ScribeMode.COMPLETE
                and self.viewed_level == game_data.current_level):
            btns.append(self.ok_button)
        return btns

    def _dispatch(self, action: str) -> str | None:
        if action in ("menu", "archive", "ok") and self.mode == ScribeMode.COMPLETE:
            # Leaving the celebratory overlay (however the player leaves —
            # "ok", or straight to a nav icon) — settle onto a normal mode
            # now so the scene isn't stuck showing it next time it's visited.
            self._go_to_page(self.viewed_level)
        if action == "menu":
            return "menu"
        if action == "archive":
            return "archive"
        if action == "submit":
            self._on_submit()
        elif action == "ok":
            return "archive"
        elif action == "prev_page":
            new_level = self._prev_flip_target()
            if new_level is not None:
                Assets.sounds.page_turning.play()
                self._go_to_page(new_level)
        elif action == "next_page":
            new_level = self._next_flip_target()
            if new_level is not None:
                Assets.sounds.page_turning.play()
                self._go_to_page(new_level)
        return None

    # ── submission logic ─────────────────────────────────────────────────────

    def _on_submit(self):
        is_correct = game_data.current_puzzle.is_correct()

        result, points = game_data.submit_result(is_correct)
        if is_correct:
            Assets.sounds.confirm.play()
        else:
            Assets.sounds.drownshock.play()

        if result == SubmitResult.CORRECT_ADVANCE:
            # game_data has already advanced current_level
            self._start_level_advance_transition(prev_level=game_data.current_level - 1)

        elif result == SubmitResult.CORRECT_FINAL:
            level = game_data.current_level
            self._book_snapshots[level] = self._capture_book_page(game_data.current_puzzle)
            self._start_hint_fade(level)
            self.active_effects.append(self._make_complete_text_effect(level))
            self._pending_complete_text_level = level
            self._pending_complete_mode = True
            self._tray_types  = []
            self._tray_rects  = []
            self._tray_images = []

        elif result == SubmitResult.INCORRECT_STAGE:
            # Hint stage advanced — cross-fade the hint image
            self._start_hint_fade(game_data.current_level)

        elif result == SubmitResult.INCORRECT_MAXED:
            # Already on last hint; tiny points, just re-fade same image
            self._start_hint_fade(game_data.current_level)

    # ── transition builders ──────────────────────────────────────────────────

    def _complete_text_and_font(self, level: int) -> tuple:
        """(text, font) for a finished level's completion message."""
        puzzle = self._puzzle_for(level)
        text = (puzzle.level_complete_text if puzzle and puzzle.level_complete_text
                else f"Level {level + 1} Complete")
        font_size = LEVEL_COMPLETE_FONT_SIZE
        font = pygame.font.Font(os.path.join(UI_PATH, "pixelfont.ttf"), font_size)
        return text, font

    def _complete_text_box(self, level: int) -> tuple:
        """(x, y, w, h) box the completion message centres itself within,
        anchored to whichever side (left/right) that level's page is on."""
        side = "left" if level % 2 == 0 else "right"
        page_x = PAGE_TEXT_LEFT[0] if side == "left" else PAGE_TEXT_RIGHT[0]
        return (page_x, PAGE_TEXT_LEFT[1], PAGE_TEXT_BOX_SIZE[0], PAGE_TEXT_BOX_SIZE[1])

    def _make_complete_text_effect(self, level: int) -> "_TextFadeInEffect":
        """Build the letter-by-letter completion message for a finished level."""
        text, font = self._complete_text_and_font(level)
        box = self._complete_text_box(level)
        return _TextFadeInEffect(text, box, font, LEVEL_COMPLETE_FONT_COLOR, len(text) // LEVEL_COMPLETE_TEXT_SPEED )

    def _stamp_complete_text(self, level: int):
        """Permanently draw the (now fully revealed) completion message onto
        that level's frozen page snapshot, so it persists after the reveal
        transition ends — visible any time that page is viewed again."""
        surf = self._book_snapshots.get(level)
        if surf is None:
            return
        text, font = self._complete_text_and_font(level)
        box_x, box_y, box_w, box_h = self._complete_text_box(level)
        page_origin = PAGE_LEFT_POS if level % 2 == 0 else PAGE_RIGHT_POS
        local_box = (box_x - page_origin[0], box_y - page_origin[1], box_w, box_h)
        for line, pos in _layout_text_block(text, local_box, font):
            if line:
                label = font.render(line, True, LEVEL_COMPLETE_FONT_COLOR)
                surf.blit(label, pos)

    def _start_level_intro(self):
        """Run at scene init: text reveal on the first page only."""
        self.mode = ScribeMode.TRANSITION
        intro_text = "Chapter I"   # replace with real narrative text
        side = game_data.current_side
        pos  = HINT_PAGE_LEFT_POS if side == "left" else HINT_PAGE_RIGHT_POS
        text_pos = (pos[0] + 10, pos[1] + 10)
        self.active_effects = [
            _TextRevealEffect(intro_text, text_pos, FONT, (60, 40, 20)),
            _DropEffect(self._get_hint_surf(game_data.current_level),
                        pos[0], pos[1]),
        ]

    def _start_hint_fade(self, level: int):
        """Cross-fade to the updated hint image (same-level stage update)."""
        self.mode = ScribeMode.TRANSITION
        side   = game_data.current_side
        pos    = HINT_PAGE_LEFT_POS if side == "left" else HINT_PAGE_RIGHT_POS

        old_surf = self._get_hint_surf(level)
        # Invalidate cache so the new stage's image is built
        self._hint_surfs.pop(level, None)
        new_surf = self._get_hint_surf(level)

        self.active_effects = [_FadeEffect(old_surf, new_surf, pos)]

    def _capture_book_page(self, puzzle: "PuzzleData | None") -> pygame.Surface:
        """Render the given puzzle's grid and currently placed pieces to an off-screen surface."""
        surf = pygame.Surface((PAGE_W, PAGE_H), pygame.SRCALPHA)
        if not puzzle:
            return surf
        gx, gy = GRID_OFFSET
        puzzle.grid.draw(surf, gx, gy, BASE_TILE_SIZE)
        for piece in self._placed_pieces:
            surf.blit(piece.display_image, (gx + piece.x, gy + piece.y))
        return surf

    def _start_level_advance_transition(self, prev_level: int):
        """
        Freeze the just-completed page and play its completion message over
        it. The next level is revealed once the message finishes — see
        _on_level_loaded, which is called from update() when the transition
        completes.

        prev_level : the level that was just completed
        """
        self.mode = ScribeMode.TRANSITION

        # Freeze the completed book page (grid + pieces) before resetting.
        # current_puzzle has already advanced past prev_level by this point,
        # so pull the just-completed puzzle from level_snapshots instead.
        prev_puzzle = game_data.level_snapshots.get(prev_level)
        self._book_snapshots[prev_level] = self._capture_book_page(prev_puzzle)

        self.active_effects = [self._make_complete_text_effect(prev_level)]
        self._pending_complete_text_level = prev_level
        self._level_advance_pending = True

    def _book_complete(self) -> bool:
        """True once the final level has been solved — nothing left to place
        anywhere in the book, so every page (including the last) is
        view/flip-only from here on."""
        return (game_data.num_levels - 1) in game_data.level_snapshots

    def _go_to_page(self, level: int):
        """Switch to review/interactive mode for a different page."""
        if level != game_data.current_level and self._dragging_piece is not None:
            # Leaving the active page mid-drag — cancel it rather than let
            # the floating piece follow the mouse onto a page it can't act on.
            self._dragging_piece    = None
            self._drag_origin_cells = set()
            self._click_mode        = False
            self._hover_cells.clear()
            self._update_grid_hover()
        self.viewed_level = level
        if level == game_data.current_level and not self._book_complete():
            self.mode = ScribeMode.INTERACTIVE
        else:
            self.mode = ScribeMode.REVIEW

    def _puzzle_for(self, level: int) -> "PuzzleData | None":
        """The puzzle data behind a given level: live if it's the active level, else its snapshot."""
        if level == game_data.current_level:
            return game_data.current_puzzle
        return game_data.level_snapshots.get(level)

    # ── hint surface cache ───────────────────────────────────────────────────

    def _get_hint_surf(self, level: int) -> pygame.Surface:
        """
        Return a PAGE_W × PAGE_H surface showing the current hint for a level.
        Uses the snapshot puzzle for completed levels and live puzzle for current.
        """
        if level in self._hint_surfs:
            return self._hint_surfs[level]

        surf = pygame.Surface((HINT_PAGE_W, HINT_PAGE_H), pygame.SRCALPHA)
        # surf.fill((245, 235, 200, 255))

        puzzle = self._puzzle_for(level)

        if puzzle and puzzle.hints:
            stage_idx  = min(puzzle.stage, len(puzzle.hints) - 1)
            hint_anim: Animation = puzzle.hints[stage_idx]
            if hint_anim:
                hint_img = hint_anim.current_frame.image
                scaled   = pygame.transform.scale(hint_img, (HINT_PAGE_W, HINT_PAGE_H))
                surf.blit(scaled, (0, 0))

        self._hint_surfs[level] = surf
        return surf

    # ── drawing ──────────────────────────────────────────────────────────────

    def _draw_book(self):
        book = Assets.animations.book.current_frame.image
        self.screen.blit(book, BOOK_POS)
        # Overlay snapshots belonging to the currently open spread only —
        # a page turn retires the previous spread's pages from view until
        # the player pages back to review them.
        current_spread = self.viewed_level // 2
        for level, surf in self._book_snapshots.items():
            if level // 2 != current_spread:
                continue
            side = "left" if level % 2 == 0 else "right"
            pos = PAGE_LEFT_POS if side == "left" else PAGE_RIGHT_POS
            self.screen.blit(surf, pos)

    def _draw_pages(self):
        """Draw static hint pages. During transitions effects handle all drawing."""
        if self.mode == ScribeMode.TRANSITION:
            return
        for level, pos in self._visible_page_positions():
            self.screen.blit(self._get_hint_surf(level), pos)

    def _visible_page_positions(self) -> list[tuple[int, tuple]]:
        """
        Return [(level, pos)] for the hint pages currently visible.
        Only the active level's hint floats outside the book;
        completed levels' pages are shown inside the book as snapshots.
        """
        level = game_data.current_level
        side  = "left" if level % 2 == 0 else "right"
        pos   = HINT_PAGE_LEFT_POS if side == "left" else HINT_PAGE_RIGHT_POS
        return [(level, pos)]

    def _draw_effects(self):
        for effect in self.active_effects:
            effect.update(self.screen)

    def _draw_ui(self):
        # Nav buttons
        for btn in self.nav_buttons:
            btn.draw()

        # Page-flip buttons
        if self.mode != ScribeMode.TRANSITION:
            if self._prev_flip_target() is not None:
                self.prev_page_btn.draw()
            if self._next_flip_target() is not None:
                self.next_page_btn.draw()

        # Submit button only on active puzzle page
        if (self.mode == ScribeMode.INTERACTIVE
                and self.viewed_level == game_data.current_level):
            self.submit_button.draw()

        # Info labels
        draw_label(self, BORDER, SCREEN_HEIGHT - 30,
                   f"Trust: {game_data.total_trust_points}", None)
        draw_label(self, SCREEN_WIDTH // 2 - 40, BORDER + 2,
                   f"Level {self.viewed_level + 1}", None)

        # Rotation hint — piece rotation unlocks from the second level onward
        if self.mode == ScribeMode.INTERACTIVE and game_data.current_level >= 1:
            draw_label(self, SCREEN_WIDTH - 80, PAGE_RIGHT_POS[1] + PAGE_H - 70,
                       "rotate", None)
            draw_label(self, SCREEN_WIDTH - 50, PAGE_RIGHT_POS[1] + PAGE_H - 50,
                                   "< >", None)

        mode_text = {
            ScribeMode.INTERACTIVE: "",
            ScribeMode.TRANSITION:  "[transition]",
            ScribeMode.REVIEW:      "[viewing old page]",
        }.get(self.mode, "")
        if mode_text:
            draw_label(self, SCREEN_WIDTH // 2 - 60, BORDER + 24, mode_text, None)

        
    # ── drag helpers ─────────────────────────────────────────────────────────

    def _grid_origin(self) -> tuple[int, int]:
        """Screen-pixel top-left of the active puzzle grid."""
        px, py = PAGE_LEFT_POS if game_data.current_side == "left" else PAGE_RIGHT_POS
        return px + GRID_OFFSET[0], py + GRID_OFFSET[1]

    def _on_level_loaded(self):
        """Reset scene state to match the current level after a level advance."""
        self.viewed_level = game_data.current_level
        raw_pieces = game_data.current_puzzle.pieces or []
        seen: set[str] = set()
        self._tray_types = []
        for p in raw_pieces:
            if p.piece_id not in seen:
                seen.add(p.piece_id)
                self._tray_types.append(p)
        self._rebuild_tray_rects()
        self._placed_pieces = []
        self._dragging_piece = None
        self._hover_cells = set()
        self._drag_origin_cells = set()
        self._click_mode = False
        # Clear hint cache for the new level so it's rebuilt fresh
        self._hint_surfs.pop(game_data.current_level, None)

    def _rebuild_tray_rects(self):
        """Compute fixed screen rects and cached thumbnails for the type palette."""
        n = len(self._tray_types)
        total_w = n * TRAY_SPACING
        start_x = SCREEN_WIDTH // 2 - total_w // 2
        self._tray_images = [
            _scale_to_fit(piece.display_image, TRAY_PIECE_SIZE)
            for piece in self._tray_types
        ]
        self._tray_rects = [
            pygame.Rect(
                start_x + i * TRAY_SPACING, TRAY_Y,
                *self._tray_images[i].get_size()
            )
            for i in range(n)
        ]

    def _snap_col_row(self, pixel_x: int, pixel_y: int) -> tuple[int, int]:
        """Convert a pixel position to the nearest grid (col, row)."""
        ox, oy = self._grid_origin()
        return round((pixel_x - ox) / BASE_TILE_SIZE), round((pixel_y - oy) / BASE_TILE_SIZE)

    def _piece_cells_at(self, piece: MarginPiece, snap_col: int, snap_row: int) -> set:
        """Translate piece.pixels to absolute grid coords at a snap position."""
        return {(col + snap_col, row + snap_row) for col, row in piece.pixels}

    def _update_grid_hover(self):
        """Apply HOVER state to cells under the dragged piece; clear elsewhere."""
        grid = game_data.current_puzzle.grid
        # Clear old hover cells
        for row in range(grid.height):
            for col in range(grid.width):
                if grid.cells[row][col] == CellState.HOVER:
                    grid.cells[row][col] = CellState.EMPTY
        # Set new hover cells
        for col, row in self._hover_cells:
            if 0 <= col < grid.width and 0 <= row < grid.height:
                if grid.cells[row][col] == CellState.EMPTY:
                    grid.cells[row][col] = CellState.HOVER

    # ── drag event handler ────────────────────────────────────────────────────

    def _drop_piece(self, grid, snap_col: int, snap_row: int):
        """Attempt to place the floating piece; discard it if invalid. Clears drag state."""
        cells = self._piece_cells_at(self._dragging_piece, snap_col, snap_row)
        if grid.can_place(cells):
            self._dragging_piece.x = snap_col * BASE_TILE_SIZE
            self._dragging_piece.y = snap_row * BASE_TILE_SIZE
            grid.place(cells, self._dragging_piece)
            Assets.sounds.draw_piece.play()
            self._placed_pieces.append(self._dragging_piece)
        # Invalid drop → piece disappears regardless of origin
        self._hover_cells.clear()
        self._update_grid_hover()
        self._dragging_piece    = None
        self._drag_origin_cells = set()
        self._click_mode        = False

    def _handle_drag(self, event):
        """Full drag-and-drop handler. Called only when mode == INTERACTIVE."""
        puzzle = game_data.current_puzzle
        grid   = puzzle.grid

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos

            # Piece is floating in click mode → this click places it
            if self._dragging_piece is not None and self._click_mode:
                px, py = self._drag_pixel_pos
                snap_col, snap_row = self._snap_col_row(px, py)
                self._drop_piece(grid, snap_col, snap_row)
                return

            # 1. Check tray type palette
            for i, rect in enumerate(self._tray_rects):
                if rect.collidepoint(mx, my):
                    prototype = self._tray_types[i]
                    self._dragging_piece    = MarginPiece(prototype.piece_id, prototype.x, prototype.y, TRAY_PIECE_SIZE)
                    self._drag_mouse_offset = (mx - rect.x, my - rect.y)
                    self._drag_pixel_pos    = (rect.x, rect.y)
                    self._drag_origin_cells = set()
                    self._click_mode        = False
                    self._mouse_down_pos    = (mx, my)
                    Assets.sounds.pickup_art.play()
                    return

            # 2. Lift a piece already placed on the grid
            ox, oy = self._grid_origin()
            col = (mx - ox) // BASE_TILE_SIZE
            row = (my - oy) // BASE_TILE_SIZE
            if 0 <= col < grid.width and 0 <= row < grid.height:
                piece = grid.cell_contents[row][col]
                if piece is not None:
                    self._drag_origin_cells = grid.cells_of_piece(piece)
                    px = ox + piece.x
                    py = oy + piece.y
                    grid.remove_piece(piece)
                    self._placed_pieces.remove(piece)
                    self._dragging_piece    = piece
                    self._drag_mouse_offset = (mx - px, my - py)
                    self._drag_pixel_pos    = (px, py)
                    self._click_mode        = False
                    self._mouse_down_pos    = (mx, my)

        elif event.type == pygame.MOUSEMOTION and self._dragging_piece:
            mx, my = event.pos
            dx, dy = self._drag_mouse_offset
            self._drag_pixel_pos = (mx - dx, my - dy)
            snap_col, snap_row = self._snap_col_row(mx - dx, my - dy)
            self._hover_cells = self._piece_cells_at(self._dragging_piece, snap_col, snap_row)
            self._update_grid_hover()

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self._dragging_piece and not self._click_mode:
            mx, my = event.pos
            mdx = mx - self._mouse_down_pos[0]
            mdy = my - self._mouse_down_pos[1]
            if mdx * mdx + mdy * mdy < 36:
                # Barely moved — treat as a click, keep piece floating
                self._click_mode = True
                return
            # Held and dragged — drop on release
            dx, dy = self._drag_mouse_offset
            snap_col, snap_row = self._snap_col_row(mx - dx, my - dy)
            self._drop_piece(grid, snap_col, snap_row)

        elif (event.type == pygame.KEYDOWN and self._dragging_piece is not None
              and game_data.current_level >= 1
              and event.key in (pygame.K_LEFT, pygame.K_RIGHT)):
            self._dragging_piece.rotate(clockwise=(event.key == pygame.K_RIGHT))
            px, py = self._drag_pixel_pos
            snap_col, snap_row = self._snap_col_row(px, py)
            self._hover_cells = self._piece_cells_at(self._dragging_piece, snap_col, snap_row)
            self._update_grid_hover()

    # ── drawing ──────────────────────────────────────────────────────────────

    def _draw_page_text(self):
        """Render each visible page's page_text centred in its own header."""
        spread_start = (self.viewed_level // 2) * 2
        for level in (spread_start, spread_start + 1):
            puzzle = self._puzzle_for(level)
            if puzzle is None or not puzzle.page_text:
                continue
            side = "left" if level % 2 == 0 else "right"
            px, py = PAGE_LEFT_POS if side == "left" else PAGE_RIGHT_POS
            # Centre the label horizontally within the page, vertically within the
            # header gap created by GRID_OFFSET[1].
            header_mid_y = py + GRID_OFFSET[1] // 2
            label = FONT.render(puzzle.page_text, True, (60, 35, 10))
            self.screen.blit(label, (px + PAGE_W // 2 - label.get_width() // 2, header_mid_y - label.get_height() // 2))

    def _draw_grid(self):
        """Draw the live grid overlay — only while the active page is the one on screen."""
        if self.mode != ScribeMode.INTERACTIVE:
            return
        puzzle = game_data.current_puzzle
        if puzzle is None:
            return
        ox, oy = self._grid_origin()
        puzzle.grid.draw(self.screen, ox, oy, BASE_TILE_SIZE)

        # Highlight hover cells on the grid with validity-based colour
        if self._hover_cells:
            valid  = puzzle.grid.can_place(self._hover_cells)
            colour = _COL_VALID if valid else _COL_INVALID
            cell_surf = pygame.Surface((BASE_TILE_SIZE, BASE_TILE_SIZE), pygame.SRCALPHA)
            cell_surf.fill(colour)
            for col, row in self._hover_cells:
                self.screen.blit(cell_surf, (ox + col * BASE_TILE_SIZE, oy + row * BASE_TILE_SIZE))

    def _draw_placed_pieces(self):
        """Draw pieces placed on the live grid — only while its page is on screen."""
        if self.mode != ScribeMode.INTERACTIVE:
            return
        ox, oy = self._grid_origin()
        for piece in self._placed_pieces:
            self.screen.blit(piece.display_image, (ox + piece.x, oy + piece.y))

    def _draw_dragging_piece(self):
        """Draw the piece currently being dragged, following the mouse."""
        if self._dragging_piece is None or self.mode != ScribeMode.INTERACTIVE:
            return
        piece = self._dragging_piece
        x, y  = self._drag_pixel_pos
        img = piece.display_image.copy()
        img.set_alpha(180)
        self.screen.blit(img, (x, y))

    def _draw_margin_pieces_options(self):
        """Draw the type palette — only while the active page is the one on screen."""
        if self.mode != ScribeMode.INTERACTIVE or not self._tray_types:
            return
        for scaled_image, rect in zip(self._tray_images, self._tray_rects):
            pygame.draw.rect(self.screen, (180, 165, 130), rect, 2)
            self.screen.blit(scaled_image, rect.topleft)