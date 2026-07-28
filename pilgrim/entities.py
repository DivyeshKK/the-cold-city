"""
Entities: the pilgrim and the things in her way.

Enemies are pluggable. Each archetype subclasses Enemy and implements
`act(game)`, using the helpers on `game` (distance, step_toward, etc.).
Register a new archetype in ENEMY_KINDS and it becomes usable from config
via EnemyConfig(kind="your_kind", ...).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Type

from .config import EnemyConfig, HeroConfig, Position


# ---------------------------------------------------------------------------
# Hero
# ---------------------------------------------------------------------------
@dataclass
class Hero:
    name: str
    glyph: str
    pos: Position
    max_hp: int
    hp: int
    attack_damage: int
    attack_range: int
    moves_per_turn: int
    can_move: bool
    can_attack: bool
    # runtime-only powerup state
    bonus_moves: int = 0      # extra movement for the current turn (Stride)
    wards: int = 0            # each absorbs one incoming hit (Ward)
    bloom_charges: int = 0    # next attack hits all adjacent tiles (Bloom)

    @classmethod
    def from_config(cls, c: HeroConfig) -> "Hero":
        return cls(
            name=c.name, glyph=c.glyph, pos=c.start,
            max_hp=c.max_hp, hp=c.max_hp,
            attack_damage=c.attack_damage, attack_range=c.attack_range,
            moves_per_turn=c.moves_per_turn,
            can_move=c.can_move, can_attack=c.can_attack,
        )

    @property
    def alive(self) -> bool:
        return self.hp > 0

    def take_damage(self, amount: int, log) -> None:
        if self.wards > 0:
            self.wards -= 1
            log(f"  a ward absorbs {amount} damage (wards left: {self.wards})")
            return
        self.hp = max(0, self.hp - amount)
        log(f"  {self.name} takes {amount} damage (hp: {self.hp}/{self.max_hp})")


# ---------------------------------------------------------------------------
# Enemies
# ---------------------------------------------------------------------------
@dataclass
class Enemy:
    kind: str
    name: str
    pos: Position
    max_hp: int
    hp: int
    damage: int
    move_range: int
    glyph: str = "e"

    # archetype defaults (overridden per subclass)
    DEFAULT_HP: int = 2
    DEFAULT_DAMAGE: int = 1
    DEFAULT_MOVE: int = 1
    GLYPH: str = "e"

    @property
    def alive(self) -> bool:
        return self.hp > 0

    def take_damage(self, amount: int, log) -> None:
        self.hp = max(0, self.hp - amount)
        state = "falls silent." if self.hp == 0 else f"hp: {self.hp}/{self.max_hp}"
        log(f"  {self.name} takes {amount} damage ({state})")

    def act(self, game) -> None:  # pragma: no cover - overridden
        raise NotImplementedError


class Goon(Enemy):
    """Moves one square, always along the closest path to the pilgrim.
    Strikes for its damage when adjacent."""

    DEFAULT_HP = 2
    DEFAULT_DAMAGE = 1
    DEFAULT_MOVE = 1
    GLYPH = "g"

    def act(self, game) -> None:
        hero = game.hero
        dist = game.distance(self.pos, hero.pos)
        if dist <= 1:
            game.log(f"{self.name} strikes the pilgrim.")
            hero.take_damage(self.damage, game.log)
            return
        # close the gap one step along the shortest path
        steps = self.move_range
        while steps > 0:
            nxt = game.step_toward(self.pos, hero.pos, avoid=game.occupied(exclude=self))
            if nxt is None or nxt == self.pos:
                break
            self.pos = nxt
            steps -= 1
            if game.distance(self.pos, hero.pos) <= 1:
                break
        game.log(f"{self.name} shuffles to {self.pos}.")


class Sniper(Enemy):
    """If the pilgrim is more than `threat_range` units away, fires for its
    damage. If the pilgrim closes in, it kites — stepping away to restore
    firing distance — and falls back to a weak melee only when cornered."""

    DEFAULT_HP = 2
    DEFAULT_DAMAGE = 2
    DEFAULT_MOVE = 1
    GLYPH = "s"

    def __init__(self, *args, threat_range: int = 3, **kwargs):
        super().__init__(*args, **kwargs)
        self.threat_range = threat_range

    def act(self, game) -> None:
        hero = game.hero
        dist = game.distance(self.pos, hero.pos)
        if dist > self.threat_range:
            game.log(f"{self.name} fires from {self.pos} across {dist} tiles.")
            hero.take_damage(self.damage, game.log)
            return
        # too close — try to kite back into firing range
        away = game.step_away(self.pos, hero.pos, avoid=game.occupied(exclude=self))
        if away is not None and away != self.pos:
            self.pos = away
            game.log(f"{self.name} retreats to {self.pos}, seeking distance.")
            return
        # cornered: weak point-blank strike (half damage, min 1)
        if dist <= 1:
            hit = max(1, self.damage // 2)
            game.log(f"{self.name} is cornered and lashes out.")
            hero.take_damage(hit, game.log)
        else:
            game.log(f"{self.name} holds its position at {self.pos}.")


# ---------------------------------------------------------------------------
# Registry + factory
# ---------------------------------------------------------------------------
ENEMY_KINDS: Dict[str, Type[Enemy]] = {
    "goon": Goon,
    "sniper": Sniper,
}


def make_enemy(cfg: EnemyConfig, index: int) -> Enemy:
    cls = ENEMY_KINDS.get(cfg.kind)
    if cls is None:
        raise ValueError(
            f"Unknown enemy kind {cfg.kind!r}. "
            f"Known kinds: {sorted(ENEMY_KINDS)}"
        )
    name = cfg.name or f"{cfg.kind}-{index + 1}"
    hp = cfg.max_hp if cfg.max_hp is not None else cls.DEFAULT_HP
    dmg = cfg.damage if cfg.damage is not None else cls.DEFAULT_DAMAGE
    mv = cfg.move_range if cfg.move_range is not None else cls.DEFAULT_MOVE

    if cls is Sniper:
        tr = cfg.threat_range if cfg.threat_range is not None else 3
        return Sniper(
            kind=cfg.kind, name=name, pos=cfg.start,
            max_hp=hp, hp=hp, damage=dmg, move_range=mv,
            glyph=cls.GLYPH, threat_range=tr,
        )
    return cls(
        kind=cfg.kind, name=name, pos=cfg.start,
        max_hp=hp, hp=hp, damage=dmg, move_range=mv, glyph=cls.GLYPH,
    )
