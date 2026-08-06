/* ============================================================================
   THE COLD CITY — difficulty model
   ----------------------------------------------------------------------------
   Answers, with numbers rather than feel: is each level hard enough?

   It reads BASE / KINDS / FLOORS straight out of pilgrim.html, so the model can
   never drift from the shipped game. Edit the game, re-run this, get the truth.

       node tools/difficulty.mjs
       node tools/difficulty.mjs --verbose

   THE MODEL
   ---------
   For each level we estimate two quantities and divide them.

     clearTurns  — how long the room takes to kill
     damageTaken — what it costs you to stand there that long

     PRESSURE  P = damageTaken / effectiveHP

   P is the fraction of your health bar a level is expected to consume.
     P < 0.30   trivial   (you are never in danger)
     0.30-0.60  fair      (it costs you, you are not threatened)
     0.60-0.85  tense     (a mistake starts to matter)
     0.85-1.00  brutal    (near death on a clean run)
     P > 1.00   lethal    (the model says you die)

   The point is not that P is exact. It is that P is DERIVED, so a change to any
   enemy stat moves it, and a level that drifts out of its intended band is
   visible immediately instead of after a playtest.
   ========================================================================== */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const HTML = join(here, '..', 'pilgrim', 'web', 'pilgrim.html');
const src = readFileSync(HTML, 'utf8');

/* ---- pull the real data out of the game -------------------------------- */
function grab(pattern, label) {
  const m = src.match(pattern);
  if (!m) throw new Error(`could not find ${label} in pilgrim.html`);
  return m[0];
}
const dataJS = [
  grab(/const BASE=\{[^}]*\};/, 'BASE'),
  grab(/const KINDS=\{[\s\S]*?\n\};/, 'KINDS'),
  grab(/const FLOORS=\[[\s\S]*?\n\];/, 'FLOORS'),
  grab(/const VETERAN = [^\n]*\n/, 'VETERAN scaling'),
  grab(/FLOORS\.forEach\([^\n]*\n/, 'exit defaults'),
].join('\n');
const { BASE, KINDS, FLOORS, VETERAN } = new Function(
  `${dataJS}; return { BASE, KINDS, FLOORS, VETERAN };`
)();

/* ---- the build we assume a player is holding ----------------------------
   Skills are drafted, so difficulty depends on what they picked. These are the
   assumptions — the one genuinely subjective part of the model, kept in one
   place so they are easy to argue with and easy to change.
   `dmg` is flat damage added, `def` guard added, `hits` extra strikes,
   `hp` bonus max health. The curve mirrors the gated pools: basics early,
   a real skill or two by the mid levels, a full bar by the end.          */
/* Difficulty depends enormously on what the player drafted, so one assumed
   build hides more than it shows. We test three archetypes: a level should be
   survivable for all of them and trivial for none. `n` is the level index. */
const BUILDS = {
  // takes every damage skill, never defends
  aggressive: (n) => ({ dmg: Math.min(6, Math.floor(n * 0.6)), def: 0,
                        hits: n >= 8 ? 2 : 1, hp: 0 }),
  // spreads picks
  balanced:   (n) => ({ dmg: Math.min(4, Math.floor(n * 0.4)), def: Math.min(2, Math.floor(n / 4)),
                        hits: n >= 9 ? 2 : 1, hp: n >= 6 ? 2 : 0 }),
  // stacks guard and health
  defensive:  (n) => ({ dmg: Math.min(2, Math.floor(n * 0.2)), def: Math.min(3, Math.floor(n / 3)),
                        hits: 1, hp: n >= 5 ? 4 : 0 }),
};

/* the band each level is *meant* to sit in */
const INTENT = [
  'trivial', 'trivial', 'fair', 'fair', 'fair', 'fair',
  'tense', 'tense', 'tense', 'brutal', 'brutal', 'brutal', 'brutal',
];

/* ---- the game's own damage formula, mirrored ---------------------------- */
/* mirrors the game: a landed blow always draws at least MIN_DAMAGE, which is
   what stops a stacked guard from making anyone immortal */
const MIN_DAMAGE = 1;
function damage({ basic, extra = 0, hits = 1, def = 0, type = 'physical', amp = 1, vuln = 0 }) {
  const d = type === 'magic' ? def * 0.5 : def;
  let raw = (basic + extra) * hits - d;
  if (raw < 0) raw = 0;
  return Math.max(MIN_DAMAGE, Math.floor(raw * amp * (1 + vuln)));
}

const BAND = (p) =>
  p < 0.30 ? 'trivial' : p < 0.60 ? 'fair' : p < 0.85 ? 'tense' : p <= 1.0 ? 'brutal' : 'LETHAL';

