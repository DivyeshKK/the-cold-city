"""
Terminal renderer — low-res pixel melancholy in ASCII.

The board's 7 rows are the palette's dusk-to-dawn color script:
    rows 0-1  OASIS  · teal/gold, the castle & hanging gardens
    rows 2-4  CITY   · deep purple, cold neon, oppressive
    rows 5-6  SLUMS  · muted browns/slate, smoggy haze

Type is all-caps monospace, low and quiet. The interface whispers.
Colors use ANSI; pass color=False for plain text (logs, tests, piping).
"""

from __future__ import annotations

from typing import Dict, Tuple

from .game import Game

# ANSI palette (approximate; the mood, not the spec)
_C = {
    "oasis": "\033[38;5;79m",   # teal-green
    "gold":  "\033[38;5;222m",
    "city":  "\033[38;5;97m",   # muted purple
    "neon":  "\033[38;5;207m",  # magenta
    "slums": "\033[38;5;101m",  # slate-brown
    "haze":  "\033[38;5;240m",
    "hero":  "\033[38;5;231m",  # bright silhouette highlight
    "enemy": "\033[38;5;203m",
    "shrine": "\033[38;5;186m",
    "dim":   "\033[2m",
    "reset": "\033[0m",
}


def _zone(y: int, height: int) -> str:
    frac = y / max(1, height - 1)
    if frac <= 0.28:
        return "oasis"
    if frac <= 0.64:
        return "city"
    return "slums"


ZONE_LABEL = {"oasis": "OASIS", "city": "CITY", "slums": "SLUMS"}
ZONE_FILL = {"oasis": "\"", "city": "·", "slums": ":"}  # drifting motes / haze


def render(game: Game, color: bool = True) -> str:
    def c(key: str, s: str) -> str:
        return f"{_C[key]}{s}{_C['reset']}" if color else s

    g = game.grid
    # locate occupants
    occ: Dict[Tuple[int, int], str] = {}
    for e in game.enemies:
        if e.alive:
            occ[e.pos] = ("enemy", e.glyph)
    if game.hero.alive:
        occ[game.hero.pos] = ("hero", game.hero.glyph)

    lines = []
    lines.append(c("dim", "  " + "─" * (g.width * 2 + 1)))
    last_zone = None
    for y in range(g.height):
        zone = _zone(y, g.height)
        row_cells = []
        for x in range(g.width):
            pos = (x, y)
            if pos in occ:
                key, glyph = occ[pos]
                row_cells.append(c(key, glyph))
            elif pos in game.power_squares:
                row_cells.append(c("shrine", "◆"))
            else:
                fill = ZONE_FILL[zone]
                row_cells.append(c("haze" if zone == "slums" else zone, fill))
        label = ""
        if zone != last_zone:
            label = c("dim", f"  {ZONE_LABEL[zone]}")
            last_zone = zone
        lines.append(c("dim", "  │") + " ".join(row_cells) + c("dim", "│") + label)
    lines.append(c("dim", "  " + "─" * (g.width * 2 + 1)))

    # status — terminal-minimal, low-opacity
    h = game.hero
    hp_bar = "▮" * h.hp + "▯" * (h.max_hp - h.hp)
    status = (f"  {h.name.upper()}  HP {hp_bar} {h.hp}/{h.max_hp}"
              f"   RANGE {h.attack_range}"
              f"{'  WARD ' + str(h.wards) if h.wards else ''}"
              f"{'  BLOOM ' + str(h.bloom_charges) if h.bloom_charges else ''}")
    foes = ", ".join(f"{e.name}({e.hp})" for e in game.enemies_alive) or "—"
    lines.append(c("dim", status))
    lines.append(c("dim", f"  FOES  {foes}"))
    return "\n".join(lines)


# Sparse poetic interstitials — printed on milestones, never as menus.
INTERSTITIALS = {
    "start": "a small silhouette against a monumental world. you cross it anyway.",
    "win": "the tyrant's reign ends where you stand. the palette warms to gold.",
    "loss": "the world stays indifferent. the smog closes over a quiet shape.",
    "timeout": "the light neither breaks nor fades. you walk on, unresolved.",
}


def interstitial(key: str, color: bool = True) -> str:
    text = INTERSTITIALS.get(key, "")
    s = f"\n  “{text.upper()}”\n"
    return f"{_C['gold']}{s}{_C['reset']}" if color else s
