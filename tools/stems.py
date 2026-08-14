"""
THE COLD CITY — adaptive score stems.

Everything is F major / F Lydian at 72 BPM, 16 bars (53.333 s), so any stem
layers under any other. Intensity comes from density and register, never tempo.

The warmth arc is harmonic, not just timbral:
    cold  = root, fifth, octave, and the Lydian #11 (B). No third.
    warm  = the third (A) and the sixth/ninth (D, G) arrive. Fmaj7 opens up.
Boss material darkens to F7 (adds Eb) without leaving the key.

SEAMLESS LOOPING: a sustained tone only loops cleanly if it completes a whole
number of cycles in the loop. Every frequency is snapped to the nearest such
value (resolution 1/53.333 = 0.019 Hz, far below audibility). Decaying sounds
are rendered past the loop end and the tail is folded back onto the start.
"""
import numpy as np, wave, struct, os

SR       = 44100
BPM      = 72.0
BARS     = 16
BEATS    = BARS * 4
LOOP_DUR = BEATS * 60.0 / BPM          # 53.3333 s
LOOP_N   = int(round(LOOP_DUR * SR))
BEAT_N   = LOOP_N // int(BEATS)
OUT      = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stems')
os.makedirs(os.path.join(OUT, 'sfx'), exist_ok=True)

T = np.arange(LOOP_N) / SR             # loop time base

# ---------------------------------------------------------------- pitch ----
def hz(name):
    """Scientific pitch -> Hz. C4 = middle C, A4 = 440."""
    step = {'C':0,'D':2,'E':4,'F':5,'G':7,'A':9,'B':11}
    n, acc, octv = name[0], 0, int(name[-1])
    if '#' in name: acc = 1
    if 'b' in name: acc = -1
    semis = step[n] + acc + (octv + 1) * 12          # MIDI number
    return 440.0 * 2 ** ((semis - 69) / 12)

def snap(f):
    """Nearest frequency completing whole cycles in the loop — kills the click."""
    return max(1, round(f * LOOP_DUR)) / LOOP_DUR

# ------------------------------------------------------------ generators ----
def sine(f, amp=1.0, phase=0.0, n=None):
    t = T if n is None else np.arange(n) / SR
    return amp * np.sin(2 * np.pi * snap(f) * t + phase)

def lfo(cycles, lo=0.0, hi=1.0, phase=0.0):
    """Amplitude LFO doing a whole number of cycles per loop, so it also loops."""
    w = (np.sin(2 * np.pi * cycles * T / LOOP_DUR + phase) + 1) / 2
    return lo + (hi - lo) * w

def stack(f, amps, detune=0.0):
    """Additive tone: harmonic series with the given amplitudes."""
    out = np.zeros(LOOP_N)
    for i, a in enumerate(amps, start=1):
        if a == 0: continue
        out += sine(f * i, a)
        if detune:
            out += sine(f * i * (1 + detune), a * 0.5)
            out += sine(f * i * (1 - detune), a * 0.5)
    return out

def lowpass(x, cutoff):
    """One-pole lowpass, run twice for a gentler 12 dB/oct slope."""
    a = np.exp(-2 * np.pi * cutoff / SR)
    for _ in range(2):
        y = np.empty_like(x); acc = 0.0
        for i in range(len(x)):                      # vectorised below
            acc = (1 - a) * x[i] + a * acc
            y[i] = acc
        x = y
    return x

def lowpass_fast(x, cutoff):
    """FFT-domain one-pole equivalent — same curve, no Python loop."""
    n = len(x)
    freqs = np.fft.rfftfreq(n, 1 / SR)
    H = 1.0 / (1.0 + (freqs / max(cutoff, 1.0)) ** 2)      # ~12 dB/oct
    return np.fft.irfft(np.fft.rfft(x) * H, n)

def highpass_fast(x, cutoff):
    n = len(x)
    freqs = np.fft.rfftfreq(n, 1 / SR)
    H = 1.0 - 1.0 / (1.0 + (freqs / max(cutoff, 1.0)) ** 2)
    return np.fft.irfft(np.fft.rfft(x) * H, n)