/* ---- per-level analysis ------------------------------------------------- */
function analyse(level, i, buildFn) {
  const build = buildFn(i);
  const hp = BASE.hp + build.hp;
  const guard = BASE.def + build.def;
  const foes = (level.enemies ?? []).map(([kind, c, r, over]) => {
    const K = { ...KINDS[kind], ...(over ?? {}) };
    // the game toughens non-boss foes with depth; mirror it exactly
    return { ...K, bd: K.bd + (K.boss ? 0 : VETERAN(i)), kind, col: c, row: r };
  });

  if (!foes.length) {
    return { name: level.name, foes: 0, clearTurns: 0, taken: 0, pressure: 0,
             hp, band: 'trivial', notes: ['no foes — a walking level'] };
  }

  /* Resolve the fight turn by turn. The earlier closed form assumed every foe
     stayed alive for the whole room, which massively overstated the cost —
     things you kill stop hitting you. This walks the actual exchange:
     the pilgrim focuses the nearest arrival, and each foe that has arrived and
     is still standing applies its damage at its own rate. Deterministic, so
     it is still a model and not a simulation with dice. */
  const perFoe = foes.map((f) => {
    const hit = damage({ basic: BASE.dmg, extra: build.dmg, hits: build.hits, def: f.def });
    const perHit = damage({ basic: f.bd, def: guard, type: f.dtype });
    // how often it actually lands a blow, given how it behaves
    /* Cover is a real counter we built: walls break the sniper's line, so a
       player who uses them eats far fewer shots. Scale ranged threat by how
       much cover the level actually provides. */
    const walls = level.walls?.length ?? 0;
    const coverFactor = Math.max(0.45, 1 - walls * 0.09);
    const rate = f.ai === 'chase' ? 1.0                  // melee: every turn adjacent
               : f.ai === 'kite'  ? 0.5 * coverFactor    // reloads, and cover blocks
               : f.ai === 'shell' ? 0.15                 // only lands if you stand still
               // the Lance telegraphs a turn ahead and fires every third turn,
               // so a reader dodges most of it
               : f.ai === 'lance' ? 0.12
               : 1.0;
    // turns before it reaches / ranges you (melee walks, shooters open fire early)
    const dist = Math.round(Math.hypot(f.col - 1, f.row - 3));
    const arrive = f.ai === 'chase' ? Math.max(0, Math.floor(dist / 2)) : 0;
    return { f, hit, perHit, rate, arrive, hp: f.hp, alive: true };
  });

  /* Build the timeline. Two different clocks matter and conflating them is
     what made the first two attempts wrong:
       foeEngage    — when it can start hurting YOU
       playerEngage — when you can start hurting IT
     A melee goon meets you in the middle. A sniper shoots from turn one but
     takes a long walk to reach, and kites while you close. */
  const withTiming = perFoe.map((p) => {
    const dist = Math.round(Math.hypot(p.f.col - 1, p.f.row - 3));
    const stride = 1 + (build.move ?? 0);
    const foeEngage = p.f.ai === 'chase' ? Math.max(1, Math.floor(dist / 2)) : 1;
    const playerEngage = p.f.ai === 'chase' ? Math.max(1, Math.floor(dist / 2))
                       : p.f.ai === 'kite'  ? Math.ceil(dist * 1.6 / stride)  // it backs away
                       :                      Math.ceil(dist / stride);
    return { ...p, dist, foeEngage, playerEngage };
  });

  // you deal with them roughly in the order you can reach them
  withTiming.sort((a, b) => a.playerEngage - b.playerEngage);
  let clock = 0;
  for (const p of withTiming) {
    clock = Math.max(clock, p.playerEngage);           // walk into range
    p.killTurns = p.hit > 0 ? Math.ceil(p.f.hp / p.hit) : 99;
    clock += p.killTurns;
    p.deadAt = clock;
  }
  const clearTurns = clock;

  // each foe bills you for every turn it is both alive and engaged
  let taken = 0;
  for (const p of withTiming) {
    const active = Math.max(0, p.deadAt - p.foeEngage);
    let from = p.perHit * p.rate * active;
    if (p.f.hurl) from += p.perHit * 0.25 * active;     // the boss throws its blade too
    p.billed = from;
    taken += from;
  }
  const notes = withTiming.map((p) =>
    `${p.f.name}: ${p.perHit}/hit x${p.rate}, hurts you t${p.foeEngage}-t${p.deadAt} ` +
    `(${Math.max(0, p.deadAt - p.foeEngage)}t) = ${p.billed.toFixed(1)}; ` +
    `you reach it t${p.playerEngage}, ${p.killTurns} strikes`);

  /* Mitigation the player actually has: shrines on the level, and the breath
     of health granted between levels. Ignoring these overstated every room. */
  const shrineHeal = (level.shrines?.length ?? 0) * 3;   // expected value of a roll
  const betweenLevels = i > 0 ? 3 : 0;
  const effectiveHP = hp + shrineHeal + betweenLevels;

  const pressure = taken / effectiveHP;
  return { name: level.name, foes: foes.length, clearTurns, taken, pressure,
           hp: effectiveHP, band: BAND(pressure), notes, perFoe: withTiming };
}

