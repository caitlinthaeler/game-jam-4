from __future__ import annotations
from config import FONT, SCREEN_WIDTH, SOUNDS_DIR, UI_PATH, FONT, BORDER, SCALE_FACTOR
from enum import Enum
import os
import pygame


class Button:
    default_button_height = 35
    default_button_width = 123
    default_sound = pygame.mixer.Sound(os.path.join(SOUNDS_DIR, "menu_selection.mp3"))
    default_sound.set_volume(0.8)

    def __init__(self, surface, next_state, x, y, text, font=FONT, text_colour=(20,20,20), width=default_button_width, height=default_button_height, sound=default_sound, enabled=True):
        self.screen = surface
        self.next_state = next_state # return value of clicking the button
        self.base_rect = pygame.Rect(x, y, width, height)
        self.rect = self.base_rect.copy() # copy, to be mutated
        self.text = text
        self.font = font
        self.text_colour = text_colour
        self.sound = sound
        self.enabled = enabled
        self.base_image = pygame.image.load(os.path.join(UI_PATH, "button2.png")).convert_alpha()
        self.background = pygame.transform.scale(self.base_image, self.rect.size)

    def draw(self):
        self.screen.blit(self.background, (self.rect.left, self.rect.top))
        label = self.font.render(self.text, True, self.text_colour)
        label_rect = label.get_rect(center=self.rect.center)
        if not self.enabled:
            overlay = pygame.Surface(self.rect.size, pygame.SRCALPHA)
            overlay.fill((128, 128, 128, 160))
            self.screen.blit(overlay, self.rect.topleft)
            self.screen.blit(label, label_rect)
            return
        if self.rect.collidepoint(pygame.mouse.get_pos()):
            self.on_hover()
        else:
            self.rect = self.base_rect
        self.background = pygame.transform.scale(self.base_image, self.rect.size)
        self.screen.blit(label, label_rect)

    def on_hover(self):
        self.rect = self.base_rect.inflate(5, 5)
        overlay = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        pygame.draw.rect(overlay, (87, 0, 72, 95), overlay.get_rect(), border_radius = 4)
        self.screen.blit(overlay, self.rect)

    def action(self):
        return self.next_state
    
    def play_sound(self):
        self.sound.play()

class BackButton(Button):
    def __init__(self, screen, previous_state):
        super().__init__(screen, previous_state, SCREEN_WIDTH-100-BORDER, BORDER, "Back", width=100)




class AnimatedButton:
    def __init__(self, surface, next_state,
                 animation: Animation,
                 x: int, y: int,
                 anchor: str = "topleft",
                 scale: float = SCALE_FACTOR,
                 width: int = None,
                 height: int = None,
                 hover_animation: Animation = None,
                 hover_inflate: tuple = (0, 0),
                 hover_transforms: list = None,
                 text: str = None,
                 font=FONT,
                 text_colour=(20, 20, 20),
                 text_offset: tuple = (0, 0),
                 sound=None):
        self.screen = surface
        self.next_state = next_state
        self.idle_animation = animation
        self.hover_animation = hover_animation
        self.scale = scale
        self.hover_inflate = hover_inflate
        self.hover_transforms = hover_transforms or []
        self.text = text
        self.font = font
        self.text_offset = text_offset
        self.text_colour = text_colour
        self.sound = sound or Button.default_sound

        nw, nh = animation.current_frame.image.get_size()
        w = width  if width  is not None else int(nw * scale)
        h = height if height is not None else int(nh * scale)
        self._custom_size = width is not None or height is not None
        self.base_rect = pygame.Rect(0, 0, w, h)
        setattr(self.base_rect, anchor, (x, y))
        self.rect = self.base_rect.copy()

    def draw(self):
        is_hovered = self.base_rect.collidepoint(pygame.mouse.get_pos())

        anim = self.hover_animation if (is_hovered and self.hover_animation) else self.idle_animation
        anim.update()

        if self._custom_size:
            image = pygame.transform.scale(anim.current_frame.image, self.base_rect.size)
        else:
            nw, nh = anim.current_frame.image.get_size()
            image = pygame.transform.scale(anim.current_frame.image, (int(nw * self.scale), int(nh * self.scale)))

        if is_hovered:
            for transform in self.hover_transforms:
                image = transform(image)

        self.rect = pygame.Rect(0, 0, *image.get_size())
        self.rect.center = self.base_rect.inflate(*self.hover_inflate).center if is_hovered else self.base_rect.center

        self.screen.blit(image, self.rect.topleft)

        if self.text:
            label = self.font.render(self.text, True, self.text_colour)
            label_rect = label.get_rect(center=(self.rect.centerx + self.text_offset[0], self.rect.centery + self.text_offset[1]))
            self.screen.blit(label, label_rect)
            self.rect = self.rect.union(label_rect)  # expand hit area to cover the label

    def set_animation(self, animation: object):
        self.idle_animation = animation

    def action(self):
        return self.next_state

    def play_sound(self):
        self.sound.play()


