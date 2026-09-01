
import json

from assets_registry import Assets, Animation
from classes import PuzzleData, Grid


def grid_from_image(animation: Animation, pixel_res: int) -> Grid:
    """Build a Grid whose shape comes from a pixel-art solution image.

    pixel_res: how many image pixels wide/tall each grid cell is.
    A cell is valid (playable) when its centre pixel has alpha > 0.
    """
    surface = animation.frames[0].image
    img_w, img_h = surface.get_size()
    cols = img_w // pixel_res
    rows = img_h // pixel_res
    valid_cells = set()
    for row in range(rows):
        for col in range(cols):
            cx = col * pixel_res + pixel_res // 2
            cy = row * pixel_res + pixel_res // 2
            if surface.get_at((cx, cy)).a > 0:
                valid_cells.add((col, row))
    return Grid(cols, rows, valid_cells)


def solution_from_idmap(idmap_animation: Animation, pixel_res: int) -> dict:
    """Build {(col, row): (piece_id, rotation)} from a generated id-map image.

    The id-map is never hand-authored — see tools/gen_idmaps.py, which locates
    each piece's placement (position + rotation) in the solution art via exact
    pixel matching and flood-fills its region with a flat colour. Here we just
    sample each cell centre (same technique as grid_from_image, so it always
    stays in lockstep with the grid shape) and look the colour up in the
    generated legend.
    """
    frame = idmap_animation.frames[0]
    surface = frame.image
    legend_path = frame.path.rsplit(".", 1)[0] + ".json"
    with open(legend_path) as f:
        legend = json.load(f)
    colour_to_key = {tuple(entry["colour"]): (entry["piece_id"], entry["rotation"]) for entry in legend}

    img_w, img_h = surface.get_size()
    cols = img_w // pixel_res
    rows = img_h // pixel_res
    solution = {}
    for row in range(rows):
        for col in range(cols):
            cx = col * pixel_res + pixel_res // 2
            cy = row * pixel_res + pixel_res // 2
            r, g, b, a = surface.get_at((cx, cy))
            if a > 0:
                key = colour_to_key.get((r, g, b))
                if key:
                    solution[(col, row)] = key
    return solution


# def new_level_0_data():
#     return PuzzleData(
#         level=0,
#         stage=0,
#         pieces=[
#             Assets.pieces.margin_piece_1, 
#             Assets.pieces.margin_piece_2],
#         hints=[
#             Assets.animations.level_1_hint_1,
#             Assets.animations.level_1_hint_2,
#             Assets.animations.level_1_hint_3,
#         ],
#         trust_points=[10, 5, 1],
#         grid=grid_from_image(Assets.animations.solution_1, cell_px_w=10, cell_px_h=10),
#         solution=Assets.animations.solution_1,
#     )


# def new_level_1_data():
#     return PuzzleData(
#         level=1,
#         stage=0,
#         pieces=[
#             Assets.pieces.margin_piece_1, 
#             Assets.pieces.margin_piece_2,
#             Assets.pieces.margin_piece_3,
#             Assets.pieces.margin_piece_4,
#             ],
#         hints=[
#             Assets.animations.level_2_hint_1,
#             Assets.animations.level_2_hint_2,
#             Assets.animations.level_2_hint_3,
#         ],
#         trust_points=[10, 5, 1],
#         grid=grid_from_image(Assets.animations.solution_2, cell_px_w=10, cell_px_h=10),
#         solution=Assets.animations.solution_2,
#     )


# def new_level_2_data():
#     return PuzzleData(
#         level=2,
#         stage=0,
#         pieces=[
#             Assets.pieces.margin_piece_1, 
#             Assets.pieces.margin_piece_2,
#             Assets.pieces.margin_piece_3,
#             Assets.pieces.margin_piece_4,
#             Assets.pieces.margin_piece_5,
#             ],
#         hints=[
#             Assets.animations.level_3_hint_1,
#             Assets.animations.level_3_hint_2,
#             Assets.animations.level_3_hint_3,
#         ],
#         trust_points=[10, 5, 1],
#         grid=grid_from_image(Assets.animations.solution_3, cell_px_w=10, cell_px_h=10),
#         solution=Assets.animations.solution_3,
#     )

def new_level_0_data():
    return PuzzleData(
        level=0,
        stage=0,
        pieces=[
            Assets.pieces.blue_flowers,
            Assets.pieces.poppies,
        ],
        hints=[
            Assets.animations.level_1_hint_1,
            Assets.animations.level_1_hint_2,
            Assets.animations.level_1_hint_3,
        ],
        trust_points=[10, 5, 1],
        grid=grid_from_image(Assets.animations.solution1, pixel_res=64),
        solution=solution_from_idmap(Assets.animations.solution1_idmap, pixel_res=64),
        page_text="The Book of Hours",
    )


def new_level_1_data():
    return PuzzleData(
        level=1,
        stage=0,
        pieces=[
            Assets.pieces.blue_flowers,
             Assets.pieces.fish,
            Assets.pieces.thistles,
            Assets.pieces.adorning_corner,
            ],
        hints=[
            Assets.animations.level_2_hint_1,
            Assets.animations.level_2_hint_2,
            Assets.animations.level_2_hint_3,
        ],
        trust_points=[10, 5, 1],
        grid=grid_from_image(Assets.animations.solution2, pixel_res=64),
        solution=solution_from_idmap(Assets.animations.solution2_idmap, pixel_res=64),
        page_text="Psalter of Coldingham",
    )


def new_level_2_data():
    return PuzzleData(
        level=2,
        stage=0,
        pieces=[
            Assets.pieces.blue_flowers,
            Assets.pieces.fish,
            Assets.pieces.poppies,
            Assets.pieces.thistles,
            Assets.pieces.adorning_corner,
            Assets.pieces.flowers,
            
            
            ],
        hints=[
            Assets.animations.level_3_hint_1,
            Assets.animations.level_3_hint_2,
            Assets.animations.level_3_hint_3,
        ],
        trust_points=[10, 5, 1],
        grid=grid_from_image(Assets.animations.solution3, pixel_res=64),
        solution=solution_from_idmap(Assets.animations.solution3_idmap, pixel_res=64),
        page_text="Chronicle of the Marches",
    )


# Map of level index → factory function.
# Each call produces a fresh PuzzleData so shared state is never an issue.
# Add new levels here only — game_data.num_levels is derived from len(LEVEL_FACTORIES).
LEVEL_FACTORIES: dict[int, callable] = {
    0: new_level_0_data,
    1: new_level_1_data,
    2: new_level_2_data,
}
