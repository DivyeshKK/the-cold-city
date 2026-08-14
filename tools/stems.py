"""
THE COLD CITY — adaptive score stems.

Every stem is the SAME 16-bar phrase at 163 BPM (23.6 s), transcribed from the
Logic session, so any stem layers under any other. Intensity comes from density
and register, never from tempo.

The music is in D minor — the relative minor of F, which is what the one-shots
are pitched to, so voices and score share a scale.

The warmth arc is register and density, not different harmony:
    cold  = the ostinato over one bass octave, thin and high.
    warm  = the octave below arrives, thirds fill in, a pad underneath.

SEAMLESS LOOPING: a sustained tone only loops cleanly if it completes a whole
number of cycles in the loop. Every frequency is snapped to the nearest such
value (resolution 1/53.333 = 0.019 Hz, far below audibility). Decaying sounds
are rendered past the loop end and the tail is folded back onto the start.
"""
import numpy as np, wave, struct, os

SR       = 44100
BPM      = 163.0
# 16 bars is the length of the written phrase (Logic bars 65-80), so the loop
# IS the composition rather than a slice of it. 23.6 s at this tempo.
BARS     = 16
BEATS    = BARS * 4
LOOP_N   = int(round(BEATS * 60.0 / BPM * SR))
# The musical length and the FILE length are not the same number unless the
# tempo happens to divide evenly into the sample rate — 72 BPM did, 163 does
# not. Everything that has to line up with the loop point (snap, the LFOs) must
# use the length the file actually IS, or the phase drifts by a fraction of a
# sample per loop and the seam slowly opens up.
LOOP_DUR = LOOP_N / SR                 # 47.117 s at 163 BPM / 32 bars
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
"""The written phrase, transcribed from Logic (bars 65-80 at 163 BPM).

   Bass moves every two bars:   F   G   A   A   F   G   D   D
   with one ostinato figure repeating over all of it:

       |A3 . . E3 . F3 . .|. F3 . . E3 . . .|

   Every second unit is a variant that strikes A3 twice at the top of the bar
   instead of holding it once.

   Roots of i-III-iv-V under a constant A/E/F cell puts this in D MINOR — the
   relative minor of F, so it shares every note with the one-shots, which were
   already pitched in F. Nothing had to be re-tuned to fit it.

   COLD and WARM are the SAME MUSIC now, not different harmony: cold plays the
   ostinato over a single bass octave, thin and high; warm adds the octave
   below, the thirds and fifths, and a pad underneath. Register and density
   carry the warmth arc, which is what stopped the early game sounding eerie.

   Added notes avoid Bb entirely — against the ostinato's E natural it makes a
   tritone, and that is the interval that made the first version creepy."""

UNITS = [('F',False), ('G',True), ('A',False), ('A',True),
         ('F',False), ('G',True), ('D',False), ('D',True)]
UNIT_BEATS = 8                                   # two bars per root
CYCLE_BEATS = len(UNITS) * UNIT_BEATS            # the whole 16-bar phrase

# (beat within the unit, note, length in beats)
OSTINATO     = [(0,'A3',.85), (1.5,'E3',.85), (3,'F3',.85),
                (5,'F3',.85), (6.5,'E3',.85)]
OSTINATO_VAR = [(0,'A3',.5), (1,'A3',.5), (1.5,'E3',.85), (3,'F3',.85),
                (5,'F3',.85), (6.5,'E3',.85)]

BASS_MID = {'F':'F2', 'G':'G2', 'A':'A2', 'D':'D2'}
BASS_LOW = {'F':'F1', 'G':'G1', 'A':'A1', 'D':'D1'}
WARM_ADD = {'F':['A2','C3'], 'G':['D3','G3'], 'A':['E3','C3'], 'D':['A2','F3']}

def ostinato(buf, amp=0.5, bright=2.8, ring=0.45, octave=1):
    """The figure itself. `octave` lifts it for stems that must sit above the
       beds without competing with them."""
    for u,(root,var) in enumerate(UNITS):
        base = u * UNIT_BEATS
        for beat, note, ln in (OSTINATO_VAR if var else OSTINATO):
            dur = ln * 60.0 / BPM + ring
            a = amp * (1.0 if beat == 0 else 0.72)     # lean on the downbeat
            place(buf, pluck(hz(note)*octave, dur, amp=a,
                             harmonics=(1.0,.20,.08,.03), bright=bright),
                  int((base + beat) * BEAT_N))

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
    """Floors 0-8. The ostinato over one bass octave. Thin and high, with no
       weight underneath — lonely rather than haunted."""
    x = np.zeros(LOOP_N)
    for u,(root,_) in enumerate(UNITS):
        pad_chord(x, [BASS_MID[root]], u*UNIT_BEATS, UNIT_BEATS,
                  amp=0.85, harmonics=(1.0,.20,.06))
    ostinato(x, amp=0.42, bright=2.6, ring=0.35)
    x += noise_loop(11, 2600, hp=700) * 0.012 * lfo(2, .8, 1.0)
    return x

def bed_warm():
    """Floors 9-18. Same phrase, same rhythm, so it crossfades with the cold
       bed — but the octave below arrives, the thirds fill in, and a pad sits
       under it. Fuller, closer, kinder."""
    x = np.zeros(LOOP_N)
    for u,(root,_) in enumerate(UNITS):
        notes = [BASS_LOW[root], BASS_MID[root]] + WARM_ADD[root]
        pad_chord(x, notes, u*UNIT_BEATS, UNIT_BEATS,
                  amp=1.0, harmonics=(1.0,.24,.09,.03))
    ostinato(x, amp=0.44, bright=3.2, ring=0.6)
    x += noise_loop(21, 1800, hp=400) * 0.011 * lfo(2, .8, 1.0)
    return x

