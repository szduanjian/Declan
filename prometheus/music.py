"""Procedural orchestral score for the 136 s mini-doc.

Each scene holds a whole number of beats in exactly 15 s, so every chapter cut
lands on a downbeat while the tempo steps up from 64 to 140 BPM.
"""
import numpy as np
from scipy.signal import butter, sosfilt, fftconvolve, sawtooth
from scipy.io import wavfile

SR = 44100
DUR = 136.0
N = int(SR * DUR)
rng = np.random.default_rng(7)

# (start, length, beats, chord per bar, intensity 0..1)
SCENES = [
    (0, 15, 16, ["Dm", "Bb", "Gm", "A"], 0.10),
    (15, 15, 20, ["Dm", "Bb", "F", "C", "A"], 0.22),
    (30, 15, 20, ["Dm", "Bb", "F", "C", "A"], 0.32),
    (45, 15, 24, ["Dm", "Bb", "F", "C", "Gm", "A"], 0.45),
    (60, 15, 24, ["Dm", "Bb", "F", "C", "Gm", "A"], 0.55),
    (75, 15, 28, ["Dm", "Bb", "F", "C", "Dm", "Gm", "A"], 0.68),
    (90, 15, 28, ["Dm", "Bb", "F", "C", "Dm", "Gm", "A"], 0.78),
    (105, 15, 32, ["Dm", "Bb", "F", "C", "Dm", "Bb", "Gm", "A"], 0.90),
    (120, 12, 28, ["Dm", "Bb", "F", "C", "Gm", "A", "A"], 1.00),
]
FINAL_T = 132.0

CHORDS = {  # bass midi, triad (root, third, fifth) pitch classes
    "Dm": (38, [2, 5, 9]), "Bb": (34, [10, 2, 5]), "F": (41, [5, 9, 0]),
    "C": (36, [0, 4, 7]), "Gm": (43, [7, 10, 2]), "A": (33, [9, 1, 4]),
    "D": (38, [2, 6, 9]),
}


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def voice(pcs, lo, hi):
    out = []
    for m in range(lo, hi + 1):
        if m % 12 in pcs:
            out.append(m)
    return out


def lp(x, fc, order=2):
    fc = min(fc, SR * 0.45)
    return sosfilt(butter(order, fc, "low", fs=SR, output="sos"), x)


def hp(x, fc, order=2):
    return sosfilt(butter(order, fc, "high", fs=SR, output="sos"), x)


def bp(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo, hi], "band", fs=SR, output="sos"), x)


def env_adsr(n, a, d, s, r):
    a, d, r = int(a * SR), int(d * SR), int(r * SR)
    e = np.full(n, s, dtype=np.float64)
    a = min(a, n)
    e[:a] = np.linspace(0, 1, a, endpoint=False) if a else e[:a]
    d = min(d, n - a)
    if d > 0:
        e[a:a + d] = np.linspace(1, s, d)
    r = min(r, n)
    if r > 0:
        e[n - r:] *= np.linspace(1, 0, r)
    return e


L = np.zeros(N)
R = np.zeros(N)


def add(sig, t, pan=0.0, gain=1.0):
    i = int(t * SR)
    if i >= N:
        return
    sig = sig[: N - i] * gain
    gl = np.cos((pan + 1) * np.pi / 4)
    gr = np.sin((pan + 1) * np.pi / 4)
    L[i:i + len(sig)] += sig * gl
    R[i:i + len(sig)] += sig * gr


def strings(m, dur, cutoff=2200, attack=0.35, release=0.8):
    n = int((dur + release) * SR)
    t = np.arange(n) / SR
    f = hz(m)
    vib = 1 + 0.004 * np.sin(2 * np.pi * 5.2 * t + rng.uniform(0, 6)) * np.clip(t / 0.8, 0, 1)
    s = np.zeros(n)
    for det in (-0.007, 0.0, 0.006):
        ph = np.cumsum(f * (1 + det) * vib) / SR
        s += sawtooth(2 * np.pi * (ph + rng.uniform()))
    s = lp(s / 3, cutoff)
    return s * env_adsr(n, attack, 0.2, 0.85, release)


def spiccato(m, cutoff=2600):
    n = int(0.22 * SR)
    t = np.arange(n) / SR
    s = sawtooth(2 * np.pi * hz(m) * t) + 0.6 * sawtooth(2 * np.pi * hz(m) * 1.004 * t)
    s = lp(s, cutoff)
    return s * np.exp(-t / 0.07) * np.clip(t / 0.006, 0, 1)


def brass(m, dur, bright=1.0):
    n = int((dur + 0.35) * SR)
    t = np.arange(n) / SR
    f = hz(m) * (1 - 0.012 * np.exp(-t / 0.05))
    ph = np.cumsum(f) / SR
    raw = sawtooth(2 * np.pi * ph) + 0.5 * sawtooth(2 * np.pi * ph * 1.003)
    dark = lp(raw, 700)
    lit = lp(raw, 1800 + 2600 * bright)
    fe = np.clip(t / 0.12, 0, 1) * (0.55 + 0.45 * np.exp(-t / 0.6))
    s = dark * (1 - fe) + lit * fe
    return s * env_adsr(n, 0.05, 0.3, 0.8, 0.35)


def timpani(m, dec=0.9):
    n = int(2.0 * SR)
    t = np.arange(n) / SR
    f = hz(m) * (1 + 0.25 * np.exp(-t / 0.03))
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.35 * np.sin(2 * np.pi * np.cumsum(f * 1.5) / SR)
    noise = bp(rng.standard_normal(n), 80, 900) * np.exp(-t / 0.05)
    return (s * np.exp(-t / dec) + 0.5 * noise) * np.clip(t / 0.002, 0, 1)


def boom():
    n = int(3.0 * SR)
    t = np.arange(n) / SR
    f = 55 * (1 + 1.2 * np.exp(-t / 0.04))
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 1.1)
    noise = lp(rng.standard_normal(n), 400) * np.exp(-t / 0.15)
    return s + 0.8 * noise


def crash(dec=2.2):
    n = int(4.0 * SR)
    t = np.arange(n) / SR
    s = hp(rng.standard_normal(n), 3500) * np.exp(-t / dec)
    return s * np.clip(t / 0.003, 0, 1)


def snare():
    n = int(0.3 * SR)
    t = np.arange(n) / SR
    s = bp(rng.standard_normal(n), 900, 6000) * np.exp(-t / 0.06)
    return s + 0.4 * np.sin(2 * np.pi * 190 * t) * np.exp(-t / 0.04)


def riser(dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = rng.standard_normal(n)
    out = np.zeros(n)
    seg = SR // 20
    for i in range(0, n, seg):
        k = i / n
        lo = 300 + 5000 * k ** 2
        out[i:i + seg] = bp(x[i:i + seg], lo, lo * 1.8)
    return out * (t / dur) ** 2.5


# ---------------------------------------------------------------- score
MOTIF = [(0, 2, 2), (2, 1, 1), (3, 1, 0)]  # (beat offset, length, chord-tone index)

for si, (t0, length, beats, prog, inten) in enumerate(SCENES):
    bl = length / beats
    bar = 4 * bl
    for bi, name in enumerate(prog):
        bt = t0 + bi * bar
        bass, pcs = CHORDS[name]
        last_bar = bi == len(prog) - 1
        # pad: low strings / violas / violins
        pad_notes = voice(pcs, 50, 64 if inten < 0.5 else 69)
        cut = 900 + 3200 * inten
        for k, m in enumerate(pad_notes):
            add(strings(m, bar, cut, attack=0.5 if inten < 0.4 else 0.15), bt,
                pan=-0.6 + 1.2 * k / max(1, len(pad_notes) - 1), gain=0.05 + 0.04 * inten)
        add(strings(bass, bar, 700 + 600 * inten), bt, gain=0.09 + 0.06 * inten)
        if inten > 0.3:
            add(strings(bass - 12, bar, 400), bt, gain=0.08 * inten)

        # string ostinato: quarters -> eighths -> sixteenths
        if inten >= 0.2:
            sub = 1 if inten < 0.3 else (2 if inten < 0.6 else 4)
            pat = [bass + 12, bass + 12, bass + 19, bass + 12, bass + 24, bass + 12, bass + 19, bass + 15]
            for k in range(4 * sub):
                m = pat[k % len(pat)] if sub > 1 else bass + 12
                acc = 1.0 if k % sub == 0 else 0.65
                add(spiccato(m, 1800 + 2500 * inten), bt + k * bl / sub,
                    pan=0.35 * np.sin(k), gain=(0.06 + 0.08 * inten) * acc)

        # heroic motif: horns first, then trumpets + violins
        if inten >= 0.3:
            tones = voice(pcs, 62, 76)
            for off, ln, idx in MOTIF:
                if last_bar and off > 0:
                    break
                m = tones[min(idx, len(tones) - 1)]
                ln_b = 4 if last_bar else ln
                add(brass(m - 12, ln_b * bl, bright=inten), bt + off * bl, pan=-0.25, gain=0.05 + 0.05 * inten)
                if inten >= 0.5:
                    add(brass(m, ln_b * bl, bright=inten), bt + off * bl, pan=0.25, gain=0.03 + 0.05 * inten)
                if inten >= 0.6:
                    add(strings(m + 12, ln_b * bl, 5000, attack=0.05), bt + off * bl, pan=0.1, gain=0.035 * inten)

        # percussion
        if inten >= 0.4:
            hits = [0] if inten < 0.6 else ([0, 2] if inten < 0.85 else [0, 1, 2, 3])
            for h in hits:
                add(timpani(bass + 12 if h % 2 == 0 else bass + 19), bt + h * bl, gain=0.22 * inten)
        if inten >= 0.65:
            for k in range(8):
                if k % 2 == 1:
                    add(snare(), bt + k * bl / 2, pan=0.2, gain=0.05 * inten)
        if last_bar and inten >= 0.2:
            # timpani roll crescendo into the next chapter
            nroll = int(8 + 16 * inten)
            for k in range(nroll):
                add(timpani(bass + 12, 0.25), bt + bar - bl * 2 + k * (2 * bl / nroll),
                    gain=0.03 + 0.18 * inten * (k / nroll) ** 1.5)

    # chapter downbeat
    add(boom(), t0, gain=0.35 + 0.35 * inten)
    if si >= 2:
        add(crash(), t0, pan=0.3, gain=0.05 + 0.08 * inten)

# gentle opening swell
add(strings(26, 15, 500, attack=5.0, release=1.0), 0, gain=0.12)
add(riser(3.5), FINAL_T - 3.5, gain=0.06)

# final cosmic chord: D major, full orchestra
fd = DUR - FINAL_T
add(boom(), FINAL_T, gain=0.9)
add(crash(3.0), FINAL_T, gain=0.18)
for m in voice([2, 6, 9], 38, 81):
    add(strings(m, fd - 0.8, 5200, attack=0.02, release=1.5), FINAL_T, pan=rng.uniform(-0.7, 0.7), gain=0.05)
for m in voice([2, 6, 9], 50, 74):
    add(brass(m, fd - 0.8, bright=1.0), FINAL_T, pan=rng.uniform(-0.5, 0.5), gain=0.06)
add(strings(26, fd, 400, attack=0.02), FINAL_T, gain=0.18)
for k in range(12):
    add(timpani(50, 0.3), FINAL_T - 1.0 + k / 12, gain=0.05 + 0.25 * k / 12)

# opening: drum hit and horn drone under the title so the film starts audibly
add(boom(), 0.05, gain=0.7)
add(crash(3.5), 0.05, gain=0.08)
for m in (38, 45, 50):
    add(brass(m, 7.0, bright=0.3), 0.05, pan=(m - 45) / 10, gain=0.07)
for m in (50, 57, 62):
    add(strings(m, 14.0, 1400, attack=1.5, release=1.0), 0.3, pan=(m - 57) / 8, gain=0.06)
for k in range(16):
    add(timpani(38, 0.3), 13.0 + k * 2.0 / 16, gain=0.05 + 0.3 * (k / 16) ** 1.5)


# ---------------------------------------------------------------- mix
def reverb(x, seed, rt=2.6):
    r = np.random.default_rng(seed)
    n = int(rt * SR)
    t = np.arange(n) / SR
    ir = r.standard_normal(n) * np.exp(-t * 6.9 / rt)
    ir = lp(ir, 5000)
    ir[: int(0.02 * SR)] = 0
    ir /= np.sqrt(np.sum(ir ** 2))
    return fftconvolve(x, ir)[: len(x)]


wetL, wetR = reverb(L, 1), reverb(R, 2)
outL = L + 0.45 * wetL
outR = R + 0.45 * wetR
st = np.stack([outL, outR], axis=1)
t = np.arange(N) / SR
# lift the quiet early chapters so the arc stays audible on laptop speakers
lift = np.interp(t, [0, 15, 30, 60, 90, 136], [2.2, 1.9, 1.6, 1.3, 1.0, 1.0])
st *= lift[:, None]
st /= np.max(np.abs(st)) + 1e-9
st = np.tanh(st * 1.6) / np.tanh(1.6)
fade = np.clip(t / 0.3, 0, 1) * np.clip((DUR - t) / 2.5, 0, 1) ** 1.5
st *= fade[:, None] * 0.95
wavfile.write("build/score.wav", SR, (st * 32767).astype(np.int16))
print("wrote build/score.wav")
