"""
gen_idmaps.py
=============
One-off content-pipeline script: locates each margin piece's placement
(position + rotation) inside its level's solution artwork via exact pixel
matching, then bakes the result into two generated (never hand-edited)
files per level:

  answer_key_N_idmap.png   same size as the solution art; each valid cell
                            is flood-filled with a flat colour identifying
                            the (piece_id, rotation) that belongs there.
  answer_key_N_idmap.json  colour -> {piece_id, rotation} legend.

The game reads these at level-load time (see levels.py:build_grid_and_solution)
to derive per-cell correctness cheaply, without any image search at runtime.

Re-run this whenever the solution art or piece sprites change:
    python3 tools/gen_idmaps.py
(run from the game/ directory, or anywhere — it locates itself)
"""
import os
import sys
import json
import time
import colorsys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

GAME_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GAME_DIR)
os.chdir(GAME_DIR)

import pygame
import numpy as np

pygame.init()
pygame.display.set_mode((10, 10))

PIXEL_RES = 64  # must match grid_from_image's pixel_res
ROTATIONS = [0, 90, 180, 270]

LEVELS = [
    {
        "solution": "assets/sprites/items/answer_key_1_revised.png",
        "idmap_out": "assets/sprites/items/answer_key_1_idmap.png",
        "legend_out": "assets/sprites/items/answer_key_1_idmap.json",
        "pieces": ["blue_flowers", "poppies"],
    },
    {
        "solution": "assets/sprites/items/answer_key_2_revised.png",
        "idmap_out": "assets/sprites/items/answer_key_2_idmap.png",
        "legend_out": "assets/sprites/items/answer_key_2_idmap.json",
        "pieces": ["blue_flowers", "fish", "thistles", "adorning_corner"],
    },
    {
        "solution": "assets/sprites/items/answer_key_3_revised.png",
        "idmap_out": "assets/sprites/items/answer_key_3_idmap.png",
        "legend_out": "assets/sprites/items/answer_key_3_idmap.json",
        "pieces": ["blue_flowers", "fish", "poppies", "thistles", "adorning_corner", "flowers"],
    },
]


def load_rgba_surf(surf):
    rgb = pygame.surfarray.pixels3d(surf).copy()
    a = pygame.surfarray.pixels_alpha(surf).copy()
    return rgb, a, surf.get_size()


def load_rgba(path):
    return load_rgba_surf(pygame.image.load(path).convert_alpha())


def coarse_candidates(sol_rgb, p_rgb, p_a, n_fp=14):
    """Sparse-fingerprint pre-filter: cheap, but noisy — narrowed by best_local below."""
    W, H = p_a.shape
    opaque = np.argwhere(p_a > 10)
    if len(opaque) < n_fp:
        return np.empty((0, 2), dtype=int)
    idxs = np.linspace(0, len(opaque) - 1, n_fp).astype(int)
    pts = opaque[idxs]
    sol_w, sol_h = sol_rgb.shape[0], sol_rgb.shape[1]
    max_tx, max_ty = sol_w - W, sol_h - H
    if max_tx < 0 or max_ty < 0:
        return np.empty((0, 2), dtype=int)
    mask = None
    for fx, fy in pts:
        colour = p_rgb[fx, fy]
        crop = sol_rgb[fx:fx + max_tx + 1, fy:fy + max_ty + 1]
        m = np.all(crop == colour, axis=-1)
        mask = m if mask is None else (mask & m)
    return np.argwhere(mask)


def cluster(points, radius=15):
    """Collapse a cloud of near-duplicate coarse candidates into one point per cluster."""
    pts = [tuple(int(v) for v in p) for p in points]
    clusters = []
    used = [False] * len(pts)
    for i, p in enumerate(pts):
        if used[i]:
            continue
        c = [p]
        used[i] = True
        for j in range(i + 1, len(pts)):
            if used[j]:
                continue
            if abs(pts[j][0] - p[0]) <= radius and abs(pts[j][1] - p[1]) <= radius:
                c.append(pts[j])
                used[j] = True
        clusters.append(c[0])
    return clusters


