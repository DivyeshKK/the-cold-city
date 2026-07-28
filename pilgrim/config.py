"""
Configuration for the pilgrimage combat simulation.

Everything you can tune about a game lives here as plain dataclasses.
`default_config()` at the bottom returns a complete, playable game — edit
it, or build your own GameConfig, to describe a scenario.

Coordinates are (x, y):
    x = column, 0 .. width-1   (left  -> right)
    y = row,    0 .. height-1  (top   -> bottom)

By convention the hero starts at the bottom (the slums) and the castle
looms at the top (the oasis). The board's 7 rows are the palette's
dusk-to-dawn color script; see render.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

Position = Tuple[int, int]


# ---------------------------------------------------------------------------
# Grid
# ---------------------------------------------------------------------------
@dataclass
class GridConfig:
    width: int = 5
    height: int = 7
    # "chebyshev" allows diagonal steps to count as 1 unit; "manhattan"
    # counts orthogonal steps only. Distance metric drives both sniper
    # range checks and goon pathing.
    distance: str = "manhattan"
    allow_diagonal_movement: bool = False

    def in_bounds(self, pos: Position) -> bool:
        x, y = pos
        return 0 <= x < self.width and 0 <= y < self.height


# ---------------------------------------------------------------------------
# Powerups (what a dice roll on a power-square can grant)
# ---------------------------------------------------------------------------
@dataclass
class Powerup:
    key: str
    name: str
    # Flavor line printed when received. Keep it terminal-minimal + poetic.
    flavor: str
    # Effect is applied to the Hero when granted. Signature: (hero) -> None.
    # Left as a key here; the actual functions live in powerups.py so config
    # stays pure data. `apply` is filled in by powerups.build_table().
    apply: Optional[Callable] = None


@dataclass
class PowerupTableConfig:
    """Maps a d6 face (1-6, or any die size) to a powerup key."""
    die_sides: int = 6
    # face -> powerup key. Missing faces = "nothing happens".
    faces: Dict[int, str] = field(
        default_factory=lambda: {
            1: "whisper",     # nothing — the world stays quiet
            2: "mend",        # +2 max hp and heal
            3: "reach",       # a ranged strike (range 2)
            4: "stride",      # +1 movement next turn
            5: "ward",        # block the next incoming damage
            6: "bloom",       # strike all adjacent tiles
        }
    )


@dataclass
class PowerSquareConfig:
    positions: List[Position] = field(default_factory=list)
    # If True, a power-square is spent after one roll. If False, it can be
    # rolled every time the hero ends a move on it.
    consume_on_use: bool = True


# ---------------------------------------------------------------------------
# Hero
# ---------------------------------------------------------------------------
@dataclass
class HeroConfig:
    name: str = "the pilgrim"
    glyph: str = "@"
    start: Position = (2, 6)          # bottom-center, deep in the slums
    max_hp: int = 10
    attack_damage: int = 1            # base melee, hits an adjacent enemy
    attack_range: int = 1             # melee reach in grid units
    moves_per_turn: int = 1           # squares of movement per turn
    # "one action" turn: on your turn you may move up to moves_per_turn
    # squares AND make one attack. Set can_move / can_attack to shape it.
    can_move: bool = True
    can_attack: bool = True


# ---------------------------------------------------------------------------
# Enemies
# ---------------------------------------------------------------------------
@dataclass
class EnemyConfig:
    kind: str                         # "goon" | "sniper" | any registered kind
    start: Position
    name: Optional[str] = None        # defaults to kind + index
    # Per-enemy overrides. Anything left None falls back to the archetype
    # defaults defined in entities.py.
    max_hp: Optional[int] = None
    damage: Optional[int] = None
    move_range: Optional[int] = None
    # Sniper-specific: minimum distance at which the ranged shot triggers.
    threat_range: Optional[int] = None


# ---------------------------------------------------------------------------
# Turn system
# ---------------------------------------------------------------------------
@dataclass
class TurnConfig:
    # Order of factions each round. "hero" and "enemies" are the two sides.
    # Default: hero acts, then every enemy acts.
    order: List[str] = field(default_factory=lambda: ["hero", "enemies"])
    max_rounds: int = 100             # safety cap for simulations


# ---------------------------------------------------------------------------
# Whole game
# ---------------------------------------------------------------------------
@dataclass
class GameConfig:
    grid: GridConfig = field(default_factory=GridConfig)
    hero: HeroConfig = field(default_factory=HeroConfig)
    enemies: List[EnemyConfig] = field(default_factory=list)
    power_squares: PowerSquareConfig = field(default_factory=PowerSquareConfig)
    powerups: PowerupTableConfig = field(default_factory=PowerupTableConfig)
    turns: TurnConfig = field(default_factory=TurnConfig)
    seed: Optional[int] = None        # fix for reproducible dice / AI


def default_config() -> GameConfig:
    """A complete, balanced starter scenario.

    The pilgrim begins bottom-center. Two goons guard the mid-city, a
    sniper watches from a rooftop, and two power-squares sit on the path
    up — the world's small mercies.
    """
    return GameConfig(
        grid=GridConfig(width=5, height=7, distance="manhattan"),
        hero=HeroConfig(start=(2, 6)),
        enemies=[
            EnemyConfig(kind="goon", start=(2, 4)),   # blocks the low road
            EnemyConfig(kind="goon", start=(3, 2)),   # guards the city
            EnemyConfig(kind="sniper", start=(2, 0)),  # atop the castle
        ],
        power_squares=PowerSquareConfig(
            # shrines on the central column — the pilgrim's natural path up,
            # so she gathers Reach/Mend/Ward as she climbs toward the castle.
            positions=[(2, 5), (2, 3)],
            consume_on_use=True,
        ),
        powerups=PowerupTableConfig(),
        turns=TurnConfig(order=["hero", "enemies"]),
        seed=None,
    )
