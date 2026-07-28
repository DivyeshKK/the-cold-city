"""
pilgrim — a configurable turn-based combat simulation on a 5x7 grid.

Low-res pixel melancholy meets eco-brutalist grandeur: one small hooded
silhouette crossing a monumental, indifferent world that slowly warms.

Quick start:
    from pilgrim import Game, default_config
    from pilgrim.play import auto_controller
    game = Game(default_config())
    print(game.run(auto_controller))   # 'win' | 'loss' | 'timeout'
"""

from .config import (
    EnemyConfig,
    GameConfig,
    GridConfig,
    HeroConfig,
    PowerSquareConfig,
    PowerupTableConfig,
    TurnConfig,
    default_config,
)
from .game import Game

__all__ = [
    "Game",
    "GameConfig",
    "GridConfig",
    "HeroConfig",
    "EnemyConfig",
    "PowerSquareConfig",
    "PowerupTableConfig",
    "TurnConfig",
    "default_config",
]
