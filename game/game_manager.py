import os
import json
from classes import PuzzleData
from enum import Enum

SAVE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "save.json")


class SubmitResult(Enum):
    CORRECT_ADVANCE   = "correct_advance"   # correct + next level exists
    CORRECT_FINAL     = "correct_final"     # correct + no more levels
    INCORRECT_STAGE   = "incorrect_stage"   # wrong, hint stage advanced
    INCORRECT_MAXED   = "incorrect_maxed"   # wrong, already on last hint


class GameData:
    def __init__(self):
        self.player_name: str = "Player"
        self.current_level: int = 0          # 0-indexed level number
        self.current_puzzle: PuzzleData | None = None
        self.total_trust_points: int = 0
        # Snapshots of completed puzzles keyed by level number, so the player
        # can flip back and view old pages.
        self.level_snapshots: dict[int, PuzzleData] = {}
        # How many levels exist — set by NewGame after loading level factory map.
        self.num_levels: int = 0
        # Indices of artefacts the player has permanently unlocked.
        self.unlocked_artefacts: set[int] = set()


    def _side_for_level(self, level: int) -> str:
        """Even levels (0, 2, 4…) live on the LEFT page; odd on the RIGHT."""
        return "left" if level % 2 == 0 else "right"

    @property
    def current_side(self) -> str:
        return self._side_for_level(self.current_level)

    @property
    def needs_page_turn(self) -> bool:
        """True when advancing to this level requires a physical page turn
        (i.e. every even level > 0, because both pages are filled)."""
        return self.current_level > 0 and self.current_level % 2 == 0

    def is_artefact_unlocked(self, idx: int) -> bool:
        return idx in self.unlocked_artefacts

    def unlock_artefact(self, idx: int, cost: int):
        self.total_trust_points -= cost
        self.unlocked_artefacts.add(idx)

    def hint_image(self, level: int | None = None) -> object:
        """Return the current hint Animation for a given level (default: current)."""
        puzzle = self.current_puzzle if level is None else self.level_snapshots.get(level)
        if puzzle is None or not puzzle.hints:
            return None
        idx = min(puzzle.stage, len(puzzle.hints) - 1)
        return puzzle.hints[idx]


    def load_level(self, level: int):
        """Replace current_puzzle with a fresh instance of the given level."""
        from levels import LEVEL_FACTORIES          # local import to avoid circulars
        factory = LEVEL_FACTORIES.get(level)
        if factory is None:
            raise ValueError(f"No factory registered for level {level}")
        self.current_level = level
        self.current_puzzle = factory()

    def submit_result(self, is_correct: bool) -> tuple["SubmitResult", int]:
        """
        Process a player submission.

        Returns (SubmitResult, points_awarded).
        The caller (ScribeScene) should react to the result to start the
        appropriate transition.
        """
        puzzle = self.current_puzzle
        max_stage = len(puzzle.trust_points) - 1

        if is_correct:
            stage_idx = min(puzzle.stage, max_stage)
            points = puzzle.trust_points[stage_idx]
            self.total_trust_points += points
            # Snapshot the completed puzzle before moving on
            self.level_snapshots[self.current_level] = puzzle
            next_level = self.current_level + 1
            if next_level < self.num_levels:
                self.load_level(next_level)
                return SubmitResult.CORRECT_ADVANCE, points
            else:
                return SubmitResult.CORRECT_FINAL, points
        else:
            if puzzle.stage < max_stage:
                puzzle.next_stage()
                return SubmitResult.INCORRECT_STAGE, 0
            else:
                # Already on last hint — minimal points, no stage advance
                points = puzzle.trust_points[max_stage]
                self.total_trust_points += points
                return SubmitResult.INCORRECT_MAXED, points


    def _reset(self):
        self.player_name = "Player"
        self.current_level = 0
        self.current_puzzle = None
        self.total_trust_points = 0
        self.level_snapshots = {}
        self.unlocked_artefacts = set()

    def _load(self, data: dict):
        self.player_name = data.get("player_name", "Player")
        self.current_level = data.get("current_level", 0)
        self.total_trust_points = data.get("total_trust_points", 0)
        self.unlocked_artefacts = set(data.get("unlocked_artefacts", []))
        puzzle_data = data.get("current_puzzle")
        self.current_puzzle = PuzzleData.from_dict(puzzle_data) if puzzle_data else None

    def _to_dict(self) -> dict:
        return {
            "player_name": self.player_name,
            "current_level": self.current_level,
            "total_trust_points": self.total_trust_points,
            "unlocked_artefacts": list(self.unlocked_artefacts),
            "current_puzzle": self.current_puzzle._to_dict() if self.current_puzzle else None,
        }


# Module-level singleton — import and read from anywhere:
#   from game_manager import game_data
game_data = GameData()


class RunState(Enum):
    RUNNING = 0
    PAUSED = 1
    SUCCESS = 2
    GAME_OVER = 3
    RESTART = 4
    START = 5
    RESUME = 6


class NewGame:
    """Manages save / load / quit. Operates on the global game_data singleton."""

    def __init__(self):
        from levels import LEVEL_FACTORIES
        game_data._reset()
        game_data.num_levels = len(LEVEL_FACTORIES)
        game_data.load_level(0)
        self.state = RunState.RUNNING

    def is_running(self) -> bool:
        return self.state == RunState.RUNNING

    def quit(self):
        self.state = RunState.GAME_OVER

    def save(self):
        with open(SAVE_PATH, "w") as f:
            json.dump(game_data._to_dict(), f, indent=2)

    def load(self) -> bool:
        if not os.path.exists(SAVE_PATH):
            return False
        with open(SAVE_PATH) as f:
            data = json.load(f)
        game_data._load(data)
        return True

    @staticmethod
    def has_save() -> bool:
        return os.path.exists(SAVE_PATH)
