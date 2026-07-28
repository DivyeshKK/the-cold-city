# THE COLD CITY — Game Rules & Moves

*A turn-based tactical combat slice. One hooded pilgrim crosses a single monumental
city district and must defeat every enemy to survive.*

---

## 1. Objective

- **Win:** defeat all three enemies (the Goon, the Mortar, and the Sniper).
- **Lose:** the Pilgrim's health reaches 0.

## 2. The Board

- A grid **12 tiles wide × 6 tiles tall** (landscape).
- Movement is **orthogonal only** — up, down, left, right. No diagonal steps.
- **Attack range** is measured in "king moves" (Chebyshev distance): a range of 1
  reaches all **8 surrounding tiles**, so you can strike a diagonally-adjacent foe.
- Only **one unit may occupy a tile** at a time. Walls are solid and block movement.

## 3. Turn Structure

Play alternates between the Pilgrim's turn and the enemies' turn.

1. **Pilgrim's turn** — you may take **up to one step and up to one strike, in either
   order** (move then attack, or attack then move, or just one, or neither). Your turn
   **ends automatically** once you have used both actions, or when no action remains.
   The **End Turn** control lets you deliberately skip a leftover action.
2. **Enemies' turn** — every living enemy acts once, resolved in this order:
   **Sniper → Mortar → Goon.**

Then the round counter advances and control returns to the Pilgrim.

## 4. The Pilgrim (you)

| Attribute | Value |
|---|---|
| Starting health | 10 (maximum 10) |
| Strike damage | 2 |
| Strike range | 1 (any adjacent tile, including diagonals) |
| Movement | 1 tile per turn (orthogonal) |
| Starting position | column 1, row 3 |

**Your moves each turn:**
- **Step** — move one orthogonal tile to an empty, in-bounds, non-wall tile.
- **Strike** — deal 2 damage to one enemy within range (adjacent by default).
- **End turn** — pass, skipping any unused step or strike.

## 5. The Enemies

Each enemy has **3 health**. Defeating all three wins the game.

### Goon — the chaser
- **Damage:** 1. **Movement:** 1 tile per turn.
- Each turn it takes the **closest path toward the Pilgrim**, routing *around* walls.
- If it is orthogonally adjacent to the Pilgrim, it **strikes for 1** instead of moving.

### Mortar — the artillery
- **Damage:** 3. **Movement:** none (stationary).
- Every turn it shells **the tile where the Pilgrim last stood** (the Pilgrim's
  position at the start of the turn). A **reticle** marks that tile in advance.
- **Counter-play:** if you **step** during your turn you leave that tile, so the shell
  craters empty ground. You may still strike the same turn — moving and attacking
  together lets you deal damage *and* dodge the mortar. Only standing still (striking
  without stepping, or being stunned) lets the shell find you.

### Sniper — the marksman
- **Damage:** 2. **Movement:** 1 tile per turn.
- Every turn it **steps away** from the Pilgrim, trying to keep its distance (it "kites").
- It **fires for 2** whenever the Pilgrim is **outside its 5×5 watch** — i.e. more than
  2 tiles away in any direction (Chebyshev distance > 2) — **and** it has a clear line
  of sight.
- **Counter-play:** get inside the 5×5 (within 2 tiles) to stop its fire, break its line
  of sight behind **cover**, or herd it into a wall/board corner where it can no longer
  retreat, then finish it.

## 6. Terrain & Hazards

### Walls / Cover
- Solid concrete tiles. They are **impassable** for every unit and **block the Sniper's
  line of fire.** Advancing behind cover is the main defense against the Sniper.

### Trap
- A **3×3 field** on the board. The first time the Pilgrim **steps into** the field
  (entering from outside), the Pilgrim is **stunned**: on the next turn they **cannot
  step** (they may still strike or end the turn).
- The trap **decays over roughly 8 rounds** and then disappears.

### Shrines
- Marked tiles (◆). **End a step on a shrine** to **roll a six-sided die** for a power
  (see below). Each shrine is **consumed** after one use.

## 7. Powerups (roll 1d6 at a shrine)

| Roll | Power | Effect |
|---|---|---|
| 1 | **Whisper** | Nothing happens. |
| 2 | **Mend** | +2 maximum health and heal to full. |
| 3 | **Reach** | Strike range becomes 2 (you can hit foes two tiles away). |
| 4 | **Edge** | +1 strike damage (permanent). |
| 5 | **Ward** | Block the next incoming hit entirely (stacks if rolled again). |
| 6 | **Bloom** | Your next strike hits **all** foes within range at once (one use). |

## 8. Controls

- **Click a tile** to step there · **click a foe** in range to strike it.
- **WASD / Arrow keys** — step. **Space / Enter** — end turn. **R** — restart.

## 9. Default Scenario (starting layout)

Coordinates are (column, row); columns 0–11 left→right, rows 0–5 top→bottom.

| Piece | Position(s) |
|---|---|
| Pilgrim | (1, 3) |
| Goon | (7, 3) |
| Mortar | (10, 1) |
| Sniper | (11, 4) |
| Walls (cover) | (5,1) (5,2) (6,2) (6,4) (8,1) (8,4) (9,2) |
| Trap (3×3, centered) | (4, 3) |
| Shrines | (2, 1) and (3, 5) |

---

### Design summary

The core tension is that all three enemies punish standing still or staying in the open,
while the Pilgrim moves and strikes only once per turn. You survive by **using cover**
against the Sniper, **staying mobile** against the Mortar, and **choosing when to trade
blows** with the Goon — earning the occasional shrine power to tip the odds.
