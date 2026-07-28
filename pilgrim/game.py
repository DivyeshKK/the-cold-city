"""
The simulation engine: grid geometry, the turn loop, combat, power-square
dice rolls, and win/lose resolution.

The engine is controller-agnostic. A "hero controller" is any callable
`fn(game) -> None` that drives the pilgrim's turn using the public methods
below (move_hero_to / hero_attack / hero_neighbors ...). play.py ships a
human controller and a simple auto controller.
"""

from __future__ import annotations

import random
from typing import Callable, List, Optional, Set, Tuple

from .config import GameConfig, Position
from .entities import Enemy, Hero, make_enemy
from .powerups import resolve

HeroController = Callable[["Game"], None]


class Game:
    def __init__(self, config: GameConfig, log: Optional[Callable[[str], None]] = None):
        self.config = config
        self.rng = random.Random(config.seed)
        self.grid = config.grid
        self.hero = Hero.from_config(config.hero)
        self.enemies: List[Enemy] = [
            make_enemy(ec, i) for i, ec in enumerate(config.enemies)
        ]
        self.power_squares: Set[Position] = set(config.power_squares.positions)
        self.round = 0
        self.events: List[str] = []
        self._log_sink = log
        self._validate_placement()

        # per-turn hero state
        self.hero_moves_left = 0
        self.hero_attacked = False

    # -- logging ------------------------------------------------------------
    def log(self, msg: str) -> None:
        self.events.append(msg)
        if self._log_sink:
            self._log_sink(msg)

    # -- validation ---------------------------------------------------------
    def _validate_placement(self) -> None:
        seen = {}
        for tag, pos in [("hero", self.hero.pos)] + \
                        [(e.name, e.pos) for e in self.enemies]:
            if not self.grid.in_bounds(pos):
                raise ValueError(f"{tag} start {pos} is off the {self.grid.width}"
                                 f"x{self.grid.height} board")
            if pos in seen:
                raise ValueError(f"{tag} and {seen[pos]} share tile {pos}")
            seen[pos] = tag
        for pos in self.power_squares:
            if not self.grid.in_bounds(pos):
                raise ValueError(f"power-square {pos} is off the board")

    # -- geometry -----------------------------------------------------------
    def distance(self, a: Position, b: Position) -> int:
        dx, dy = abs(a[0] - b[0]), abs(a[1] - b[1])
        if self.grid.distance == "chebyshev":
            return max(dx, dy)
        return dx + dy  # manhattan

    def _step_offsets(self) -> List[Position]:
        orth = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        if self.grid.allow_diagonal_movement:
            return orth + [(1, 1), (1, -1), (-1, 1), (-1, -1)]
        return orth

    def neighbors(self, pos: Position) -> List[Position]:
        out = []
        for dx, dy in self._step_offsets():
            n = (pos[0] + dx, pos[1] + dy)
            if self.grid.in_bounds(n):
                out.append(n)
        return out

    def occupied(self, exclude: Optional[object] = None) -> Set[Position]:
        tiles = set()
        if self.hero.alive and self.hero is not exclude:
            tiles.add(self.hero.pos)
        for e in self.enemies:
            if e.alive and e is not exclude:
                tiles.add(e.pos)
        return tiles

    def is_free(self, pos: Position) -> bool:
        return self.grid.in_bounds(pos) and pos not in self.occupied()

    def step_toward(self, src: Position, dst: Position,
                    avoid: Optional[Set[Position]] = None) -> Optional[Position]:
        """One neighbor of src that most reduces distance to dst. Ties break
        toward the larger axis gap, giving natural, closest-path pathing."""
        avoid = avoid or set()
        best, best_key = None, None
        gap_x, gap_y = abs(src[0] - dst[0]), abs(src[1] - dst[1])
        for n in self.neighbors(src):
            if n in avoid:
                continue
            d = self.distance(n, dst)
            # prefer moving along the axis with the larger remaining gap
            axis_pref = 1 if (n[0] != src[0] and gap_x >= gap_y) or \
                             (n[1] != src[1] and gap_y > gap_x) else 0
            key = (d, -axis_pref)
            if best_key is None or key < best_key:
                best, best_key = n, key
        return best

    def step_away(self, src: Position, threat: Position,
                  avoid: Optional[Set[Position]] = None) -> Optional[Position]:
        """One neighbor of src that most increases distance from `threat`."""
        avoid = avoid or set()
        best, best_d = None, self.distance(src, threat)
        for n in self.neighbors(src):
            if n in avoid:
                continue
            d = self.distance(n, threat)
            if d > best_d:
                best, best_d = n, d
        return best

    # -- hero turn primitives ----------------------------------------------
    def start_hero_turn(self) -> None:
        self.hero_moves_left = self.hero.moves_per_turn + self.hero.bonus_moves
        self.hero.bonus_moves = 0
        self.hero_attacked = False

    def hero_move_options(self) -> List[Position]:
        if not self.hero.can_move or self.hero_moves_left <= 0:
            return []
        return [n for n in self.neighbors(self.hero.pos) if self.is_free(n)]

    def move_hero_to(self, pos: Position) -> bool:
        if pos not in self.hero_move_options():
            return False
        self.hero.pos = pos
        self.hero_moves_left -= 1
        self.log(f"{self.hero.name} steps to {pos}.")
        self._maybe_roll_power_square(pos)
        return True

    def enemy_at(self, pos: Position) -> Optional[Enemy]:
        for e in self.enemies:
            if e.alive and e.pos == pos:
                return e
        return None

    def hero_attack_targets(self) -> List[Enemy]:
        if not self.hero.can_attack or self.hero_attacked:
            return []
        return [e for e in self.enemies
                if e.alive and self.distance(self.hero.pos, e.pos) <= self.hero.attack_range]

    def hero_attack(self, target: Enemy) -> bool:
        if self.hero_attacked or not self.hero.can_attack:
            return False
        if self.distance(self.hero.pos, target.pos) > self.hero.attack_range:
            return False
        self.hero_attacked = True
        if self.hero.bloom_charges > 0:
            self.hero.bloom_charges -= 1
            self.log(f"{self.hero.name} blooms — light breaks outward.")
            for e in list(self.hero_attack_targets_all_adjacent()):
                e.take_damage(self.hero.attack_damage, self.log)
        else:
            self.log(f"{self.hero.name} strikes {target.name}.")
            target.take_damage(self.hero.attack_damage, self.log)
        return True

    def hero_attack_targets_all_adjacent(self) -> List[Enemy]:
        return [e for e in self.enemies
                if e.alive and self.distance(self.hero.pos, e.pos) <= self.hero.attack_range]

    # -- power squares ------------------------------------------------------
    def _maybe_roll_power_square(self, pos: Position) -> None:
        if pos not in self.power_squares:
            return
        table = self.config.powerups
        face = self.rng.randint(1, table.die_sides)
        key = table.faces.get(face, "whisper")
        pu = resolve(key)
        self.log(f"* {self.hero.name} reaches a shrine and rolls a {face}: "
                 f"{pu.name} — {pu.flavor}")
        if pu.apply:
            pu.apply(self.hero)
        if self.config.power_squares.consume_on_use:
            self.power_squares.discard(pos)

    # -- resolution ---------------------------------------------------------
    @property
    def enemies_alive(self) -> List[Enemy]:
        return [e for e in self.enemies if e.alive]

    def is_won(self) -> bool:
        return len(self.enemies_alive) == 0

    def is_lost(self) -> bool:
        return not self.hero.alive

    def is_over(self) -> bool:
        return self.is_won() or self.is_lost() or self.round >= self.config.turns.max_rounds

    def run(self, hero_controller: HeroController) -> str:
        """Play out the whole game. Returns 'win', 'loss', or 'timeout'."""
        while not self.is_over():
            self.round += 1
            self.log(f"\n=== round {self.round} ===")
            for faction in self.config.turns.order:
                if faction == "hero":
                    if self.hero.alive:
                        self.start_hero_turn()
                        hero_controller(self)
                elif faction == "enemies":
                    for e in self.enemies_alive:
                        e.act(self)
                if self.is_won() or self.is_lost():
                    break
        if self.is_won():
            return "win"
        if self.is_lost():
            return "loss"
        return "timeout"