def scale_hover(factor: float):
    return lambda surf: pygame.transform.scale(
        surf, (int(surf.get_width() * factor), int(surf.get_height() * factor)))

def rotate_hover(angle: float):
    return lambda surf: pygame.transform.rotate(surf, angle)

def tint_hover(colour: tuple, alpha: int = 80):
    def _tint(surf):
        result = surf.copy()
        overlay = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        overlay.fill((*colour, alpha))
        result.blit(overlay, (0, 0))
        return result
    return _tint


def get_clicked_button(event, buttons):
    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        for button in buttons:
            if getattr(button, "enabled", True) and button.rect.collidepoint(event.pos):
                button.play_sound()
                return button
    return None
        

def format_background(screen: pygame.Surface, file_name: str):
    # load the background and scale it to fit the screen
    background_path = os.path.join(UI_PATH, file_name)
    background = pygame.image.load(background_path).convert()
    background = pygame.transform.scale(background, screen.get_size())
    return background


class CellState(Enum):
    INVALID = -1
    EMPTY = 0
    HOVER = 1
    FILLED = 2

class Grid:
    def __init__(self, width: int, height: int, valid_cells: set | None = None):
        """
        width, height : grid dimensions in cells.
        valid_cells   : optional set of (col, row) that are playable (EMPTY).
                        If None, every cell is EMPTY (fully rectangular grid).
        """
        self.width = width
        self.height = height
        # Start every cell as INVALID; then mark valid ones as EMPTY.
        self.cells = [[CellState.INVALID for _ in range(width)] for _ in range(height)]
        self.cell_contents = [[None for _ in range(width)] for _ in range(height)]
        if valid_cells is None:
            # All cells playable
            for row in range(height):
                for col in range(width):
                    self.cells[row][col] = CellState.EMPTY
        else:
            for col, row in valid_cells:
                if 0 <= col < width and 0 <= row < height:
                    self.cells[row][col] = CellState.EMPTY

    def set_cell(self, x: int, y: int, value: CellState):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.cells[y][x] = value

    def get_cell(self, x: int, y: int) -> CellState | None:
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.cells[y][x]
        return None

    def can_place(self, piece_cells: set) -> bool:
        """True if every cell in piece_cells is within bounds and currently EMPTY."""
        for col, row in piece_cells:
            if not (0 <= col < self.width and 0 <= row < self.height):
                return False
            if self.cells[row][col] not in (CellState.EMPTY, CellState.HOVER):
                return False
        return bool(piece_cells)  # empty set is not a valid placement

    def place(self, piece_cells: set, piece):
        """Mark cells as FILLED and record the piece object in cell_contents."""
        for col, row in piece_cells:
            self.cells[row][col] = CellState.FILLED
            self.cell_contents[row][col] = piece

    def remove_piece(self, piece):
        """Clear all cells that belong to the given piece."""
        for row in range(self.height):
            for col in range(self.width):
                if self.cell_contents[row][col] is piece:
                    self.cells[row][col] = CellState.EMPTY
                    self.cell_contents[row][col] = None

    def cells_of_piece(self, piece) -> set:
        """Return the (col, row) set currently occupied by a piece."""
        return {
            (col, row)
            for row in range(self.height)
            for col in range(self.width)
            if self.cell_contents[row][col] is piece
        }

    def get_valid_cells(self) -> set:
        """Return all (col, row) that are not INVALID."""
        return {
            (col, row)
            for row in range(self.height)
            for col in range(self.width)
            if self.cells[row][col] != CellState.INVALID
        }

    def draw(self, screen: pygame.Surface, origin_x: int, origin_y: int, cell_size: int):
        """Draw the grid overlay onto screen."""
        _COLOURS = {
            CellState.EMPTY:  (200, 190, 160),
            CellState.HOVER:  (130, 200, 130),
            CellState.FILLED: (100, 140, 100),
        }
        for row in range(self.height):
            for col in range(self.width):
                state = self.cells[row][col]
                if state == CellState.INVALID:
                    continue
                rect = pygame.Rect(
                    origin_x + col * cell_size,
                    origin_y + row * cell_size,
                    cell_size, cell_size,
                )
                colour = _COLOURS.get(state, (200, 190, 160))
                # Filled cells get a light fill; others just an outline
                if state == CellState.FILLED:
                    pygame.draw.rect(screen, colour, rect)
                pygame.draw.rect(screen, colour, rect)

    def reset(self):
        for row in range(self.height):
            for col in range(self.width):
                if self.cells[row][col] != CellState.INVALID:
                    self.cells[row][col] = CellState.EMPTY
                self.cell_contents[row][col] = None

    def _to_dict(self) -> dict:
        return {
            "width": self.width,
            "height": self.height,
            "cells": [[state.value for state in row] for row in self.cells],
            "cell_contents": [
                [
                    (self.cell_contents[r][c].piece_id
                     if self.cell_contents[r][c] is not None else None)
                    for c in range(self.width)
                ]
                for r in range(self.height)
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Grid:
        """Restore grid layout. cell_contents is left empty — caller re-places pieces."""
        g = cls(data["width"], data["height"], valid_cells=set())
        raw = data.get("cells", [])
        for r in range(g.height):
            for c in range(g.width):
                try:
                    g.cells[r][c] = CellState(raw[r][c])
                except (IndexError, ValueError):
                    g.cells[r][c] = CellState.INVALID
        return g

class PuzzleData:
    def __init__(self, level: int=0, stage: int=0, pieces: list=None,
                 hints: list=None, trust_points: list=None,
                 grid: "Grid | None" = None, solution: object=None):
        self.level = level
        self.stage = stage
        self.pieces: list = pieces or []   # available MarginPiece objects
        self.hints = hints                 # list of Animation per stage
        self.trust_points = trust_points   # list of int per stage
        self.grid: Grid = grid if isinstance(grid, Grid) else Grid(8, 10)
        self.solution = solution           # animation asset


    def next_stage(self):
        if self.stage < len(self.hints) - 1:
            self.stage += 1

    def clear_grid(self):
        self.grid.reset()

    def load(self, data: dict):
        self.stage = data.get("stage", 0)
        self.pieces = data.get("pieces", [])
        self.grid = data.get("grid", Grid)
        self.hints = data.get("hints", [None, None, None])
        self.solution = data.get("solution", [])

    def paste_piece(self, piece):
        self.pieces

    def strip_piece(self, piece):
        self.pieces.remove(piece)

    def is_correct(self) -> bool:
        return all(
            self.grid.cells[row][col] == CellState.FILLED
            for row in range(self.grid.height)
            for col in range(self.grid.width)
            if self.grid.cells[row][col] != CellState.INVALID
        )

    
        
    def is_overlapping(self, piece) -> bool:
        """True if the piece's current grid cells overlap any already-filled cell."""
        for col, row in piece.get_cells_at_position():
            if self.grid.get_cell(col, row) == CellState.FILLED:
                return True
        return False

    def valid_space(self, piece) -> bool:
        """True if every cell the piece occupies is within bounds and EMPTY."""
        return self.grid.can_place(piece.get_cells_at_position())

    def apply_grid_highlights(self, piece):
        pass

    def _to_dict(self) -> dict:
        # hints, pieces, and solution are asset objects — they're fully
        # re-created by the level factory on load, so we don't serialise them.
        return {
            "level": self.level,
            "stage": self.stage,
            "grid": self.grid._to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PuzzleData":
        """Restore a PuzzleData from a save dict.
        Re-runs the level factory so all asset references are live,
        then patches stage and grid layout back in."""
        from levels import LEVEL_FACTORIES
        level = data.get("level", 0)
        factory = LEVEL_FACTORIES.get(level)
        if factory is None:
            raise ValueError(f"No factory for level {level}")
        puzzle = factory()
        puzzle.stage = data.get("stage", 0)
        grid_data = data.get("grid")
        if grid_data:
            puzzle.grid = Grid.from_dict(grid_data)
        return puzzle
    

    
def draw_label(self, x: int, y: int, name: str, icon: object | None):
        if icon:
            icon.update()
            icon_surf = icon.current_frame.image
        else:
            icon_surf = None
        draw_x = x
        if icon_surf:
            self.screen.blit(icon_surf, (draw_x, y))
            draw_x += icon_surf.get_width() + 6
        label = FONT.render(name, True, (255, 255, 255))
        label_y = y + ((icon_surf.get_height() - label.get_height()) // 2 if icon_surf else 0)
        self.screen.blit(label, (draw_x, label_y))
    