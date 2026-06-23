import pygame
import numpy as np
import random


class VHSEffect:
    def __init__(self, surface_size: tuple[int, int], intensity: float = 0.6):
        self.intensity = intensity
        self.enabled = True
        self._surface_size = surface_size
        self._scanlines = self._make_scanlines(surface_size, intensity)

    def _make_scanlines(self, size, intensity):
        overlay = pygame.Surface(size, pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 0))
        alpha = int(intensity * 55)
        for y in range(0, size[1], 2):
            pygame.draw.line(overlay, (0, 0, 0, alpha), (0, y), (size[0] - 1, y))
        return overlay

    def apply(self, surface: pygame.Surface) -> None:
        if not self.enabled:
            return
        arr = pygame.surfarray.pixels3d(surface)  # (width, height, 3)
        w, h = arr.shape[0], arr.shape[1]

        # Chromatic aberration: shift red right, blue left
        shift = max(1, int(self.intensity * 4))
        arr[:, :, 0] = np.roll(arr[:, :, 0], shift, axis=0)
        arr[:, :, 2] = np.roll(arr[:, :, 2], -shift, axis=0)

        # Film grain
        grain = int(self.intensity * 20)
        if grain > 0:
            noise = np.random.randint(-grain, grain + 1, (w, h), dtype=np.int16)
            for c in range(3):
                arr[:, :, c] = np.clip(arr[:, :, c].astype(np.int16) + noise, 0, 255)

        # Grayscale overlay — blend pixels toward luminance
        gray_amount = self.intensity * 0.4
        gray = (arr[:, :, 0].astype(np.float32) * 0.299 +
                arr[:, :, 1].astype(np.float32) * 0.587 +
                arr[:, :, 2].astype(np.float32) * 0.114)
        for c in range(3):
            arr[:, :, c] = np.clip(
                arr[:, :, c].astype(np.float32) * (1.0 - gray_amount) + gray * gray_amount,
                0, 255
            ).astype(np.uint8)

        del arr  # unlock surface

        # Scanlines overlay
        surface.blit(self._scanlines, (0, 0))

        # Occasional horizontal jitter on a random strip
        if random.random() < 0.08 * self.intensity:
            strip_y = random.randint(0, h - 12)
            strip_h = random.randint(2, 12)
            strip_h = min(strip_h, h - strip_y)
            jitter_x = random.randint(-int(self.intensity * 6), int(self.intensity * 6))
            if jitter_x != 0:
                strip = surface.subsurface((0, strip_y, w, strip_h)).copy()
                surface.blit(strip, (jitter_x, strip_y))

    def set_intensity(self, intensity: float):
        self.intensity = max(0.0, min(1.0, intensity))
        self._scanlines = self._make_scanlines(self._surface_size, self.intensity)
