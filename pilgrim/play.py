"""
Entry point: play the pilgrimage by hand, watch it play itself, or batch-
simulate for balancing.

    python -m pilgrim.play              # interactive
    python -m pilgrim.play --auto       # watch the auto-pilgrim
    python -m pilgrim.play --auto --seed 7
    python -m pilgrim.play --batch 500  # win-rate over 500 auto games
    python -m pilgrim.play --no-color   # plain text (piping / tests)
"""

from __future__ import annotations

import argparse
from typing import Optional

from .config import GameConfig, default_config
from .game import Game
from .render import interstitial, render


# ---------------------------------------------------------------------------
# Controllers
# ---------------------------------------------------------------------------
def auto_controller(game: Game) -> None:
    """A quiet, competent pilgrim: strike what's in reach, else close on the
    nearest foe, spending the whole movement budget."""
    def try_attack() -> bool:
        targets = game.hero_attack_targets()
        if targets:
            game.hero_attack(min(targets, key=lambda e: e.hp))
            return True
        return False

    try_attack()
    while game.hero_moves_left > 0 and game.enemies_alive:
        nearest = min(game.enemies_alive,
                      key=lambda e: game.distance(game.hero.pos, e.pos))
        step = game.step_toward(game.hero.pos, nearest.pos,
                                avoid=game.occupied(exclude=game.hero))
        if step is None or not game.move_hero_to(step):
            break
        if game.hero_attacked:
            continue
        try_attack()
    try_attack()


def human_controller(color: bool = True):
    def controller(game: Game) -> None:
        while True:
            print(render(game, color=color))
            moves = game.hero_move_options()
            targets = game.hero_attack_targets()
            print(f"\n  YOUR TURN  (moves left: {game.hero_moves_left})")
            opts = []
            for m in moves:
                opts.append(("move", m))
                print(f"    [{len(opts)}] move -> {m}")
            for t in targets:
                opts.append(("attack", t))
                print(f"    [{len(opts)}] strike {t.name} "
                      f"({t.hp}hp @ {t.pos})")
            print("    [0] end turn")
            choice = input("  > ").strip()
            if choice in ("0", "", "end"):
                return
            if not choice.isdigit() or not (1 <= int(choice) <= len(opts)):
                print("  (the wind takes your words. try again.)")
                continue
            kind, val = opts[int(choice) - 1]
            if kind == "move":
                game.move_hero_to(val)
            else:
                game.hero_attack(val)
            if not game.enemies_alive:
                return
            if game.hero_moves_left <= 0 and not game.hero_attack_targets():
                return
    return controller


# ---------------------------------------------------------------------------
# Runners
# ---------------------------------------------------------------------------
def play(config: Optional[GameConfig] = None, auto: bool = False,
         color: bool = True) -> str:
    config = config or default_config()
    log = (lambda m: print(m)) if not auto else (lambda m: print(m))
    game = Game(config, log=log)

    print(interstitial("start", color))
    controller = auto_controller if auto else human_controller(color)
    result = game.run(controller)

    print(render(game, color=color))
    print(interstitial(result, color))
    print(f"  [{result.upper()} · {game.round} rounds]")
    return result


def batch(n: int, config: Optional[GameConfig] = None) -> None:
    """Run n auto games silently; report the win/loss/timeout split.
    Useful for balancing the ruleset (enemy counts, HP, powerup table)."""
    base = config or default_config()
    tally = {"win": 0, "loss": 0, "timeout": 0}
    rounds_total = 0
    for i in range(n):
        cfg = GameConfig(
            grid=base.grid, hero=base.hero, enemies=base.enemies,
            power_squares=base.power_squares, powerups=base.powerups,
            turns=base.turns, seed=i,  # vary the dice/placement per run
        )
        game = Game(cfg)  # no log sink -> silent
        result = game.run(auto_controller)
        tally[result] += 1
        rounds_total += game.round
    print(f"  {n} auto games:")
    for k in ("win", "loss", "timeout"):
        pct = 100 * tally[k] / n
        print(f"    {k:8s} {tally[k]:4d}  ({pct:5.1f}%)")
    print(f"    avg rounds: {rounds_total / n:.1f}")


def main() -> None:
    ap = argparse.ArgumentParser(description="pilgrimage combat simulation")
    ap.add_argument("--auto", action="store_true", help="auto-play the pilgrim")
    ap.add_argument("--batch", type=int, metavar="N",
                    help="run N silent auto games, report win rate")
    ap.add_argument("--seed", type=int, help="fix the RNG for reproducibility")
    ap.add_argument("--no-color", action="store_true", help="plain-text output")
    args = ap.parse_args()

    cfg = default_config()
    if args.seed is not None:
        cfg.seed = args.seed

    if args.batch:
        batch(args.batch, cfg)
    else:
        play(cfg, auto=args.auto, color=not args.no_color)


if __name__ == "__main__":
    main()
