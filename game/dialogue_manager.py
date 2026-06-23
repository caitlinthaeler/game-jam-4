"""
Dialogue system.

Dialogue files (JSON):
  {
    "id": "file_id",
    "lines": [
      {"speaker": "Name", "text": "What they say."}
    ],
    "next": {
      "type": "choices" | "file" | "exit",
      "flags_raise": ["flag_name", ...],

      // type == "choices":
      "options": [
        {"text": "Player option text", "file": "next_file_id"},
        ...
      ],

      // type == "file":
      "file": "next_file_id",

      // type == "exit":
      "to": "world_map"   // scene name to return to
    }
  }

Master file (JSON) at <surveyor_dir>/master.json:
  {
    "default": "first_meeting",
    "entries": [
      {
        "requires_all": ["flag_a"],
        "requires_none": ["flag_b"],
        "file": "some_file_id"
      }
    ]
  }
  Entries checked top-to-bottom; first full match wins. "default" is the fallback.
"""

import pygame
import os
import json
import sys
from collections import deque
from config import DIALOGUE_DIR, FONT, SCREEN_WIDTH, SCREEN_HEIGHT, BORDER, FPS
from assets_registry import Assets

# Map speaker names to their idle sprite. Any speaker not listed shows no sprite.
_SPEAKER_SPRITES = {
    "Surveyor Bob":     lambda: Assets.animations.surveyor_1_idle,
    "Surveyor Dave":    lambda: Assets.animations.surveyor_2_idle,
    "Surveyor Michael": lambda: Assets.animations.surveyor_3_idle,
}

_SPEED = 2          # characters revealed per frame (60 fps -> ~120 chars/sec)
_BOX_H = 200
_BOX_X = BORDER
_BOX_Y = SCREEN_HEIGHT - _BOX_H - BORDER
_BOX_W = SCREEN_WIDTH - BORDER * 2
_PAD = 16
_TEXT_W = _BOX_W - _PAD * 2
_LINE_H = 24
_CHOICE_H = 38
_CHOICE_GAP = 6

_COL_BG       = (15,  15,  25,  210)
_COL_BORDER   = (180, 160, 120)
_COL_SPEAKER  = (220, 200, 140)
_COL_TEXT     = (240, 235, 220)
_COL_PROMPT   = (150, 140, 110)
_COL_BTN_HOV  = ( 55,  45,  65)
_COL_BTN_IDLE = (220, 200, 140)