def noise_loop(seed, cutoff, hp=None):
    """Noise generated at loop length then filtered in the frequency domain —
       circular by construction, so it loops with no seam at all."""
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(LOOP_N)
    x = lowpass_fast(x, cutoff)
    if hp: x = highpass_fast(x, hp)
    m = np.max(np.abs(x))
    return x / m if m > 0 else x

def pluck(freq, dur, amp=1.0, harmonics=(1.0, .45, .22, .11, .06), bright=1.0):
    """One decaying note. Higher harmonics die faster, as they do on a string.
       Frequency is snapped like the drones so a tail that wraps past the loop
       point lands back in phase with itself instead of beating against it."""
    freq = snap(freq)
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for i, a in enumerate(harmonics, start=1):
        decay = np.exp(-t * (2.2 + i * 1.5) / bright)
        out += a * np.sin(2 * np.pi * freq * i * t) * decay
    attack = np.minimum(1.0, t / 0.004)              # 4 ms, no click
    return amp * out * attack / max(1e-9, np.max(np.abs(out)))

def place(buf, sig, at):
    """Drop a sound in at sample `at`, wrapping its tail around the loop point."""
    n = len(sig)
    idx = (np.arange(n) + at) % LOOP_N
    np.add.at(buf, idx, sig)

# ------------------------------------------------------------ harmony ------
"""A four-chord progression, four bars each, filling the 16-bar loop.

   The first version of this score sat on a single F chord for the whole 53
   seconds. That is what made it read as ambient rather than as music: no
   harmonic movement and no rhythm, so nothing ever arrived. Motion comes from
   HARMONY and ARPEGGIATION, not from adding a drum kit — the early floors stay
   percussion-free on purpose, so the first kick in the game is still the boss.

   Cold voicings omit the third everywhere (fifths, fourths and ninths only),
   so the progression moves while the world still feels unresolved. Warm
   voicings are the same roots with the thirds and sevenths filled in."""
PROG = ['F', 'Dm', 'Bb', 'C']                       # 4 bars each
COLD_VOICING = {                                    # no thirds anywhere
    'F' : ['F2','C3','G3','F3'],                    # F5 add9
    'Dm': ['D2','A2','E3','D3'],                    # D5 add9
    'Bb': ['Bb1','F2','C3','Bb2'],                  # Bb5 add9
    'C' : ['C2','G2','F3','D3'],                    # Csus4 add9
}
WARM_VOICING = {
    'F' : ['F2','A2','C3','E3','G3'],               # Fmaj9
    'Dm': ['D2','F2','A2','C3','E4'],               # Dm9
    'Bb': ['Bb1','D3','F3','A3'],                   # Bbmaj7
    'C' : ['C2','E3','G3','A3','D4'],               # C6/9
}
ARP_COLD = {'F':['F3','C4','G4','C4'], 'Dm':['D3','A3','E4','A3'],
            'Bb':['Bb2','F3','C4','F3'], 'C':['C3','G3','D4','G3']}
ARP_WARM = {'F':['F3','A3','C4','E4'], 'Dm':['D3','F3','A3','C4'],
            'Bb':['Bb2','D3','F3','A3'], 'C':['C3','E3','G3','A3']}

CHORD_BEATS = int(BEATS) // len(PROG)               # 16 beats = 4 bars each

def pad_chord(buf, notes, start_beat, len_beats, amp=1.0, harmonics=(1.0,.3,.12,.05),
              attack=0.9, release=2.2):
    """One sustained chord with a soft swell, wrapped so the last chord's tail
       flows back into the first — the loop point lands mid-progression and you
       cannot hear where it is."""
    n = int((len_beats * 60.0 / BPM + release) * SR)
    t = np.arange(n) / SR
    env = np.minimum(1.0, t / attack)
    hold = len_beats * 60.0 / BPM
    env *= np.where(t < hold, 1.0, np.exp(-(t - hold) / (release / 3)))
    sig = np.zeros(n)
    for note in notes:
        f = snap(hz(note))
        for i, a in enumerate(harmonics, start=1):
            sig += a * np.sin(2 * np.pi * f * i * t) / len(notes)
    place(buf, sig * env * amp, int(start_beat * BEAT_N))

