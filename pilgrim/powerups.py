"""
Powerups the pilgrim can receive from a dice roll on a power-square.

Each effect mutates the Hero. Add your own by writing a small function and
registering it in POWERUPS; then point a die face at its key in
config.PowerupTableConfig.faces.
"""

from __future__ import annotations

from typing import Dict

from .config import Powerup


# --- effect functions ------------------------------------------------------
def _whisper(hero) -> None:
    # Nothing. The world stays quiet. (Kept as an effect so the table is
    # uniform and so you can hook flavor/telemetry onto "nothing" too.)
    pass


def _mend(hero) -> None:
    hero.max_hp += 2
    hero.hp = hero.max_hp


def _reach(hero) -> None:
    # A lasting upgrade: melee reach becomes ranged.
    hero.attack_range = max(hero.attack_range, 2)


def _stride(hero) -> None:
    # Temporary: +1 movement for the hero's next turn only. The engine
    # decrements bonus_moves back to 0 at end of the hero's turn.
    hero.bonus_moves += 1


def _ward(hero) -> None:
    # Charges that each block one instance of incoming damage.
    hero.wards += 1


def _bloom(hero) -> None:
    # Arms a one-shot area strike: the hero's next attack hits every
    # adjacent tile. Consumed by the engine when spent.
    hero.bloom_charges += 1


# --- registry --------------------------------------------------------------
POWERUPS: Dict[str, Powerup] = {
    "whisper": Powerup("whisper", "A Whisper",
                       "the wind carries nothing. you keep walking.", _whisper),
    "mend": Powerup("mend", "Mend",
                    "green terraces breathe; you stand a little taller.", _mend),
    "reach": Powerup("reach", "Reach",
                     "distance folds. your strike learns to travel.", _reach),
    "stride": Powerup("stride", "Stride",
                      "the road shortens beneath a quicker step.", _stride),
    "ward": Powerup("ward", "Ward",
                    "concrete softens around you; one blow will pass.", _ward),
    "bloom": Powerup("bloom", "Bloom",
                     "light gathers, ready to break outward all at once.", _bloom),
}


def resolve(key: str) -> Powerup:
    """Look up a powerup by key, defaulting to the quiet 'whisper'."""
    return POWERUPS.get(key, POWERUPS["whisper"])