def pulse():
    """Enemy phase. A low heartbeat under whatever bed is playing — the city
       acting. Sits deliberately low so it adds weight, not melody."""
    x = np.zeros(LOOP_N)
    for b in range(int(BEATS)):
        at = b * BEAT_N
        body = hit(100 + b, 0.42, 150, amp=0.95, curve=7.0)
        tone = pluck(hz('D1'), 0.42, amp=0.55, harmonics=(1.0, .30, .10), bright=1.4)
        place(x, body[:len(tone)] * 0.7 + tone * 0.8, at)
        if b % 4 in (1, 3):                                   # soft breath off-beat
            place(x, hit(500 + b, 0.30, 2600, amp=0.16, hp=700, curve=9.0),
                  at + BEAT_N // 2)
    x += noise_loop(31, 120) * 0.05 * lfo(4, .4, 1.0)
    return x

def tension():
    """Low HP, or a foe adjacent.

       The written figure, an octave up and struck on every eighth instead of
       its own rhythm. Urgency out of DENSITY, using notes that are already in
       the piece — the earlier version got this from a semitone beat and a
       tritone, which is a horror cue, not tension."""
    x = np.zeros(LOOP_N)
    per = int(0.5 * BEAT_N)
    for b in range(int(BEATS) * 2):
        beat = b * 0.5
        u = int(beat // UNIT_BEATS) % len(UNITS)
        within = beat - (beat // UNIT_BEATS) * UNIT_BEATS
        cell = ['A3','E3','F3','E3'][b % 4]
        a = 0.5 if b % 4 == 0 else 0.26
        place(x, pluck(hz(cell)*2, 0.42, amp=a,
                       harmonics=(1.0,.14,.05), bright=3.0), b*per)
    return x

def melody():
    """The pilgrim's theme: the written figure lifted an octave and given room,
       so it reads as a line being sung over the phrase rather than a second
       copy of it."""
    x = np.zeros(LOOP_N)
    for u,(root,var) in enumerate(UNITS):
        base = u * UNIT_BEATS
        for beat, note, ln in OSTINATO:
            if var and beat in (5,):          # thin it out so it breathes
                continue
            place(x, pluck(hz(note)*2, ln*60.0/BPM + 0.9, amp=.62 if beat==0 else .44,
                           harmonics=(1.0,.30,.12,.05), bright=2.6),
                  int((base+beat)*BEAT_N))
    return x * 0.9

def hearth():
    """The ramen stall and the shops. The same phrase played close and gently —
       the one place in the game that is on the pilgrim's side."""
    x = np.zeros(LOOP_N)
    ostinato(x, amp=0.8, bright=3.6, ring=1.1)
    for u,(root,_) in enumerate(UNITS):
        pad_chord(x, [BASS_MID[root]] + WARM_ADD[root], u*UNIT_BEATS, UNIT_BEATS,
                  amp=0.30, harmonics=(1.0,.18,.06))
    x += noise_loop(51, 1400, hp=300) * 0.040 * lfo(2, .6, 1.0)
    return x

def boss_bed():
    """Boss floors. D minor, low and heavy — the first time in the game the
       player hears a kick drum, and that is the point. Rooted on D like the
       rest of the score; the earlier Eb sat a semitone above the tonic, which
       is the exact interval we took out everywhere else."""
    x  = stack(hz('D1'), [1.0, .40, .18, .09, .04], detune=.004) * lfo(2, .7, 1.0)
    x += stack(hz('A2'), [.35, .16, .07], detune=.003) * lfo(3, .5, .95)
    x += stack(hz('F3'), [.26, .10], detune=.003) * lfo(5, .4, .9, phase=2.6)
    x += stack(hz('D3'), [.20, .08], detune=.002) * lfo(4, .3, .85, phase=1.4)
    for b in range(int(BEATS)):
        if b % 4 in (0, 2):
            place(x, hit(700 + b, 0.55, 110, amp=0.85, curve=6.0), b * BEAT_N)
    x += noise_loop(61, 90) * 0.09 * lfo(2, .5, 1.0)
    return x

def boss_press():
    """Layers on when the boss drops below half. Faster, higher, less air."""
    x = np.zeros(LOOP_N)
    for b in range(int(BEATS)):                                # quarters at 163
        at = b * BEAT_N
        place(x, hit(900 + b, 0.16, 5200, amp=0.30, hp=1800, curve=22.0), at)
    for b in range(int(BEATS)):
        if b % 2 == 1:
            place(x, hit(1300 + b, 0.34, 200, amp=0.55, curve=8.0), b * BEAT_N)
    x += stack(hz('D4'), [.16, .07], detune=.004) * lfo(8, .2, 1.0)
    x += stack(hz('A4'), [.10, .04], detune=.003) * lfo(12, .1, 1.0, phase=1.0)
    x += sine(hz('F5'), .09) * lfo(16, .0, 1.0, phase=2.2)
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
    # Levels dropped roughly 6 dB across the board after playtest: the score
    # plays continuously under everything, and what reads as "present" when you
    # audition a stem on its own reads as "loud" an hour into a session. The
    # relative balance is unchanged — every stem moved together.
    loops = [
        ('bed_cold.wav',   bed_cold,   0.26),   ('bed_warm.wav',   bed_warm,   0.26),
        ('pulse.wav',      pulse,      0.15),   ('tension.wav',    tension,    0.13),
        ('melody.wav',     melody,     0.15),   ('hearth.wav',     hearth,     0.24),
        ('boss_bed.wav',   boss_bed,   0.28),   ('boss_press.wav', boss_press, 0.14),
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
