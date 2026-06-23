
from assets_registry import Assets, Animation
from classes import PuzzleData, Grid


def grid_from_image(animation: Animation, cell_px_w: int, cell_px_h: int) -> Grid:
    """Build a Grid whose shape comes from a pixel-art solution image.

    cell_px_w / cell_px_h: how many image pixels wide/tall each grid cell is.
    A cell is valid (playable) when its centre pixel has alpha > 0.
    """
    surface = animation.frames[0].image
    img_w, img_h = surface.get_size()
    cols = img_w // cell_px_w
    rows = img_h // cell_px_h
    valid_cells = set()
    for row in range(rows):
        for col in range(cols):
            cx = col * cell_px_w + cell_px_w // 2
            cy = row * cell_px_h + cell_px_h // 2
            if surface.get_at((cx, cy)).a > 0:
                valid_cells.add((col, row))
    return Grid(cols, rows, valid_cells)


def new_level_0_data():
    return PuzzleData(
        level=0,
        stage=0,
        pieces=[
            Assets.pieces.margin_piece_1, 
            Assets.pieces.margin_piece_2],
        hints=[
            Assets.animations.level_1_hint_1,
            Assets.animations.level_1_hint_2,
            Assets.animations.level_1_hint_3,
        ],
        trust_points=[10, 5, 1],
        grid=grid_from_image(Assets.animations.solution_1, cell_px_w=10, cell_px_h=10),
        solution=Assets.animations.solution_1,
    )


def new_level_1_data():
    return PuzzleData(
        level=1,
        stage=0,
        pieces=[
            Assets.pieces.margin_piece_1, 
            Assets.pieces.margin_piece_2,
            Assets.pieces.margin_piece_3,
            Assets.pieces.margin_piece_4,
            ],
        hints=[
            Assets.animations.level_2_hint_1,
            Assets.animations.level_2_hint_2,
            Assets.animations.level_2_hint_3,
        ],
        trust_points=[10, 5, 1],
        grid=grid_from_image(Assets.animations.solution_2, cell_px_w=10, cell_px_h=10),
        solution=Assets.animations.solution_2,
    )


def new_level_2_data():
    return PuzzleData(
        level=2,
        stage=0,
        pieces=[
            Assets.pieces.margin_piece_1, 
            Assets.pieces.margin_piece_2,
            Assets.pieces.margin_piece_3,
            Assets.pieces.margin_piece_4,
            Assets.pieces.margin_piece_5,
            ],
        hints=[
            Assets.animations.level_3_hint_1,
            Assets.animations.level_3_hint_2,
            Assets.animations.level_3_hint_3,
        ],
        trust_points=[10, 5, 1],
        grid=grid_from_image(Assets.animations.solution_3, cell_px_w=10, cell_px_h=10),
        solution=Assets.animations.solution_3,
    )


# Map of level index → factory function.
# Each call produces a fresh PuzzleData so shared state is never an issue.
# Add new levels here only — game_data.num_levels is derived from len(LEVEL_FACTORIES).
LEVEL_FACTORIES: dict[int, callable] = {
    0: new_level_0_data,
    1: new_level_1_data,
    2: new_level_2_data,
}
