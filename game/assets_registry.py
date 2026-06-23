import pygame
from pygame.locals import *
import config
from config import SPRITES_DIR, SOUNDS_DIR, BASE_TILE_SIZE, PIECE_CELL_SIZE
from enum import Enum


class Frame:
    def __init__(self, path: str=None, color: tuple[int, int, int]=None, size: tuple[int, int]=None, offset: tuple[int, int]=(0,0), angle: float=0):
        self.path  = path
        self.color = color
        self.size = size
        self.offset = (offset[0], offset[1])
        self.angle = angle  
        
        # load image once
        if self.path:
            self.path = SPRITES_DIR + path
            image = pygame.image.load(self.path).convert_alpha()
            if self.size:
                image = pygame.transform.scale(image, self.size)
        else:
            image = pygame.Surface(self.size, pygame.SRCALPHA).convert_alpha()
            image.fill(self.color)
        # set rotation
        if self.angle != 0:
            self.image = pygame.transform.rotate(image, self.angle)
        else:
            self.image = image


class Animation:
    def __init__(self, frames: list[Frame], ticks_per_frame: int=-1, loop: bool=False):
        self.frames = frames
        self.ticks_per_frame = ticks_per_frame
        self.current_frame_index = 0
        self.ticks_elapsed = 0
        self.loop = loop
        self.paused = False

    @property
    def current_frame(self) -> Frame:
        return self.frames[self.current_frame_index]
    
    def set_frame(self, index: int):
        self.current_frame_index = max(0, min(index, len(self.frames) - 1))
        self.paused = True
    
    def update(self):
        if self.paused or self.ticks_per_frame == -1:
            return  # nothing to update

        self.ticks_elapsed += 1
        if self.ticks_elapsed >= self.ticks_per_frame:
            self.ticks_elapsed = 0
            if self.loop:
                self.current_frame_index = (self.current_frame_index + 1) % len(self.frames)
            else:
                self.current_frame_index = min(self.current_frame_index + 1, len(self.frames) - 1)




class Sprite:
    def __init__(self, x: float, y: float, animation: Animation):
        self.x = x
        self.y = y
        self.animation = animation
    
    def draw(self, screen: pygame.Surface):
        frame = self.animation.current_frame
        pos = (
            int(self.x * BASE_TILE_SIZE + frame.offset[0] + config.camera_offset[0]), 
            int(self.y * BASE_TILE_SIZE + frame.offset[1] + config.camera_offset[1]))
        screen.blit(frame.image, pos)
    
    def set_pos(self, x: float, y: float):
        self.x = x
        self.y = y
    
    def set_animation(self, animation: Animation):
        self.animation = animation
        self.animation.current_frame_index = 0
        self.animation.ticks_elapsed = 0

    def get_animation(self) -> Animation | None:
        return self.animation

