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
    """Floors 0-8. Root, fifth, octave, Lydian #11. No third — nothing to hold on to."""
    x  = stack(hz('F2'), [1.0, .30, .12, .05]) * lfo(3, .55, 1.0)
    x += stack(hz('C3'), [.45, .14, .05]) * lfo(2, .35, .85, phase=1.1)
    x += stack(hz('F3'), [.26, .08]) * lfo(5, .30, .70, phase=2.3)
    x += sine(hz('B4'), .045) * lfo(8, .0, 1.0, phase=.7)      # the #11 glint
    x += sine(hz('E5'), .035) * lfo(11, .0, 1.0, phase=2.0)    # maj7 air
    x += sine(hz('C5'), .028) * lfo(7, .0, 1.0, phase=3.4)
    x += noise_loop(11, 3800, hp=900) * 0.030 * lfo(2, .5, 1.0)   # tape hiss
    x += noise_loop(12, 260) * 0.055 * lfo(3, .4, 1.0, phase=1.7)  # room rumble
    return x

def bed_warm():
    """Floors 9-18. Same root so it crossfades with the cold bed — but the
       third and the ninth arrive, and the world stops being indifferent."""
    x  = stack(hz('F2'), [1.0, .28, .10, .04]) * lfo(3, .60, 1.0)
    x += stack(hz('C3'), [.40, .13]) * lfo(2, .45, .90, phase=1.1)
    x += stack(hz('A3'), [.42, .16, .06]) * lfo(4, .35, .95, phase=.4)   # THE THIRD
    x += stack(hz('E4'), [.24, .08]) * lfo(3, .30, .85, phase=2.2)       # maj7
    x += stack(hz('D4'), [.18, .06]) * lfo(5, .20, .75, phase=3.1)       # sixth
    x += stack(hz('G4'), [.13, .04]) * lfo(6, .15, .65, phase=1.5)       # ninth
    x += sine(hz('C5'), .05) * lfo(9, .1, 1.0, phase=.9)
    x += sine(hz('A4'), .06) * lfo(7, .1, 1.0, phase=2.6)
    x += noise_loop(21, 2400, hp=500) * 0.026 * lfo(2, .6, 1.0)
    x += noise_loop(22, 200) * 0.048 * lfo(3, .5, 1.0, phase=2.0)
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
    # (beat, note, amp) — F major, leaning on the sixth and the maj7
    phrase = [
        (0,  'F4', .85), (2,  'A4', .70), (3,  'C5', .62),
        (6,  'A4', .55), (8,  'G4', .78), (10, 'F4', .60),
        (14, 'D4', .72), (16, 'F4', .55), (19, 'E5', .68),
        (22, 'C5', .58), (24, 'A4', .62), (28, 'F4', .80),
        (32, 'C5', .55), (35, 'D5', .60), (38, 'A4', .50),
        (42, 'F4', .70), (46, 'E4', .55), (48, 'G4', .62),
        (52, 'F4', .58), (56, 'C4', .70), (60, 'F3', .65),
    ]
    for beat, note, amp in phrase:
        n = pluck(hz(note), 3.2, amp=amp, harmonics=(1.0, .30, .14, .06), bright=2.2)
        place(x, n, int(beat * BEAT_N))
    return x * 0.9

def hearth():
    """The ramen stall and the shops. Warm, close, no threat. Diegetic-feeling —
       this is the one place in the game that is on the pilgrim's side."""
    x = np.zeros(LOOP_N)
    arp = ['F3', 'A3', 'C4', 'E4', 'C4', 'A3']
    for b in range(int(BEATS)):
        note = arp[b % len(arp)]
        n = pluck(hz(note), 2.4, amp=.55 if b % 2 else .70,
                  harmonics=(1.0, .22, .09, .03), bright=2.8)
        place(x, n, int(b * BEAT_N))
    x += stack(hz('F2'), [.40, .10]) * lfo(2, .6, 1.0)
    x += stack(hz('A3'), [.14, .05]) * lfo(3, .4, .9, phase=1.2)
    x += noise_loop(51, 1400, hp=300) * 0.045 * lfo(2, .6, 1.0)   # room tone
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
    for name, fn in [('sfx/shrine.wav', sfx_shrine), ('sfx/clear.wav', sfx_clear),
                     ('sfx/death.wav', sfx_death),   ('sfx/win.wav', sfx_win)]:
        p = write(name, fn(), peak=0.72)
        print(f'  {name:16s} {os.path.getsize(p)/1e6:5.1f} MB')