class DialogueManager:
    def __init__(self, screen: pygame.Surface, clock: pygame.time.Clock):
        self.screen = screen
        self.clock = clock
        self._bg: pygame.Surface = None
        self._game = None
        self._queue: deque = deque()
        self._surveyor_dir: str = ""
        self._last_speaker: str = ""

    # ------------------------------------------------------------------ public

    def run(self, surveyor_dir: str, game) -> str:
        """
        Consult master.json, run all queued dialogue files in order.
        Blocks until the conversation ends.
        Returns the name of the scene to transition to (default "world_map").
        """
        self._game = game
        self._surveyor_dir = surveyor_dir
        self._queue.clear()

        master_path = os.path.join(DIALOGUE_DIR, surveyor_dir, "master.json")
        start = self._resolve_master(master_path)
        if not start:
            return "world_map"

        self._bg = self.screen.copy()
        self._push(start)

        while self._queue:
            path = self._queue.popleft()
            result = self._run_file(path)
            if result:
                return result

        return "world_map"

    # ----------------------------------------------------------------- private

    def _push(self, file_id: str):
        path = os.path.join(DIALOGUE_DIR, self._surveyor_dir, file_id + ".json")
        self._queue.appendleft(path)

    def _resolve_master(self, path: str):
        if not os.path.exists(path):
            return None
        with open(path) as f:
            data = json.load(f)
        for entry in data.get("entries", []):
            req = entry.get("requires_all", [])
            blk = entry.get("requires_none", [])
            # if self._game.flags.check_all(req) and self._game.flags.check_none(blk):
            #     return entry["file"]
        return data.get("default")

    def _run_file(self, path: str):
        if not os.path.exists(path):
            return None
        with open(path) as f:
            data = json.load(f)

        lines = data.get("lines", [])
        nxt   = data.get("next", {"type": "exit", "to": "world_map"})

        for line in lines:
            self._show_line(line["speaker"], line["text"])

        # for flag in nxt.get("flags_raise", []):
        #     self._game.raise_flag(flag)

        nxt_type = nxt.get("type", "exit")
        if nxt_type == "exit":
            return nxt.get("to", "world_map")
        elif nxt_type == "file":
            self._push(nxt["file"])
        elif nxt_type == "choices":
            chosen = self._show_choices(nxt["options"])
            if chosen:
                self._push(chosen)
        return None

    # --------------------------------------------------------- blocking renders

    def _show_line(self, speaker: str, text: str):
        """Typewriter line. Space/Right/Click: first press skips animation, second advances."""
        self._last_speaker = speaker
        chars = 0
        total = len(text)
        done  = False

        while True:
            advance = False
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
                is_skip = (event.type == pygame.KEYDOWN and
                           event.key in (pygame.K_SPACE, pygame.K_RIGHT))
                is_click = (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1)
                if is_skip or is_click:
                    if not done:
                        done = True
                        chars = total
                    else:
                        advance = True

            if not done:
                chars = min(chars + _SPEED, total)
                if chars >= total:
                    done = True

            self._draw_line(speaker, text[:chars], done)
            pygame.display.flip()
            self.clock.tick(FPS)
            if advance:
                return

    def _show_choices(self, options: list):
        """Display player-choice buttons; returns the file id of the chosen option."""
        rects = [
            pygame.Rect(
                _BOX_X + _PAD,
                _BOX_Y + 42 + i * (_CHOICE_H + _CHOICE_GAP),
                _BOX_W - _PAD * 2,
                _CHOICE_H,
            )
            for i in range(len(options))
        ]
        while True:
            mouse = pygame.mouse.get_pos()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for i, r in enumerate(rects):
                        if r.collidepoint(event.pos):
                            return options[i]["file"]
            self._draw_choices(options, rects, mouse)
            pygame.display.flip()
            self.clock.tick(FPS)

    # --------------------------------------------------------------- rendering

    def _make_box(self) -> pygame.Surface:
        box = pygame.Surface((_BOX_W, _BOX_H), pygame.SRCALPHA)
        box.fill(_COL_BG)
        pygame.draw.rect(box, _COL_BORDER, box.get_rect(), 2)
        return box

    def _draw_sprite(self, speaker: str):
        getter = _SPEAKER_SPRITES.get(speaker)
        if getter is None:
            return
        anim = getter()
        anim.update()
        surf = anim.current_frame.image
        self.screen.blit(surf, (BORDER * 2, _BOX_Y - surf.get_height()))

    def _draw_line(self, speaker: str, visible: str, done: bool):
        self.screen.blit(self._bg, (0, 0))
        self._draw_sprite(speaker)
        box = self._make_box()

        name_surf = FONT.render(speaker, True, _COL_SPEAKER)
        box.blit(name_surf, (_PAD, _PAD - 2))
        # pygame.draw.line(box, _COL_SPEAKER, (_PAD, _PAD + name_surf.get_height() - 1), (_PAD + name_surf.get_width(), _PAD + name_surf.get_height() - 1), 1)

        y = 42
        for line in self._wrap(visible):
            box.blit(FONT.render(line, True, _COL_TEXT), (_PAD, y))
            y += _LINE_H

        if done:
            prompt = FONT.render("SPACE  ▶", True, _COL_PROMPT)
            box.blit(prompt, (_BOX_W - prompt.get_width() - _PAD,
                               _BOX_H - _PAD - prompt.get_height()))

        self.screen.blit(box, (_BOX_X, _BOX_Y))

    def _draw_choices(self, options: list, rects: list, mouse: tuple):
        self.screen.blit(self._bg, (0, 0))
        self._draw_sprite(self._last_speaker)
        box = self._make_box()

        box.blit(FONT.render("Choose your response:", True, _COL_SPEAKER), (_PAD, _PAD - 2))

        for opt, rect in zip(options, rects):
            local = rect.move(-_BOX_X, -_BOX_Y)
            hov   = rect.collidepoint(mouse)
            pygame.draw.rect(box, _COL_BTN_HOV if hov else _COL_BTN_IDLE, local)
            label = FONT.render(opt["text"], True,
                                _COL_TEXT if hov else _COL_BTN_HOV)
            box.blit(label, (local.x + 10,
                              local.y + (local.height - label.get_height()) // 2))

        self.screen.blit(box, (_BOX_X, _BOX_Y))

    # ----------------------------------------------------------------- helpers

    def _wrap(self, text: str) -> list:
        words = text.split()
        lines, cur = [], ""
        for w in words:
            test = (cur + " " + w).strip()
            if FONT.size(test)[0] <= _TEXT_W:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines
