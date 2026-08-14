"""
Arrange the hand-made Logic loops into the eight stems the game asks for.

The loops are a BAND — drums, pads, toppers — all 16 bars at 163 BPM (23.558 s),
which is exactly the engine's loop length. The engine does not want a band
though; it wants eight layers it can fade independently against game state. So
each stem here is a weighted sum of the source loops, chosen so that the score
ASSEMBLES ITSELF as the player gets deeper into trouble:

    exploring        pad
    the city acts    + kick
    hurt / cornered  + tambourine, trance topper
    a boss           + snare, perc slam, the whole kit

That keeps the rule the score has followed from the start — percussion means
threat — while using the real material rather than anything synthesised.

Source levels are wildly different (kick is ~11 dB hotter than the pads), so
every source gets a gain here, and every finished stem is normalised to a
LOUDNESS target rather than a peak — played material is far more transient than
synthesised pads, and peak-matching left it about 9 dB quieter in the ear.
"""
import numpy as np, wave, os, sys

SR  = 44100
SRC = "/Users/divyeshk/Downloads/chillcsassn4/newBeats/videogamemusic"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stems')
os.makedirs(OUT, exist_ok=True)

FILES = {
    'pad':    'Dystopian Pad.wav',
    'dtop':   'Dystopian topper.wav',
    'trance': 'Trance Topper.wav',
    'vocal':  'Vocal Topper.wav',
    'kick':   'kick.wav',
    'snare':  'snare.wav',
    'slam':   'perc slam.wav',
    'tamb':   'tambourine.wav',
}

# Per-source gain, evening out the bounce levels before anything is combined.
# kick and vocal came in hot; slam and tambourine came in quiet.
GAIN = {'pad':1.00, 'dtop':0.85, 'trance':0.70, 'vocal':0.55,
        'kick':0.34, 'snare':0.50, 'slam':0.95, 'tamb':0.75}

# stem -> {source: relative amount}, target LOUDNESS in dB RMS, and a peak cap.
#
# Matched on RMS, not on peak. Played material is far more transient than
# synthesised pads — normalising these to the same PEAK as the generated set
# left them 8-10 dB quieter in the ear, which would have buried the score under
# the sound effects. The targets are what the generated set actually measured,
# so the game sounds as loud as the version already tuned against playtest.
# The cap is a safety net: if hitting the loudness target would push a stem's
# peak past it, the cap wins and the stem simply plays a little quieter.
STEMS = {
    'bed_cold':   ({'pad':1.0, 'dtop':0.35},                         -20.0, 0.42),
    'bed_warm':   ({'pad':1.0, 'dtop':0.75, 'vocal':0.60},           -22.0, 0.42),
    'pulse':      ({'kick':1.0},                                     -27.0, 0.40),
    'tension':    ({'tamb':1.0, 'trance':0.65},                      -27.0, 0.30),
    'melody':     ({'vocal':1.0, 'dtop':0.40},                       -27.0, 0.30),
    'hearth':     ({'pad':0.85, 'dtop':1.0, 'vocal':0.35},           -24.0, 0.40),
    'boss_bed':   ({'pad':0.9, 'kick':1.0, 'snare':0.8, 'slam':0.7}, -23.0, 0.46),
    'boss_press': ({'tamb':0.8, 'trance':1.0, 'snare':0.7,
                    'slam':0.6},                                     -31.0, 0.30),
}

def read(name):
    """Read a WAV at any bit depth via its raw frames. Logic bounces 24-bit."""
    path = os.path.join(SRC, name)
    with wave.open(path, 'rb') as w:
        n, ch, sw = w.getnframes(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(n)
    if sw == 2:
        a = np.frombuffer(raw, dtype='<i2').astype(np.float64) / 32768.0
    elif sw == 3:                       # 24-bit: three bytes, little-endian signed
        b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
        v = (b[:,0] | (b[:,1] << 8) | (b[:,2] << 16))
        v = np.where(v & 0x800000, v - 0x1000000, v)
        a = v.astype(np.float64) / 8388608.0
    elif sw == 4:
        a = np.frombuffer(raw, dtype='<i4').astype(np.float64) / 2147483648.0
    else:
        raise SystemExit(f'{name}: unsupported sample width {sw}')
    return a.reshape(-1, ch)[:, :2] if ch >= 2 else np.stack([a, a], axis=1)

def write(name, sig, target_db, cap):
    """Normalise to a loudness, not to a peak — then hold the peak under `cap`
       so no combination the game can play is able to clip."""
    rms = np.sqrt((sig.mean(axis=1) ** 2).mean())
    if rms > 0:
        sig = sig * (10 ** (target_db / 20.0) / rms)
    pk = np.max(np.abs(sig))
    if pk > cap: sig = sig * (cap / pk)
    path = os.path.join(OUT, name + '.wav')
    with wave.open(path, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((sig * 32767).astype('<i2').tobytes())
    return path

def read_back(stem):
    with wave.open(os.path.join(OUT, stem + '.wav'), 'rb') as w:
        a = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2')
    x = a.reshape(-1, 2).astype(np.float64) / 32768.0
    return 20*np.log10(np.sqrt((x.mean(axis=1)**2).mean()) + 1e-12), np.max(np.abs(x))

if __name__ == '__main__':
    src = {}
    for key, fn in FILES.items():
        src[key] = read(fn)
        print(f'  read {fn:24s} {len(src[key])/SR:7.3f}s')
    lens = {len(v) for v in src.values()}
    if len(lens) != 1:
        sys.exit(f'FATAL: sources differ in length {lens} — they will drift apart')
    n = lens.pop()
    print(f'\nall sources {n} samples = {n/SR:.3f}s  (16 bars at 163 BPM)\n')

    for stem, (recipe, target_db, cap) in STEMS.items():
        mix = np.zeros((n, 2))
        for key, amt in recipe.items():
            mix += src[key] * GAIN[key] * amt
        write(stem, mix, target_db, cap)
        got = read_back(stem)
        parts = ' + '.join(f'{k}*{a:g}' for k, a in recipe.items())
        print(f'  {stem:11s} {got[0]:6.1f} dB  peak {got[1]:.3f}'
              f'{"  (peak-capped)" if got[1] >= cap - 1e-3 else ""}   {parts}')