class MarginPiece:
    # dir = SPRITES_DIR + "pieces/"
    dir = SPRITES_DIR

    def __init__(self, path=None, x: int=0, y: int=0):
        self.piece_id = path
        self.x = x
        self.y = y

        # load image once
        if path:
            full_path = MarginPiece.dir + path
            image = pygame.image.load(full_path).convert_alpha()
        else:
            image = pygame.Surface((BASE_TILE_SIZE, BASE_TILE_SIZE), pygame.SRCALPHA).convert_alpha()

        self.image: pygame.Surface = image
        # Cell set: (col, row) offsets from (0,0), built from non-transparent pixels.
        # Step by PIECE_CELL_SIZE (10px) since source images are at 1000% scale.
        self.pixels: set = self.cells_from_surface(image, 0, 0, PIECE_CELL_SIZE) if path else set()
        # display_image is scaled so each cell fills exactly BASE_TILE_SIZE pixels.
        if path and self.pixels:
            cols = max(c for c, _ in self.pixels) + 1
            rows = max(r for _, r in self.pixels) + 1
            self.display_image = pygame.transform.scale(
                image, (cols * BASE_TILE_SIZE, rows * BASE_TILE_SIZE)
            )
        else:
            self.display_image = image

    def get_cells_at_position(self) -> set:
        """Return absolute (col, row) grid cells based on current x/y position."""
        col_offset = self.x // BASE_TILE_SIZE
        row_offset = self.y // BASE_TILE_SIZE
        return {(col + col_offset, row + row_offset) for col, row in self.pixels}
    
    def cells_from_surface(self, surface: pygame.Surface, world_x: int, world_y: int, cell_size: int) -> set:
        """Build a cell set from non-transparent pixels of a surface."""
        cells = set()
        for px in range(0, surface.get_width(), cell_size):
            for py in range(0, surface.get_height(), cell_size):
                # Sample the centre of each cell block
                sample_x = min(px + cell_size // 2, surface.get_width() - 1)
                sample_y = min(py + cell_size // 2, surface.get_height() - 1)
                if surface.get_at((sample_x, sample_y)).a > 0:
                    col = (world_x + px) // cell_size
                    row = (world_y + py) // cell_size
                    cells.add((col, row))
        return cells
        
        

class AudioChannel(Enum):
    SOUND_EFFECTS = 0
    BACKGROUND_AMBIENCE = 1
    PLAYER = 2
    BACKGROUND_MUSIC = 3

class SoundEffect:
    pygame.mixer.set_num_channels(6)


    def __init__(self, path: str, volume: float=0.8, loop=False):
        self.sound = pygame.mixer.Sound(SOUNDS_DIR + path)
        self.sound.set_volume(volume)
        self.loop = -1 if loop else 0

    def play(self, channel: pygame.mixer.Channel=0):
        pygame.mixer.Channel(channel).play(self.sound, loops=self.loop)

    def stop(self):
        self.sound.stop()

class BackgroundMusic:
    current_track = None
    
    def __init__(self, path: str, volume: float=0.4):
        self.path = SOUNDS_DIR + path
        self.volume = volume
        

    def play(self, loops=-1):
        if BackgroundMusic.current_track != self.path:
            pygame.mixer.music.load(self.path)
            pygame.mixer.music.set_volume(self.volume)
            pygame.mixer.music.play(loops)
            BackgroundMusic.current_track = self.path
        
    def stop(self):
        pygame.mixer.music.stop()
        BackgroundMusic.current_track = None

    def pause(self):
        pygame.mixer.music.pause()
    
    def unpause(self):
        pygame.mixer.music.unpause()
    
    def set_volume(self, volume: float):
        self.volume = volume
        pygame.mixer.music.set_volume(volume)
    
    @staticmethod
    def fade_out(ms: int):
        pygame.mixer.music.fadeout(ms)
        BackgroundMusic.current_track = None

player_fps = 10
player_run_fps = 5

class Animations:
    
    default_button = Animation([Frame(path="items/button2.png", size=(100, 50))], ticks_per_frame=30)
    menu_icon = Animation([Frame(path="items/menu_icon.png", size=(50, 50))], ticks_per_frame=30)
    archive_icon = Animation([Frame(path="items/archive_icon.png", size=(50, 50))], ticks_per_frame=30)
    paint_icon = Animation([Frame(path="items/paint_icon.png", size=(50, 50))], ticks_per_frame=30)

    toggle_on = Animation([Frame(path="items/toggle_on.png", size=(100, 50)),], ticks_per_frame=30)
    toggle_off = Animation([Frame(path="items/toggle_off.png", size=(100, 50)),], ticks_per_frame=30)

    # hint_page = Animation([Frame(path="items/button.png")], ticks_per_frame=30)
    book = Animation([Frame(path="items/book.png", size=(480, 320))], ticks_per_frame=30)
    page_turning = Animation([Frame(path="items/player_map.png")], ticks_per_frame=30)

    level_1_hint_1 = Animation([Frame(path="hints/hint_test_1_1.png")], ticks_per_frame=30)
    level_1_hint_2 = Animation([Frame(path="hints/hint_test_1_2.png")], ticks_per_frame=30)
    level_1_hint_3 = Animation([Frame(path="hints/hint_test_1_3.png")], ticks_per_frame=30)

    level_2_hint_1 = Animation([Frame(path="hints/hint_test_2_1.png")], ticks_per_frame=30)
    level_2_hint_2 = Animation([Frame(path="hints/hint_test_2_2.png")], ticks_per_frame=30)
    level_2_hint_3 = Animation([Frame(path="hints/hint_test_2_3.png")], ticks_per_frame=30)

    level_3_hint_1 = Animation([Frame(path="hints/hint_test_3_1.png")], ticks_per_frame=30)
    level_3_hint_2 = Animation([Frame(path="hints/hint_test_3_2.png")], ticks_per_frame=30)
    level_3_hint_3 = Animation([Frame(path="hints/hint_test_3_3.png")], ticks_per_frame=30)

    # artefacts
    # artefact 1
    blackadder_locked = Animation([Frame(path="artefacts/blackadder_locked.png")], ticks_per_frame=30)
    blackadder_unlocked = Animation([Frame(path="artefacts/blackadder_unlocked.png")], ticks_per_frame=30)

    # artefact 2
    gask_locked = Animation([Frame(path="artefacts/gask_locked.png")], ticks_per_frame=30)
    gask_unlocked = Animation([Frame(path="artefacts/gask_unlocked.png")], ticks_per_frame=30)

    # artefact 3
    lesmahagow_locked = Animation([Frame(path="artefacts/lesmahagow_locked.png")], ticks_per_frame=30)
    lesmahagow_unlocked = Animation([Frame(path="artefacts/lesmahagow_unlocked.png")], ticks_per_frame=30)

    # artefact 4
    scone_chartulary_locked = Animation([Frame(path="artefacts/scone_chartulary_locked.png")], ticks_per_frame=30)
    scone_chartulary_unlocked = Animation([Frame(path="artefacts/scone_chartulary_unlocked.png")], ticks_per_frame=30)


    solution_1 = Animation([Frame(path="items/margin_test_0.png")], ticks_per_frame=30)
    solution_2 = Animation([Frame(path="items/margin_test_1.png")], ticks_per_frame=30)
    solution_3 = Animation([Frame(path="items/margin_test_2.png")], ticks_per_frame=30)

    book_flip_animation = Animation([
        Frame(path="items/book_flip_animation1.png", size=(480, 320)),
        Frame(path="items/book_flip_animation2.png", size=(480, 320)),
        Frame(path="items/book_flip_animation3.png", size=(480, 320)),
        Frame(path="items/book_flip_animation4.png", size=(480, 320)),
        Frame(path="items/book_flip_animation5.png", size=(480, 320)),
        Frame(path="items/book_flip_animation6.png", size=(480, 320)),
        Frame(path="items/book_flip_animation7.png", size=(480, 320)),], ticks_per_frame=5)

    coin_animation = Animation([
        Frame(path="items/coin1.png", size=(32, 32)),
        Frame(path="items/coin2.png", size=(32, 32)),
        Frame(path="items/coin3.png", size=(32, 32)),
        Frame(path="items/coin4.png", size=(32, 32)),
        Frame(path="items/coin5.png", size=(32, 32)),
        Frame(path="items/coin6.png", size=(32, 32)),
        Frame(path="items/coin7.png", size=(32, 32)),
        Frame(path="items/coin8.png", size=(32, 32)),], ticks_per_frame=12, loop=True)
    

class MarginPieces:
    test_piece = MarginPiece(path="pieces/organic_shape.png")
    margin_piece_1 = MarginPiece(path="pieces/piece_test_1.png")
    margin_piece_2 = MarginPiece(path="pieces/piece_test_2.png")
    margin_piece_3 = MarginPiece(path="pieces/piece_test_3.png")
    margin_piece_4 = MarginPiece(path="pieces/piece_test_4.png")
    margin_piece_5 = MarginPiece(path="pieces/piece_test_5.png")

    # use these
    adorning_corner = MarginPiece(path="pieces/adorning_corner.png")
    blue_flowers = MarginPiece(path="pieces/blue_flowers.png")
    fish = MarginPiece(path="pieces/fish.png")
    flowers = MarginPiece(path="pieces/flowers.png")
    poppies = MarginPiece(path="pieces/poppies.png")
    thistles = MarginPiece(path="pieces/thistles.png")

class Sound:
    birds_chirping = SoundEffect(path="birds_chirping.mp3")
    page_turning = SoundEffect(path="book.mp3", volume=2)
    confirm = SoundEffect(path="confirm.mp3")
    default_button_click = SoundEffect(path="menu_selection.mp3", volume=0.4)
    drownshock = SoundEffect(path="shock.mp3")
    game_start = SoundEffect(path="game_start.mp3")
    anomaly_click = SoundEffect(path="shock.mp3", volume=0.4)
    papers_shuffling = SoundEffect(path="papers_shuffling.mp3", volume=0.4)
    menu2 = SoundEffect(path="menu2.wav", volume=0.4)
    women_murmuring = SoundEffect(path="soundhunterin-female-voices-crowds-chatting-talking-women-on-fair-frauenstimmen-140260_1.mp3", volume=0.8, loop=True)
    coins_added = SoundEffect(path="coins added.mp3", volume=0.8)
    bookpage = SoundEffect(path="bookpage.mp3", volume=0.8)
    drop_item = SoundEffect(path="drop item.mp3", volume=0.8)
    pickup = SoundEffect(path="pick up.mp3", volume=0.8)



class Music:
    menu= BackgroundMusic(path="MarginMenu.mp3", volume=1)
    church = BackgroundMusic(path="freesound_community-chant-49054.mp3", volume=0.5)
    gameplay = BackgroundMusic(path="Marginalised_(online-video-cutter.com)-1.mp3", volume=1)




class Assets:
    animations = Animations
    sounds = Sound
    background_music = Music
    pieces = MarginPieces
