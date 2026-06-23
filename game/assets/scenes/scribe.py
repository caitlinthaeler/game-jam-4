"""
ScribeScene
===========
Manages the prayer-book UI where the player drags margin-pieces onto the grid.

Layout
------
  Left page  → even-numbered levels  (0, 2, 4 …)
  Right page → odd-numbered  levels  (1, 3, 5 …)
  A physical page-turn happens when advancing to an even level > 0,
  because both visible pages are then full.

Modes
-----
  INTERACTIVE  – player can drag/drop (only on the current-level page)
  TRANSITION   – all input locked; one or more effects are running
  REVIEW       – player is browsing an old page; drag/drop disabled

Effects (run in parallel inside TRANSITION mode)
-------------------------------------------------
  Each effect is a small object updated every frame via update() → bool(done).
  When ALL active effects are done, mode reverts to INTERACTIVE.
"""

import pygame
from enum import Enum, auto

from scene_manager import Scene
from assets_registry import Assets, Animation, MarginPiece
from classes import (
    AnimatedButton, Button, get_clicked_button,
    scale_hover, tint_hover, format_background, draw_label,
    Grid, CellState,
)
from config import BORDER, SCREEN_WIDTH, SCREEN_HEIGHT, FONT, BASE_TILE_SIZE, SPRITES_DIR
from game_manager import game_data, SubmitResult

# ── layout constants ────────────────────────────────────────────────────────