/* ---- report ------------------------------------------------------------- */
const verbose = process.argv.includes('--verbose');
const NAMES = Object.keys(BUILDS);
const byBuild = Object.fromEntries(NAMES.map(n => [n, FLOORS.map((f, i) => analyse(f, i, BUILDS[n]))]));
const rows = byBuild.balanced;                       // the headline column

console.log('\n  THE COLD CITY — difficulty curve');
console.log('  pressure = share of the health bar a level is expected to cost');
console.log('  ' + '='.repeat(84));
console.log('  ' + 'level'.padEnd(12) + 'foes turns |  ' +
  NAMES.map(n => n.slice(0, 9).padEnd(10)).join('') + '|  worst      intent');
console.log('  ' + '-'.repeat(84));

const problems = [], nullified = [], unsurvivable = [];
FLOORS.forEach((_, i) => {
  const ps = NAMES.map(n => byBuild[n][i].pressure);
  const worst = Math.max(...ps), best = Math.min(...ps);
  const r = rows[i];
  console.log(
    '  ' + r.name.replace(/ —.*/, '').padEnd(12) +
    String(r.foes).padEnd(5) + String(r.clearTurns).padEnd(6) + '|  ' +
    ps.map(p => p.toFixed(2).padEnd(10)).join('') + '|  ' +
    BAND(worst).padEnd(10) + (INTENT[i] ?? '-')
  );
  if (verbose) byBuild.balanced[i].notes?.forEach(n => console.log('      · ' + n));
  if (!r.foes) return;
  /* Intent is judged against the BALANCED build — that is the design target.
     A glass cannon is *supposed* to be risky, so it is not held to the band;
     it is only flagged when a level becomes outright unsurvivable for it. */
  if (r.band !== INTENT[i]) problems.push({ i, r, worst: r.pressure, want: INTENT[i] });
  if (worst > 2.0) unsurvivable.push(
    `L${i} — P=${worst.toFixed(2)} for the ${NAMES[ps.indexOf(worst)]} build`);
  // and the real red flag: an enemy that some build reduces to zero
  for (const n of NAMES)
    for (const p of byBuild[n][i].perFoe ?? [])
      if (p.f.ai !== 'shell' && damage({ basic: p.f.bd, def: BASE.def + BUILDS[n](i).def, type: p.f.dtype }) === 0)
        nullified.push(`L${i} ${p.f.name} deals 0 to a ${n} build`);
});
console.log('  ' + '-'.repeat(84) + '\n');

if (nullified.length) {
  console.log('  !! NULLIFIED ENEMIES — subtractive guard has reduced these to zero damage');
  [...new Set(nullified)].forEach(n => console.log('     ' + n));
  console.log('');
}
if (unsurvivable.length) {
  console.log('  !! UNSURVIVABLE FOR SOME BUILD (P > 2.0 — no route through)');
  unsurvivable.forEach(u => console.log('     ' + u));
  console.log('');
}
if (problems.length) {
  console.log('  OFF-INTENT (measured on the balanced build)');
  for (const { i, r, worst, want } of problems)
    console.log(`     L${i} reads ${BAND(worst)} (P=${worst.toFixed(2)}), intended ${want}`);
  console.log('');
}

/* ---- thresholds for the adaptive hints ---------------------------------
   A hint should fire when a player is doing materially worse than the model
   says they should be — not at a number someone guessed. We take the modelled
   damage from each source and trip the hint at 1.5x that.                  */
console.log('  ADAPTIVE HINT THRESHOLDS (derived from the model, not guessed)');
console.log('  ' + '-'.repeat(78));
console.log('  a hint should fire only when a player is doing materially worse');
console.log('  than the model expects — we trip at 1.5x the expected hit count.\n');
for (const [ai, label] of [['shell', 'mortar shells landing on you'],
                           ['kite',  'sniper shots landing on you']]) {
  // count the hits the model actually expects, level by level
  const counts = [];
  for (const r of rows) {
    for (const p of r.perFoe ?? []) {
      if (p.f.ai !== ai) continue;
      counts.push(p.rate * Math.max(0, p.deadAt - p.foeEngage));
    }
  }
  if (!counts.length) continue;
  const expected = counts.reduce((a, b) => a + b, 0) / counts.length;
  const trip = Math.max(2, Math.round(expected * 1.5));
  console.log(`    ${label.padEnd(30)} expected ${expected.toFixed(1)} per foe -> hint at ${trip}`);
}
console.log('');
