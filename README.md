# THE COLD CITY

**▶ Play it: [the-cold-city.vercel.app](https://the-cold-city.vercel.app)**

> Low-res pixel melancholy meets eco-brutalist grandeur — a small, hushed
> silhouette walking through a big, indifferent world.

A turn-based tactical combat slice. One hooded pilgrim crosses a single city
district: seven floors, a skill drafted after each one, and three kinds of
enemy that each punish a different mistake.

![zones](https://img.shields.io/badge/board-12%C3%976-6f6?style=flat-square)
![floors](https://img.shields.io/badge/floors-7-a8e?style=flat-square)
![skills](https://img.shields.io/badge/skills-16-fc9?style=flat-square)

---

## The rules in brief

Each turn you may take **one step** and **one strike**, in either order. Your
turn ends on its own once you've used both — striking commits it. Clear a floor
and you draft **1 of 3** skills; you may carry **5**.

**Damage**

```
damage = ⌊ max(0, (basic + extra) × hits − defense) × amp × (1 + vulnerability) ⌋
```

Base damage `4`, defense `1`, HP `10`, MP `4`, move `1`, range `1`.
Defense is subtracted **once per attack, not per hit** — so extra hits multiply
every flat bonus and cut through armour. **Magic ignores 50% of defense**, which
is the other answer to armour.

**The enemies**

| | Behaviour | The lesson |
|---|---|---|
| **Grunt** | Takes the closest path to you; strikes when adjacent. | Positioning |
| **Archer** | Kites away, fires when you're outside its 5×5 with a clear line. Reloads between shots. | Use cover |
| **Mage** | Shells the tile where you *last stood*; its damage half-ignores your guard. | Keep moving |
| **Warden** (boss) | Heavy plate — defense 3. Blades glance off. | Magic & multi-hit |

**Terrain** — walls block the archer's line of fire · a 3×3 trap field stuns you
for a turn and decays · shrines (◆) roll a d6 for a heal or an edge.

Full reference: **[pilgrim/RULES.md](pilgrim/RULES.md)** ·
printable handout: **[pilgrim/RULES.pdf](pilgrim/RULES.pdf)**

---

## Repository

| Path | What it is |
|---|---|
| [`pilgrim/web/pilgrim.html`](pilgrim/web/pilgrim.html) | **The game.** One self-contained file — canvas renderer, rules, UI. |
| [`the-cold-city/`](the-cold-city/) | Static deploy root (a copy of the game as `index.html`). |
| [`pilgrim/`](pilgrim/) | A Python implementation of the same ruleset, for headless simulation and balance testing. |
| [`pilgrim/RULES.md`](pilgrim/RULES.md) | Complete rules reference. |

### Run the browser game locally

```bash
python3 -m http.server 8000 --directory pilgrim/web
```

Then open <http://localhost:8000/pilgrim.html>.

### Run the Python simulator

```bash
python3 -m pilgrim.play --auto     # watch it play itself
python3 -m pilgrim.play --batch 400  # win-rate over 400 games, for balancing
```

---

## Design notes

The board is rendered at a deliberate **320×180** and scaled up crisp
(`image-rendering: pixelated`). Depth comes from silhouette and parallax, not
detail. The palette is the mood: deep purples and cold cyan/magenta neon,
concrete slate softened by green terraces.

Two rules the interface follows throughout:

- **Show, don't tell.** Damage lands as impact — a white hit-flash, a camera
  kick, a floating number, HP ticks that ghost out on hover to preview a blow.
  No arithmetic on the play surface; the formula lives in the rules panel.
- **Teach at the moment of use.** No wall of text up front. Speech bubbles are
  anchored to the thing they describe, one idea per beat, gated on the action
  you just took — and MP is only explained the first time you own a spell.