def best_local(sol_rgb, p_rgb, p_a, tx0, ty0, W, H, window=12):
    """Exhaustively verify every opaque pixel in a small window to find the true offset."""
    opaque = p_a > 10
    best = (0, None)
    for dx in range(-window, window + 1):
        for dy in range(-window, window + 1):
            tx, ty = tx0 + dx, ty0 + dy
            if tx < 0 or ty < 0:
                continue
            crop = sol_rgb[tx:tx + W, ty:ty + H]
            if crop.shape[:2] != (W, H):
                continue
            cm = np.all(crop == p_rgb, axis=-1)
            score = cm[opaque].mean() if opaque.sum() else 0
            if score > best[0]:
                best = (score, (tx, ty))
    return best


def find_all_placements(sol_rgb, p_rgb, p_a, min_score=0.985):
    """All confident (near-)exact placements of one piece orientation in the solution art."""
    W, H = p_a.shape
    cands = coarse_candidates(sol_rgb, p_rgb, p_a)
    if len(cands) == 0:
        return []
    out = []
    for tx0, ty0 in cluster(cands):
        score, pos = best_local(sol_rgb, p_rgb, p_a, tx0, ty0, W, H)
        if pos is not None and score >= min_score:
            out.append(pos)
    return out


def palette(n):
    colours = []
    for i in range(n):
        h = i / max(n, 1)
        r, g, b = colorsys.hsv_to_rgb(h, 0.85, 0.95)
        colours.append((int(r * 255), int(g * 255), int(b * 255)))
    return colours


def main():
    for level in LEVELS:
        t0 = time.time()
        sol_rgb, sol_a, (sw, sh) = load_rgba(level["solution"])
        placements = []

        for piece_name in level["pieces"]:
            orig = pygame.image.load(f"assets/sprites/pieces/{piece_name}.png").convert_alpha()
            for angle in ROTATIONS:
                # `angle` here is the CLOCKWISE rotation label, matching
                # MarginPiece.rotation's convention (rotate(clockwise=True)
                # advances it by +90 per press). pygame.transform.rotate uses
                # the opposite (counter-clockwise-positive) sign convention,
                # so we negate here to keep the stored label and the pixel
                # data it was derived from in agreement.
                rot_surf = pygame.transform.rotate(orig, -angle) if angle else orig
                p_rgb, p_a, (W, H) = load_rgba_surf(rot_surf)
                for (tx, ty) in find_all_placements(sol_rgb, p_rgb, p_a):
                    placements.append({
                        "piece_id": f"pieces/{piece_name}.png",
                        "rotation": angle,
                        "tx": tx, "ty": ty, "W": W, "H": H,
                        "alpha_mask": p_a,
                    })

        print(level["solution"], "-> found", len(placements), "placements in",
              round(time.time() - t0, 1), "s")

        unique_keys = sorted({(p["piece_id"], p["rotation"]) for p in placements})
        colours = palette(len(unique_keys))
        key_to_colour = dict(zip(unique_keys, colours))

        idmap_alpha = np.zeros((sw, sh), dtype=np.uint8)
        idmap_rgb = np.zeros((sw, sh, 3), dtype=np.uint8)
        for p in placements:
            colour = key_to_colour[(p["piece_id"], p["rotation"])]
            mask = p["alpha_mask"] > 10
            tx, ty, W, H = p["tx"], p["ty"], p["W"], p["H"]
            idmap_rgb[tx:tx + W, ty:ty + H][mask] = colour
            idmap_alpha[tx:tx + W, ty:ty + H][mask] = 255

        idmap = pygame.Surface((sw, sh), pygame.SRCALPHA)
        pygame.surfarray.blit_array(idmap, idmap_rgb)
        alpha_view = pygame.surfarray.pixels_alpha(idmap)
        alpha_view[:, :] = idmap_alpha
        del alpha_view

        pygame.image.save(idmap, level["idmap_out"])

        legend = [
            {"colour": list(colour), "piece_id": piece_id, "rotation": rotation}
            for (piece_id, rotation), colour in key_to_colour.items()
        ]
        with open(level["legend_out"], "w") as f:
            json.dump(legend, f, indent=2)

        print("   saved", level["idmap_out"], "and", level["legend_out"],
              "with", len(legend), "legend entries")

    print("DONE")


if __name__ == "__main__":
    main()
