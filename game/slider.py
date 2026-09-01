import pygame


class Slider:
    def __init__(
        self,
        rect: pygame.Rect,
        value: float = 0.0,
        min_value: float = 0.0,
        max_value: float = 1.0,
        on_change=None,
        track_colour=(200, 200, 200),
        fill_colour=(120, 120, 120),
        knob_colour=(255, 255, 255),
        knob_outline_colour=(80, 80, 80),
        knob_outline_width=2,
        knob_radius=None,
        border_radius=None,
        label_font=None,
        label_colour=(0, 0, 0),
        label_format="{percent}%",
        label_offset=(16, 0),
    ):
        self.rect = pygame.Rect(rect)
        self.min_value = min_value
        self.max_value = max_value
        self.value = max(min_value, min(max_value, value))
        self.on_change = on_change

        self.track_colour = track_colour
        self.fill_colour = fill_colour
        self.knob_colour = knob_colour
        self.knob_outline_colour = knob_outline_colour
        self.knob_outline_width = knob_outline_width
        self.knob_radius = knob_radius if knob_radius is not None else self.rect.height // 2 + 4
        self.border_radius = border_radius if border_radius is not None else self.rect.height // 2

        self.label_font = label_font
        self.label_colour = label_colour
        self.label_format = label_format
        self.label_offset = label_offset

        self._dragging = False

    @property
    def ratio(self) -> float:
        span = self.max_value - self.min_value
        return 0.0 if span == 0 else (self.value - self.min_value) / span

    def set_value(self, value: float, notify: bool = True):
        new_value = max(self.min_value, min(self.max_value, value))
        changed = new_value != self.value
        self.value = new_value
        if changed and notify and self.on_change:
            self.on_change(self.value)

    def _value_at(self, x: int) -> float:
        rel_x = max(0, min(x - self.rect.left, self.rect.width))
        ratio = rel_x / self.rect.width if self.rect.width else 0.0
        return self.min_value + ratio * (self.max_value - self.min_value)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self._dragging = True
                self.set_value(self._value_at(event.pos[0]))
                return True
        elif event.type == pygame.MOUSEMOTION and self._dragging:
            self.set_value(self._value_at(event.pos[0]))
            return True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self._dragging:
            self._dragging = False
            return True
        return False

    def draw(self, surface: pygame.Surface):
        pygame.draw.rect(surface, self.track_colour, self.rect, border_radius=self.border_radius)

        fill_rect = self.rect.copy()
        fill_rect.width = int(self.ratio * self.rect.width)
        pygame.draw.rect(surface, self.fill_colour, fill_rect, border_radius=self.border_radius)

        knob_center = (self.rect.left + int(self.ratio * self.rect.width), self.rect.centery)
        pygame.draw.circle(surface, self.knob_colour, knob_center, self.knob_radius)
        if self.knob_outline_width:
            pygame.draw.circle(surface, self.knob_outline_colour, knob_center, self.knob_radius, self.knob_outline_width)

        if self.label_font:
            text = self.label_format.format(value=self.value, percent=int(self.ratio * 100))
            label = self.label_font.render(text, True, self.label_colour)
            label_rect = label.get_rect(
                midleft=(self.rect.right + self.label_offset[0], self.rect.centery + self.label_offset[1])
            )
            surface.blit(label, label_rect)