PAGE_W, PAGE_H = 240, 320          # in-book page slot dimensions (grid area)
HINT_PAGE_W, HINT_PAGE_H = 24*5, 32*5  # floating hint page outside the book
# Book is 2×PAGE_W wide; centre it on screen.
BOOK_POS       = (SCREEN_WIDTH//2 - 250, 80)
# Left page occupies the left half of the book; right page the right half.
PAGE_LEFT_POS  = (BOOK_POS[0],          BOOK_POS[1])
PAGE_RIGHT_POS = (BOOK_POS[0] + PAGE_W, BOOK_POS[1])
HINT_PAGE_LEFT_POS = (20, BOOK_POS[1]+(PAGE_H // 2 - HINT_PAGE_H // 2))
HINT_PAGE_RIGHT_POS = (BOOK_POS[0]+(PAGE_W*2)+20, BOOK_POS[1]+(PAGE_H // 2 - HINT_PAGE_H // 2))
HINT_FADE_SPEED  = 8               # alpha units per frame
SLIDE_SPEED      = 7               # pixels per frame
PAGE_TURN_FRAMES = 40              # frames for the page-turn flash

# ── drag / tray constants ───────────────────────────────────────────────────
# Grid is drawn inset from the page origin by this many pixels.
GRID_OFFSET      = (0, 0)
# Piece tray sits below the book area.
TRAY_Y           = BOOK_POS[1] + PAGE_H + 20
TRAY_PIECE_SIZE  = 32              # display size of each tray thumbnail (px)
TRAY_SPACING     = 150              # centre-to-centre horizontal gap in tray
# Tint colours for drag feedback
_COL_VALID   = (130, 200, 130, 160)
_COL_INVALID = (220, 60,  60,  160)


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


class _SlideOutEffect:
    """Slides a surface off-screen left (if side=='left') or right."""
    def __init__(self, surface: pygame.Surface, x: int, y: int, side: str, speed: int = SLIDE_SPEED):
        self.surf  = surface
        self.x     = float(x)
        self.y     = y
        self.side  = side
        self.speed = speed
        self.done  = False

    def update(self, screen: pygame.Surface):
        if self.done:
            return
        if self.side == "left":
            self.x -= self.speed
            screen.blit(self.surf, (int(self.x), self.y))
            if self.x + self.surf.get_width() < 0:
                self.done = True
        else:
            self.x += self.speed
            screen.blit(self.surf, (int(self.x), self.y))
            if self.x > SCREEN_WIDTH:
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


class _PageTurnEffect:
    """Simple flash-white overlay that simulates a page turn."""
    def __init__(self, total_frames: int = PAGE_TURN_FRAMES):
        self.frame  = 0
        self.total  = total_frames
        self.done   = False
        self._overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        self._overlay.fill((245, 235, 200))

    def update(self, screen: pygame.Surface):
        if self.done:
            return
        self.frame += 1
        # fade in then out
        half = self.total // 2
        alpha = int(255 * self.frame / half) if self.frame <= half else int(255 * (self.total - self.frame) / half)
        self._overlay.set_alpha(max(0, min(255, alpha)))
        screen.blit(self._overlay, (0, 0))
        if self.frame >= self.total:
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


# ── scene modes ─────────────────────────────────────────────────────────────

class ScribeMode(Enum):
    INTERACTIVE = auto()   # player can drag/drop on current-level page
    TRANSITION  = auto()   # effects running; all input locked
    REVIEW      = auto()   # browsing old pages; no drag/drop


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
        # Screen-space rects for each tray slot — fixed, never rebuilt.
        self._tray_rects: list[pygame.Rect] = []
        self._rebuild_tray_rects()

        # ── nav buttons ──
        self.nav_buttons = [
            AnimatedButton(
                surface=self.screen,
                next_state="menu",
                animation=Assets.animations.menu_icon,
                x=BORDER, y=BORDER,
                text="menu",
                hover_transforms=[tint_hover((87, 0, 72)), scale_hover(1.1)],
            ),
            AnimatedButton(
                surface=self.screen,
                next_state="office",
                animation=Assets.animations.menu_icon,
                x=SCREEN_WIDTH - 200, y=BORDER,
                text="back",
                hover_transforms=[tint_hover((87, 0, 72)), scale_hover(1.1)],
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
            animation=Assets.animations.menu_icon,
            x=SCREEN_WIDTH // 2 - 100, y=SCREEN_HEIGHT - 80,
            width=200, height=55,
            text="submit solution",
            hover_transforms=[tint_hover((5, 5, 5)), scale_hover(1.1)],
        )

        # Kick off the opening text-reveal for level 0
        self._start_level_intro()

    # ── public loop interface ────────────────────────────────────────────────

    def update(self) -> str | None:
        # Advance all running effects; switch back to INTERACTIVE when done
        if self.mode == ScribeMode.TRANSITION:
            if all(e.done for e in self.active_effects):
                self.active_effects.clear()
                self.mode = ScribeMode.INTERACTIVE
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
        self._draw_grid()
        self._draw_placed_pieces()
        self._draw_effects()           # transition effects on top of static content
        self._draw_dragging_piece()    # always on top
        self._draw_margin_pieces_options()
        self._draw_ui()
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

    def _current_clickables(self) -> list:
        btns = list(self.nav_buttons)
        # Page-flip buttons always available unless mid-transition
        if self.mode != ScribeMode.TRANSITION:
            if self.viewed_level > 0:
                btns.append(self.prev_page_btn)
            max_unlocked = max(game_data.level_snapshots.keys(), default=-1)
            max_page = max(max_unlocked, game_data.current_level)
            if self.viewed_level < max_page:
                btns.append(self.next_page_btn)
        # Submit only when on current level page and interactive
        if (self.mode == ScribeMode.INTERACTIVE
                and self.viewed_level == game_data.current_level):
            btns.append(self.submit_button)
        return btns

    def _dispatch(self, action: str) -> str | None:
        if action == "menu":
            return "menu"
        if action == "office":
            return "office"
        if action == "submit":
            self._on_submit()
        elif action == "prev_page":
            self._go_to_page(self.viewed_level - 1)
        elif action == "next_page":
            max_unlocked = max(game_data.level_snapshots.keys(), default=-1)
            max_page = max(max_unlocked, game_data.current_level)
            if self.viewed_level < max_page:
                self._go_to_page(self.viewed_level + 1)
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
            # No more levels — stay on final page, show completion
            self._start_hint_fade(game_data.current_level)

        elif result == SubmitResult.INCORRECT_STAGE:
            # Hint stage advanced — cross-fade the hint image
            self._start_hint_fade(game_data.current_level)

        elif result == SubmitResult.INCORRECT_MAXED:
            # Already on last hint; tiny points, just re-fade same image
            self._start_hint_fade(game_data.current_level)

    # ── transition builders ──────────────────────────────────────────────────

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
        puzzle = game_data.current_puzzle
        side   = game_data.current_side
        pos    = HINT_PAGE_LEFT_POS if side == "left" else HINT_PAGE_RIGHT_POS

        old_surf = self._get_hint_surf(level)
        # Invalidate cache so the new stage's image is built
        self._hint_surfs.pop(level, None)
        new_surf = self._get_hint_surf(level)

        self.active_effects = [_FadeEffect(old_surf, new_surf, pos)]

    def _capture_book_page(self) -> pygame.Surface:
        """Render the current puzzle's grid and placed pieces to an off-screen surface."""
        surf = pygame.Surface((PAGE_W, PAGE_H), pygame.SRCALPHA)
        puzzle = game_data.current_puzzle
        if not puzzle:
            return surf
        gx, gy = GRID_OFFSET
        puzzle.grid.draw(surf, gx, gy, BASE_TILE_SIZE)
        for piece in self._placed_pieces:
            surf.blit(piece.display_image, (gx + piece.x, gy + piece.y))
        return surf

    def _start_level_advance_transition(self, prev_level: int):
        """
        Build the transition that plays when the player completes a level.

        prev_level : the level that was just completed
        new_level  : game_data.current_level (already advanced)
        """
        self.mode = ScribeMode.TRANSITION
        new_level   = game_data.current_level
        new_side    = game_data.current_side
        prev_side   = "left" if prev_level % 2 == 0 else "right"
        new_pos     = HINT_PAGE_LEFT_POS if new_side == "left" else HINT_PAGE_RIGHT_POS
        prev_pos    = HINT_PAGE_LEFT_POS if prev_side == "left" else HINT_PAGE_RIGHT_POS

        # Freeze the completed book page (grid + pieces) before resetting
        self._book_snapshots[prev_level] = self._capture_book_page()

        old_hint = self._get_hint_surf(prev_level)
        new_hint = self._get_hint_surf(new_level)

        effects = [
            # Slide the completed level's hint out of view
            _SlideOutEffect(old_hint, prev_pos[0], prev_pos[1], prev_side),
        ]

        if game_data.needs_page_turn:
            effects.append(_PageTurnEffect())

        # New hint drops in from top on the appropriate side
        effects.append(_DropEffect(new_hint, new_pos[0], new_pos[1]))

        text_pos = (new_pos[0] + 10, new_pos[1] + 10)
        effects.append(_TextRevealEffect(f"Chapter {new_level + 1}", text_pos, FONT, (60, 40, 20)))

        self.active_effects = effects
        self._level_advance_pending = True
        self.viewed_level = new_level

    def _go_to_page(self, level: int):
        """Switch to review/interactive mode for a different page."""
        self.viewed_level = level
        if level == game_data.current_level:
            self.mode = ScribeMode.INTERACTIVE
        else:
            self.mode = ScribeMode.REVIEW

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

        # Pick the right puzzle source
        if level == game_data.current_level:
            puzzle = game_data.current_puzzle
        else:
            puzzle = game_data.level_snapshots.get(level)

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
        # Overlay completed-level snapshots inside their respective book pages
        for level, surf in self._book_snapshots.items():
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
            if self.viewed_level > 0:
                self.prev_page_btn.draw()
            max_unlocked = max(game_data.level_snapshots.keys(), default=-1)
            max_page = max(max_unlocked, game_data.current_level)
            if self.viewed_level < max_page:
                self.next_page_btn.draw()

        # Submit button only on active puzzle page
        if (self.mode == ScribeMode.INTERACTIVE
                and self.viewed_level == game_data.current_level):
            self.submit_button.draw()

        # Info labels
        draw_label(self, BORDER, SCREEN_HEIGHT - 30,
                   f"Trust: {game_data.total_trust_points}", None)
        draw_label(self, SCREEN_WIDTH // 2 - 40, BORDER + 2,
                   f"Level {game_data.current_level + 1}", None)

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
        """Compute fixed screen rects for the type palette. Called once at init."""
        n = len(self._tray_types)
        total_w = n * TRAY_SPACING
        start_x = SCREEN_WIDTH // 2 - total_w // 2
        self._tray_rects = [
            pygame.Rect(
                start_x + i * TRAY_SPACING, TRAY_Y,
                *self._tray_types[i].display_image.get_size()
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
                    fresh = MarginPiece(prototype.piece_id)
                    self._dragging_piece    = fresh
                    self._drag_mouse_offset = (mx - rect.x, my - rect.y)
                    self._drag_pixel_pos    = (rect.x, rect.y)
                    self._drag_origin_cells = set()
                    self._click_mode        = False
                    self._mouse_down_pos    = (mx, my)
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

    # ── drawing ──────────────────────────────────────────────────────────────

    def _draw_grid(self):
        """Draw the grid overlay on the current puzzle page."""
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
        """Draw all pieces that have been placed on the grid."""
        ox, oy = self._grid_origin()
        for piece in self._placed_pieces:
            self.screen.blit(piece.display_image, (ox + piece.x, oy + piece.y))

    def _draw_dragging_piece(self):
        """Draw the piece currently being dragged, following the mouse."""
        if self._dragging_piece is None:
            return
        piece = self._dragging_piece
        x, y  = self._drag_pixel_pos
        img = piece.display_image.copy()
        img.set_alpha(180)
        self.screen.blit(img, (x, y))

    def _draw_margin_pieces_options(self):
        """Draw the type palette at the bottom of the screen."""
        if not self._tray_types:
            return
        for piece, rect in zip(self._tray_types, self._tray_rects):
            pygame.draw.rect(self.screen, (180, 165, 130), rect, 2)
            self.screen.blit(piece.display_image, rect.topleft)