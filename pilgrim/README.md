# pilgrim — a turn-based combat simulation on a 5×7 grid

> Low-res pixel melancholy meets eco-brutalist grandeur — one small hooded
> silhouette crossing a monumental, indifferent world that slowly warms.

A configurable, scriptable engine for simulating turn-based grid combat.
You describe the hero, the enemies, the shrines, the turn order, and the
dice-roll powerups; the engine plays it out. Win by defeating every enemy.

## Run it

```bash
python3 -m pilgrim.play            # play by hand
python3 -m pilgrim.play --auto     # watch the auto-pilgrim
python3 -m pilgrim.play --auto --seed 1     # reproducible run
python3 -m pilgrim.play --batch 400         # win-rate over 400 auto games
python3 -m pilgrim.play --no-color          # plain text (piping / tests)
```

The board's 7 rows are the palette's dusk-to-dawn color script: **slums**
(bottom, smoggy slate) → **city** (middle, oppressive purple/neon) →
**oasis** (top, teal & gold, the eco-brutalist castle). The pilgrim `@`
starts small at the bottom and the world warms as she climbs. `◆` = shrine,
`g` = goon, `s` = sniper.

## The default scenario

- **Grid** 5 wide × 7 tall, Manhattan distance, no diagonal movement.
- **Pilgrim** starts bottom-center `(2,6)`, 10 HP, 1 move + 1 melee attack
  per turn, range 1.
- **Two goons** at `(2,4)` and `(3,2)`; **one sniper** atop the castle `(2,0)`.
- **Two shrines** on the central column `(2,5)` and `(2,3)` — the pilgrim's
  natural path up, so she gathers power as she climbs.
- Balanced to ~83% auto-win over 400 games (bad dice can still doom you).

## How the pieces behave

| Piece | Rule |
|-------|------|
| **Pilgrim** | Each turn: move up to `moves_per_turn` squares **and** make one attack (adjacent by default). Landing on a shrine rolls a d6 for a powerup. |
| **Goon** | Moves one square along the closest path to the pilgrim. Strikes for 1 when adjacent. |
| **Sniper** | If the pilgrim is **more than 3 units away**, fires for 2. If she closes in, it *kites* — stepping away to restore firing range — and only lashes out weakly when cornered. |

## The d6 powerup table (shrines)

| Roll | Powerup | Effect |
|------|---------|--------|
| 1 | Whisper | nothing — the world stays quiet |
| 2 | Mend    | +2 max HP and full heal |
| 3 | Reach   | melee becomes ranged (range 2) |
| 4 | Stride  | +1 movement next turn |
| 5 | Ward    | block the next incoming hit |
| 6 | Bloom   | next attack hits all adjacent tiles |

## Describing your own game

Everything is plain dataclasses in [`config.py`](config.py). Build a
`GameConfig` and pass it to `Game`:

```python
from pilgrim import (Game, GameConfig, GridConfig, HeroConfig,
                     EnemyConfig, PowerSquareConfig, TurnConfig)
from pilgrim.play import auto_controller, play

cfg = GameConfig(
    grid=GridConfig(width=5, height=7, distance="manhattan"),
    hero=HeroConfig(start=(2, 6), max_hp=12, moves_per_turn=1, attack_range=1),
    enemies=[
        EnemyConfig(kind="goon",   start=(1, 4)),
        EnemyConfig(kind="goon",   start=(3, 4)),
        EnemyConfig(kind="sniper", start=(2, 0), threat_range=3, damage=2),
    ],
    power_squares=PowerSquareConfig(positions=[(2, 5), (2, 3)],
                                    consume_on_use=True),
    turns=TurnConfig(order=["hero", "enemies"], max_rounds=100),
    seed=1,
)

play(cfg, auto=True)                 # or interactive: play(cfg)
# or drive it yourself:
result = Game(cfg).run(auto_controller)   # 'win' | 'loss' | 'timeout'
```

**Knobs you control:**
- **Enemy count / type / placement** — the `enemies` list. Per-enemy
  overrides: `max_hp`, `damage`, `move_range`, `threat_range` (sniper).
- **Turn systems** — `TurnConfig.order` (e.g. `["enemies", "hero"]` to let
  foes act first). Enemy behavior is per-archetype; the hero's turn is
  driven by a *controller* (human, auto, or your own function).
- **Shrine placement** — `PowerSquareConfig.positions`; `consume_on_use`
  makes them one-shot or reusable.
- **Powerups** — `PowerupTableConfig.faces` maps each die face to a powerup
  key; `die_sides` changes the die.
- **Hero turn** — `moves_per_turn`, `attack_range`, `attack_damage`,
  `can_move`, `can_attack`.

## Extending it

- **New enemy type** — subclass `Enemy` in [`entities.py`](entities.py),
  implement `act(self, game)` using the engine helpers (`game.distance`,
  `game.step_toward`, `game.step_away`, `game.hero`), and register it in
  `ENEMY_KINDS`. It's then usable as `EnemyConfig(kind="your_kind", ...)`.
- **New powerup** — write an effect function in [`powerups.py`](powerups.py),
  add it to `POWERUPS`, and point a die face at its key in the config.
- **New hero controller** — any `fn(game) -> None` that calls
  `game.move_hero_to(...)` / `game.hero_attack(...)`. See
  `auto_controller` in [`play.py`](play.py).

## Files

| File | Purpose |
|------|---------|
| [`config.py`](config.py) | All tunable dataclasses + `default_config()` |
| [`entities.py`](entities.py) | Hero, Enemy, Goon, Sniper, registry |
| [`powerups.py`](powerups.py) | Powerup effects + d6 table |
| [`game.py`](game.py) | Engine: geometry, turn loop, combat, resolution |
| [`render.py`](render.py) | Themed ASCII renderer + poetic interstitials |
| [`play.py`](play.py) | CLI: interactive / auto / batch controllers |