def arpeggio(buf, table, amp=0.5, step=0.5, bright=2.6, dur=1.1):
    """Eighth-note arpeggio across the progression. This is the single thing
       that stopped the beds feeling like weather and started them feeling like
       a piece of music — rhythm without a single drum."""
    per = int(step * BEAT_N)
    for b in range(int(BEATS / step)):
        beat = b * step
        chord = PROG[int(beat // CHORD_BEATS) % len(PROG)]
        seq = table[chord]
        note = seq[b % len(seq)]
        # a gentle swing in emphasis so it breathes instead of machine-gunning
        a = amp * (1.0 if b % 4 == 0 else 0.62 if b % 2 == 0 else 0.42)
        place(buf, pluck(hz(note), dur, amp=a,
                         harmonics=(1.0,.20,.08,.03), bright=bright), b * per)

def hit(seed, dur, cutoff, amp=1.0, hp=None, curve=6.0):
    """Percussive noise burst — kick body, breath, cymbal-ish depending on args."""
    n = int(dur * SR)
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(n)
    f = np.fft.rfftfreq(n, 1 / SR)
    H = 1.0 / (1.0 + (f / max(cutoff, 1.0)) ** 2)
    if hp: H *= 1.0 - 1.0 / (1.0 + (f / hp) ** 2)
    x = np.fft.irfft(np.fft.rfft(x) * H, n)
    env = np.exp(-np.arange(n) / SR * curve)
    x *= env
    m = np.max(np.abs(x))
    return amp * x / m if m > 0 else x

# ------------------------------------------------------------- rendering ----
def stereo(left, right=None, width=0.25):
    """Gentle Haas-style width: a few ms of delay on one side, nothing extreme."""
    if right is None:
        d = int(width * 0.011 * SR)
        right = np.roll(left, d)
    return np.stack([left, right], axis=1)

def write(name, sig, peak=0.7):
    sig = np.asarray(sig, dtype=np.float64)
    if sig.ndim == 1: sig = stereo(sig)
    m = np.max(np.abs(sig))
    if m > 0: sig = sig / m * peak
    data = (sig * 32767).astype('<i2')
    path = os.path.join(OUT, name)
    with wave.open(path, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(data.tobytes())
    return path

# ================================================================ STEMS ====

def bed_cold():
    """Floors 0-8. Fifths, fourths and ninths — no third anywhere, so the
       progression moves without ever resolving. Arpeggio carries the pulse."""
    x = np.zeros(LOOP_N)
    for i, chord in enumerate(PROG):
        pad_chord(x, COLD_VOICING[chord], i*CHORD_BEATS, CHORD_BEATS,
                  amp=1.0, harmonics=(1.0,.30,.12,.05))
    arpeggio(x, ARP_COLD, amp=0.34, bright=2.2, dur=1.0)
    x += sine(hz('B4'), .030) * lfo(8, .0, 1.0, phase=.7)      # the #11 glint
    x += sine(hz('C5'), .022) * lfo(7, .0, 1.0, phase=3.4)
    x += noise_loop(11, 3800, hp=900) * 0.026 * lfo(2, .5, 1.0)   # tape hiss
    x += noise_loop(12, 260) * 0.045 * lfo(3, .4, 1.0, phase=1.7)  # room rumble
    return x

def bed_warm():
    """Floors 9-18. Same roots and the same rhythm, so it crossfades with the
       cold bed — but the thirds and sevenths fill in and the world stops
       being indifferent."""
    x = np.zeros(LOOP_N)
    for i, chord in enumerate(PROG):
        pad_chord(x, WARM_VOICING[chord], i*CHORD_BEATS, CHORD_BEATS,
                  amp=1.0, harmonics=(1.0,.26,.10,.04))
    arpeggio(x, ARP_WARM, amp=0.40, bright=3.0, dur=1.3)
    x += sine(hz('C5'), .035) * lfo(9, .1, 1.0, phase=.9)
    x += sine(hz('A4'), .040) * lfo(7, .1, 1.0, phase=2.6)
    x += noise_loop(21, 2400, hp=500) * 0.022 * lfo(2, .6, 1.0)
    x += noise_loop(22, 200) * 0.040 * lfo(3, .5, 1.0, phase=2.0)
    return x

def pulse():
    """Enemy phase. A low heartbeat under whatever bed is playing — the city
       acting. Sits deliberately low so it adds weight, not melody."""
    x = np.zeros(LOOP_N)
    for b in range(int(BEATS)):
        at = b * BEAT_N
        body = hit(100 + b, 0.42, 150, amp=0.95, curve=7.0)
        tone = pluck(hz('F1'), 0.42, amp=0.55, harmonics=(1.0, .30, .10), bright=1.4)
        place(x, body[:len(tone)] * 0.7 + tone * 0.8, at)
        if b % 4 in (1, 3):                                   # soft breath off-beat
            place(x, hit(500 + b, 0.30, 2600, amp=0.16, hp=700, curve=9.0),
                  at + BEAT_N // 2)
    x += noise_loop(31, 120) * 0.05 * lfo(4, .4, 1.0)
    return x

def tension():
    """Low HP, or a foe adjacent. B against C — the #11 grinding on the fifth.
       Deliberately lives ABOVE the beds: the low end is already occupied, and a
       stem that competes for it just makes the mix muddy instead of anxious."""
    swell = lfo(6, .10, 1.0)
    x  = sine(hz('B4'), .55) * swell
    x += sine(hz('C5'), .48) * lfo(6, .10, 1.0, phase=.35)     # semitone beating
    x += sine(hz('B5'), .26) * lfo(13, .0, 1.0)
    x += sine(hz('F5'), .20) * lfo(9, .0, 1.0, phase=1.8)      # tritone to B
    x += sine(hz('C6'), .12) * lfo(17, .0, 1.0, phase=.6)
    x += noise_loop(41, 11000, hp=4200) * 0.34 * lfo(6, .0, 1.0, phase=.2)
    x += stack(hz('F2'), [.10, .03]) * lfo(3, .3, 1.0)         # just a trace of dread
    return x

def melody():
    """The pilgrim's theme. Sparse, unhurried, mostly silence — it should feel
       like something half-remembered rather than a tune being performed."""
    x = np.zeros(LOOP_N)
    # (beat, note, amp) — a real tune now, following the chords underneath it
    # rather than drifting over a single one. Still leaves room to breathe, but
    # something arrives at least every couple of beats.
    phrase = [
        # F                                   Dm
        (0,'F4',.85), (1.5,'A4',.62), (3,'C5',.70), (5,'A4',.55),
        (6.5,'G4',.60), (8,'F4',.75), (10,'C5',.58), (12,'A4',.66),
        (14,'G4',.55),
        (16,'D4',.80), (17.5,'F4',.60), (19,'A4',.72), (21,'C5',.58),
        (22.5,'A4',.55), (24,'F4',.70), (26,'E4',.60), (28,'D4',.74),
        (30,'A3',.55),
        # Bb                                  C
        (32,'F4',.78), (33.5,'D4',.58), (35,'Bb3',.70), (37,'D4',.60),
        (38.5,'F4',.64), (40,'A4',.72), (42,'F4',.58), (44,'D4',.66),
        (46,'Bb3',.60),
        (48,'C4',.80), (49.5,'E4',.60), (51,'G4',.72), (53,'A4',.62),
        (54.5,'G4',.55), (56,'E4',.68), (58,'D4',.58), (60,'C4',.76),
        (62,'F3',.66),
    ]
    for beat, note, amp in phrase:
        n = pluck(hz(note), 3.2, amp=amp, harmonics=(1.0, .30, .14, .06), bright=2.2)
        place(x, n, int(beat * BEAT_N))
    return x * 0.9

def hearth():
    """The ramen stall and the shops. Warm, close, no threat. Diegetic-feeling —
       this is the one place in the game that is on the pilgrim's side."""
    x = np.zeros(LOOP_N)
    arpeggio(x, ARP_WARM, amp=0.72, step=0.5, bright=3.4, dur=2.0)
    for i, chord in enumerate(PROG):
        pad_chord(x, WARM_VOICING[chord][:3], i*CHORD_BEATS, CHORD_BEATS,
                  amp=0.34, harmonics=(1.0,.18,.06))
    x += noise_loop(51, 1400, hp=300) * 0.040 * lfo(2, .6, 1.0)   # room tone
    return x

def boss_bed():
    """Boss floors. F7 — the Eb darkens it without leaving the key. This is the
       first time in the game the player hears a kick drum, and that is the point."""
    x  = stack(hz('F1'), [1.0, .40, .18, .09, .04], detune=.004) * lfo(2, .7, 1.0)
    x += stack(hz('C3'), [.35, .16, .07], detune=.003) * lfo(3, .5, .95)
    x += stack(hz('Eb4'), [.20, .08], detune=.002) * lfo(4, .3, .85, phase=1.4)
    x += stack(hz('F3'), [.28, .10], detune=.003) * lfo(5, .4, .9, phase=2.6)
    for b in range(int(BEATS)):
        if b % 4 in (0, 2):
            place(x, hit(700 + b, 0.55, 110, amp=0.85, curve=6.0), b * BEAT_N)
    x += noise_loop(61, 90) * 0.09 * lfo(2, .5, 1.0)
    return x

def boss_press():
    """Layers on when the boss drops below half. Faster, higher, less air."""
    x = np.zeros(LOOP_N)
    for b in range(int(BEATS) * 2):                            # eighth notes
        at = b * BEAT_N // 2
        place(x, hit(900 + b, 0.16, 5200, amp=0.30, hp=1800, curve=22.0), at)
    for b in range(int(BEATS)):
        if b % 2 == 1:
            place(x, hit(1300 + b, 0.34, 200, amp=0.55, curve=8.0), b * BEAT_N)
    x += stack(hz('F4'), [.16, .07], detune=.004) * lfo(8, .2, 1.0)
    x += stack(hz('Eb5'), [.10, .04], detune=.003) * lfo(12, .1, 1.0, phase=1.0)
    x += sine(hz('C5'), .09) * lfo(16, .0, 1.0, phase=2.2)
    return x

# ============================================================== ONE-SHOTS ==
def oneshot(sig, sr=SR, fade=0.02):
    n = len(sig)
    f = int(fade * sr)
    sig[:f]  *= np.linspace(0, 1, f)
    sig[-f:] *= np.linspace(1, 0, f)
    return sig

def sfx_shrine():
    """A bell. Bright, brief, unambiguous — you got something."""
    n = int(1.8 * SR); out = np.zeros(n)
    for note, amp, d in [('C5', .9, 1.7), ('E5', .7, 1.6), ('G5', .45, 1.4), ('C6', .35, 1.2)]:
        p = pluck(hz(note), d, amp=amp, harmonics=(1.0, .18, .07), bright=4.0)
        out[:len(p)] += p
    return oneshot(out)

def sfx_clear():
    """Floor cleared. Fmaj7 arpeggio rising — release, not triumph."""
    n = int(2.6 * SR); out = np.zeros(n)
    for i, note in enumerate(['F4', 'A4', 'C5', 'E5', 'F5']):
        p = pluck(hz(note), 2.2, amp=.85 - i * .07, harmonics=(1.0, .25, .10), bright=3.2)
        at = int(i * 0.11 * SR)
        out[at:at + len(p)] += p[:n - at]
    return oneshot(out)

def sfx_death():
    """Descending, low, no resolution. The city does not mark your passing."""
    n = int(3.4 * SR); t = np.arange(n) / SR
    glide = hz('F2') * 2 ** (-t * 0.32)                    # slides down a fifth-ish
    ph = 2 * np.pi * np.cumsum(glide) / SR
    out = np.sin(ph) * np.exp(-t * 0.75)
    out += 0.35 * np.sin(2 * ph) * np.exp(-t * 1.3)
    out += 0.12 * np.sin(0.5 * ph) * np.exp(-t * 0.5)
    rng = np.random.default_rng(77)
    out += 0.06 * rng.standard_normal(n) * np.exp(-t * 2.5)
    return oneshot(out)

# ------------------------------------------------- character voices --------
"""One sound per character, each built from the thing that character DOES —
   the mechanic the player has to learn is the mechanic they hear.

   All of them are pitched inside F, so a hit lands in tune with whatever the
   score is playing underneath rather than fighting it. They are short: these
   fire constantly, and anything with a tail becomes noise within two turns."""

def glide(f0, f1, dur, curve=1.0):
    """A pitch sweep — the backbone of most of these."""
    n = int(dur * SR); t = np.arange(n) / SR
    f = f0 * (f1/f0) ** ((t/dur) ** curve)
    return np.sin(2*np.pi*np.cumsum(f)/SR), t, n

def sfx_goon():
    """Heavy, dumb, close. A boot landing and a short grunt of effort."""
    out = hit(2001, 0.26, 220, amp=0.9, curve=16.0)                  # footfall
    n = len(out); t = np.arange(n)/SR
    body = np.sin(2*np.pi*snap(hz('F2'))*t) * np.exp(-t*14)
    return oneshot(out*0.7 + body*0.5)

def sfx_sniper():
    """A rifle report is wrong for this game — what the sniper does is REACH.
       A tight high crack, then the shot travelling away from you."""
    crack = hit(2002, 0.09, 9000, amp=1.0, hp=2500, curve=48.0)
    w, t, n = glide(hz('C6'), hz('C5'), 0.34, curve=0.55)
    tail = w * np.exp(-t*9) * 0.42
    out = np.zeros(max(len(crack), n))
    out[:len(crack)] += crack
    out[:n] += tail
    return oneshot(out)

def sfx_mortar():
    """Falling, not firing — the mortar's whole lesson is that it lands where
       you WERE, so the sound is the descent and the thump at the end of it."""
    w, t, n = glide(hz('A4'), hz('A2'), 0.55, curve=1.7)
    fall = w * np.exp(-t*2.2) * 0.5
    out = np.zeros(int(0.9*SR)); out[:n] += fall
    boom = hit(2003, 0.42, 130, amp=1.0, curve=8.0)
    at = int(0.42*SR); out[at:at+len(boom)] += boom[:len(out)-at]
    return oneshot(out)

def sfx_warden():
    """Heavy plate. Blades glance off it, so it should sound like a struck bell
       that refuses to break — metallic, and unmoved."""
    n = int(1.1*SR); t = np.arange(n)/SR; out = np.zeros(n)
    # inharmonic partials are what make metal sound like metal, not like a note
    for mult, amp in [(1,.9),(2.76,.5),(5.4,.28),(8.9,.14),(13.3,.07)]:
        out += amp*np.sin(2*np.pi*snap(hz('F2'))*mult*t)*np.exp(-t*(2.5+mult*0.5))
    strike = hit(2004, 0.18, 3000, amp=0.35, hp=800, curve=26.0)
    out[:len(strike)] += strike            # shorter than the ring; add, don't slice
    return oneshot(out)

def sfx_agent():
    """Agent 180 rewrites the floor under you. Digital, wrong, deliberately
       machine-like — the one voice in the game that isn't organic."""
    n = int(0.5*SR); t = np.arange(n)/SR
    steps = np.floor(t*28)/28                       # quantised = mechanical
    f = snap(hz('C4')) * (2 ** (np.sin(steps*7.0)*0.55))
    out = np.sign(np.sin(2*np.pi*np.cumsum(f)/SR)) * 0.34      # square wave
    out *= np.exp(-t*5.5) * (1 - 0.4*np.sin(t*220))
    return oneshot(out)

def sfx_lance():
    """The final boss marks the floor and then takes it. The biggest sound in
       the game: sub weight first, metal on top, and a long ring."""
    n = int(1.6*SR); t = np.arange(n)/SR
    out = np.sin(2*np.pi*snap(hz('F1'))*t)*np.exp(-t*2.0)*1.0
    out += np.sin(2*np.pi*snap(hz('C2'))*t)*np.exp(-t*2.6)*0.5
    for mult, amp in [(6.1,.20),(9.7,.12),(14.2,.06)]:
        out += amp*np.sin(2*np.pi*snap(hz('F2'))*mult*t)*np.exp(-t*3.2)
    imp = hit(2005, 0.30, 180, amp=0.8, curve=9.0)
    out[:len(imp)] += imp
    return oneshot(out)

def sfx_step():
    """The pilgrim. Soft, small, and quiet enough to hear a hundred times."""
    return oneshot(hit(2006, 0.13, 900, amp=0.5, hp=180, curve=34.0))

def sfx_strike():
    """A blade. Air first, then the contact."""
    sw = hit(2007, 0.16, 6500, amp=0.55, hp=1400, curve=26.0)
    n = len(sw); t = np.arange(n)/SR
    edge = np.sin(2*np.pi*snap(hz('C5'))*t)*np.exp(-t*26)*0.30
    return oneshot(sw + edge)

def sfx_hurt():
    """The pilgrim taking a hit. Dull and internal — felt, not heard."""
    n = int(0.34*SR); t = np.arange(n)/SR
    out = np.sin(2*np.pi*snap(hz('F2'))*t)*np.exp(-t*11)*0.8
    out += np.sin(2*np.pi*snap(hz('B2'))*t)*np.exp(-t*15)*0.35   # the tritone
    thud = hit(2008, 0.16, 700, amp=0.4, curve=22.0)
    out[:len(thud)] += thud
    return oneshot(out)

def sfx_win():
    """The world finally warms. Slow attack, full Fmaj7 add9, no percussion."""
    n = int(5.0 * SR); t = np.arange(n) / SR
    out = np.zeros(n)
    for note, amp in [('F2', .8), ('C3', .5), ('A3', .55), ('E4', .40),
                      ('G4', .28), ('C5', .30), ('F5', .22)]:
        out += amp * np.sin(2 * np.pi * hz(note) * t)
    env = np.minimum(1.0, t / 1.6) * np.exp(-np.maximum(0, t - 2.2) * 0.8)
    return oneshot(out * env)

# =================================================================== MAIN ==
if __name__ == '__main__':
    # Gain staging, not uniform normalisation. Each stem is bounced at the level
    # it should sit at IN THE MIX, so the engine can play any combination at
    # unity without a limiter and without ducking. Beds are the foundation;
    # everything else is a layer on top and is quieter by design.
    loops = [
        ('bed_cold.wav',   bed_cold,   0.50),   ('bed_warm.wav',   bed_warm,   0.50),
        ('pulse.wav',      pulse,      0.26),   ('tension.wav',    tension,    0.20),
        ('melody.wav',     melody,     0.26),   ('hearth.wav',     hearth,     0.46),
        ('boss_bed.wav',   boss_bed,   0.50),   ('boss_press.wav', boss_press, 0.24),
    ]
    print(f'{LOOP_DUR:.3f}s  {LOOP_N} samples  {BPM:g} BPM  {BARS} bars  F major\n')
    for name, fn, pk in loops:
        p = write(name, fn(), peak=pk)
        print(f'  {name:16s} peak {pk:.2f}  {os.path.getsize(p)/1e6:5.1f} MB')
    # One-shots stay a touch under the loops so a hit reads as an event on top
    # of the music rather than punching a hole through it.
    shots = [('shrine',sfx_shrine,.72), ('clear',sfx_clear,.72),
             ('death',sfx_death,.72),   ('win',sfx_win,.75),
             ('goon',sfx_goon,.62),     ('sniper',sfx_sniper,.55),
             ('mortar',sfx_mortar,.68), ('warden',sfx_warden,.62),
             ('agent',sfx_agent,.52),   ('lance',sfx_lance,.75),
             ('step',sfx_step,.34),     ('strike',sfx_strike,.55),
             ('hurt',sfx_hurt,.62)]
    for name, fn, pk in shots:
        p = write('sfx/'+name+'.wav', fn(), peak=pk)
        print(f'  sfx/{name+".wav":13s} peak {pk:.2f}  {os.path.getsize(p)/1e3:5.0f} KB')
