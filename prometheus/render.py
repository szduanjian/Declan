"""Frame renderer for 薪火 — schematic line-art mini-doc, 1920x1080 @ 30 fps."""
import math
import subprocess
import sys
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops

W, H = 1920, 1080
SS = 2
FPS = 30
DUR = 136.0
SCENE = 15.0

SERIF_B = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"
SERIF_R = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"
_fonts = {}


def font(size, bold=False):
    key = (size, bold)
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(SERIF_B if bold else SERIF_R, int(size * SS), index=2)
    return _fonts[key]


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def lerp(a, b, k):
    return a + (b - a) * k


def lerp_col(a, b, k):
    return tuple(int(lerp(a[i], b[i], k)) for i in range(3))


# ------------------------------------------------------------ palette
PARCH = (231, 218, 188)
NIGHT = (7, 9, 20)
INK_DAY = (58, 40, 24)
INK_NIGHT = (226, 206, 158)
RED_DAY = (168, 42, 28)
RED_NIGHT = (255, 146, 64)


def darkness(t):
    """Parchment ages through chapters 1-3, flips to night at the 60 s cut, deepens to full starfield."""
    if t < 15:
        return 0.0
    if t < 60:
        return 0.22 * (t - 15) / 45
    if t >= 120:
        return 1.0
    k = ease((t - 60) / 0.5)
    return lerp(0.22, lerp(0.7, 1.0, (t - 60) / 60), k)


def ink_mix(t):
    return ease((t - 60) / 0.5)


# ------------------------------------------------------------ backgrounds
def _make_backgrounds():
    r = np.random.default_rng(3)
    yy, xx = np.mgrid[0:H, 0:W]
    cx, cy = W / 2, H / 2
    rad = np.sqrt(((xx - cx) / W) ** 2 + ((yy - cy) / H) ** 2)
    vign = 1 - 0.55 * np.clip(rad - 0.15, 0, 1) ** 1.6

    noise = r.standard_normal((H // 4, W // 4))
    noise = np.array(Image.fromarray(((noise * 30) + 128).clip(0, 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)) / 255.0 - 0.5
    fine = r.standard_normal((H, W)) * 0.035
    blot = np.array(Image.fromarray((r.random((12, 20)) * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)) / 255.0 - 0.5
    base = np.array(PARCH, float)[None, None, :]
    tone = 1 + 0.10 * noise[..., None] + fine[..., None] + 0.08 * blot[..., None]
    parch = base * tone * vign[..., None]
    parch[..., 2] *= 0.97
    parch = Image.fromarray(parch.clip(0, 255).astype(np.uint8))

    sky = np.zeros((H, W, 3))
    neb = np.array(Image.fromarray((r.random((9, 16)) * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)) / 255.0
    neb2 = np.array(Image.fromarray((r.random((18, 32)) * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)) / 255.0
    sky += np.array(NIGHT, float)
    sky += (neb ** 3)[..., None] * np.array([40, 22, 60]) + (neb2 ** 4)[..., None] * np.array([10, 30, 55])
    sky *= (1 - 0.5 * np.clip(rad, 0, 1))[..., None]
    sky = Image.fromarray(sky.clip(0, 255).astype(np.uint8))
    return parch, sky


STARS = None


def _make_stars():
    r = np.random.default_rng(11)
    n = 900
    return np.stack([r.uniform(0, W, n), r.uniform(0, H, n), r.uniform(0.4, 2.2, n) ** 1.5,
                     r.uniform(0, 6.28, n), r.uniform(0.5, 3, n)], 1)


# ------------------------------------------------------------ vector toolkit
def circle(c, r, a0=0, a1=2 * math.pi, n=None):
    n = n or max(12, int(abs(a1 - a0) * r / 6))
    a = np.linspace(a0, a1, n)
    return np.stack([c[0] + r * np.cos(a), c[1] + r * np.sin(a)], 1)


def ellipse(c, rx, ry, rot=0.0, n=120):
    a = np.linspace(0, 2 * math.pi, n)
    x, y = rx * np.cos(a), ry * np.sin(a)
    cr, sr = math.cos(rot), math.sin(rot)
    return np.stack([c[0] + x * cr - y * sr, c[1] + x * sr + y * cr], 1)


def poly(*pts, close=False):
    p = list(pts)
    if close:
        p.append(p[0])
    return np.array(p, float)


def rect(x, y, w, h):
    return poly((x, y), (x + w, y), (x + w, y + h), (x, y + h), close=True)


def bezier(p0, p1, p2, p3, n=60):
    t = np.linspace(0, 1, n)[:, None]
    p0, p1, p2, p3 = map(np.array, (p0, p1, p2, p3))
    return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3


def partial(pts, frac):
    if frac >= 1:
        return pts, pts[-1]
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    cum = np.concatenate([[0], np.cumsum(seg)])
    tot = cum[-1]
    if tot == 0 or frac <= 0:
        return pts[:1], pts[0]
    target = frac * tot
    i = np.searchsorted(cum, target) - 1
    i = max(0, min(i, len(seg) - 1))
    k = (target - cum[i]) / (seg[i] + 1e-9)
    end = pts[i] + (pts[i + 1] - pts[i]) * k
    return np.vstack([pts[: i + 1], end]), end


def dashed(pts, frac, dash=14, gap=10):
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    cum = np.concatenate([[0], np.cumsum(seg)])
    lim = cum[-1] * frac
    out = []
    s = 0.0
    while s < lim:
        v = np.linspace(s, min(s + dash, lim), 3)
        out.append(np.stack([np.interp(v, cum, pts[:, 0]), np.interp(v, cum, pts[:, 1])], 1))
        s += dash + gap
    return out


class Diagram:
    """Strokes and labels in a local coordinate box, revealed over scene time."""

    def __init__(self):
        self.items = []

    def s(self, pts, t0, t1, w=2.2, col="ink", dash=False, pen=True):
        self.items.append(("s", pts, t0, t1, w, col, dash, pen))
        return self

    def dyn(self, fn, t0, w=2.2, col="ink"):
        self.items.append(("d", fn, t0, w, col))
        return self

    def txt(self, text, pos, t0, size=22, col="ink", anchor="mm", bold=False):
        self.items.append(("t", text, pos, t0, size, col, anchor, bold))
        return self

    def dot(self, pos, t0, r=5, col="ink", fill=True):
        self.items.append(("o", pos, t0, r, col, fill))
        return self


class Ctx:
    def __init__(self, img, pal, alpha=1.0):
        self.img = img
        self.d = ImageDraw.Draw(img)
        self.pal = pal
        self.alpha = alpha

    def col(self, name, a=1.0):
        c = self.pal[name]
        return (*c, int(255 * clamp(a * self.alpha)))

    def line(self, pts, w, col, a=1.0):
        if len(pts) < 2:
            return
        p = [(float(x) * SS, float(y) * SS) for x, y in pts]
        self.d.line(p, fill=self.col(col, a), width=max(1, int(w * SS)), joint="curve")

    def disc(self, c, r, col, a=1.0, fill=True, w=2):
        x, y = c[0] * SS, c[1] * SS
        rr = r * SS
        if fill:
            self.d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=self.col(col, a))
        else:
            self.d.ellipse([x - rr, y - rr, x + rr, y + rr], outline=self.col(col, a), width=int(w * SS))

    def text(self, s, pos, size, col, a=1.0, anchor="mm", bold=False, spacing=0):
        if a <= 0.01:
            return
        f = font(size, bold)
        if spacing:
            x, y = pos
            widths = [f.getlength(ch) / SS + spacing for ch in s]
            total = sum(widths) - spacing
            if anchor[0] == "m":
                x -= total / 2
            elif anchor[0] == "r":
                x -= total
            for ch, wd in zip(s, widths):
                self.d.text((x * SS, y * SS), ch, font=f, fill=self.col(col, a), anchor="l" + anchor[1])
                x += wd
            return
        self.d.text((pos[0] * SS, pos[1] * SS), s, font=f, fill=self.col(col, a), anchor=anchor)


def draw_diagram(ctx, dg, t, ox, oy, sc=1.0, speed=1.0, pens=None):
    def tr(p):
        p = np.asarray(p, float)
        return np.stack([ox + p[..., 0] * sc, oy + p[..., 1] * sc], -1) if p.ndim > 1 else (ox + p[0] * sc, oy + p[1] * sc)

    t = t * speed
    for it in dg.items:
        kind = it[0]
        if kind == "s":
            _, pts, t0, t1, w, col, dsh, pen = it
            fr = ease((t - t0) / max(1e-3, t1 - t0))
            if fr <= 0:
                continue
            P = tr(pts)
            if dsh:
                for seg in dashed(P, fr, 12 * sc + 2, 9 * sc + 2):
                    ctx.line(seg, w * max(sc, 0.5), col)
            else:
                part, end = partial(P, fr)
                ctx.line(part, w * max(sc, 0.5), col)
                if pen and fr < 1 and pens is not None:
                    pens.append(end)
        elif kind == "d":
            _, fn, t0, w, col = it
            if t < t0:
                continue
            a = ease((t - t0) / 0.8)
            for pts in fn(t):
                ctx.line(tr(pts), w * max(sc, 0.5), col, a)
        elif kind == "t":
            _, text, pos, t0, size, col, anchor, bold = it
            a = ease((t - t0) / 0.7)
            if a > 0 and size * sc >= 7:
                ctx.text(text, tr(pos), size * sc, col, a, anchor, bold)
        elif kind == "o":
            _, pos, t0, r, col, fill = it
            a = ease((t - t0) / 0.4)
            if a > 0:
                ctx.disc(tr(pos), r * max(sc, 0.4) * (0.6 + 0.4 * a), col, a, fill, w=1.6 * max(sc, 0.5))


# ------------------------------------------------------------ diagrams (local box ~1000 x 760)
def dg_confucius():
    d = Diagram()
    c = (500, 380)
    d.s(circle(c, 320), 1.0, 3.2, 2.4)
    d.s(circle(c, 300), 1.4, 3.6, 1.2)
    d.s(circle(c, 205), 2.0, 4.0, 1.6)
    for k in range(72):
        a = k * math.pi / 36
        l = 18 if k % 6 == 0 else 8
        d.s(poly((c[0] + 300 * math.cos(a), c[1] + 300 * math.sin(a)),
                 (c[0] + (300 - l) * math.cos(a), c[1] + (300 - l) * math.sin(a))), 2.8 + k * 0.02, 3.0 + k * 0.02, 1.2, pen=False)
    virtues = ["仁", "义", "礼", "智", "信"]
    V = [(c[0] + 205 * math.cos(-math.pi / 2 + k * 2 * math.pi / 5), c[1] + 205 * math.sin(-math.pi / 2 + k * 2 * math.pi / 5)) for k in range(5)]
    d.s(np.array(V + [V[0]]), 4.0, 6.0, 1.8, "red")
    for k, v in enumerate(V):
        d.dot(v, 4.2 + k * 0.3, 7, "red")
        d.s(poly(c, v), 4.6 + k * 0.2, 5.4 + k * 0.2, 0.8, pen=False)
        lp = (c[0] + 258 * math.cos(-math.pi / 2 + k * 2 * math.pi / 5), c[1] + 258 * math.sin(-math.pi / 2 + k * 2 * math.pi / 5))
        d.txt(virtues[k], lp, 5.0 + k * 0.35, 40, bold=True)
    d.s(circle(c, 150), 5.4, 6.2, 1.0, pen=False)
    for k in range(7):
        x = c[0] - 105 + k * 30
        d.s(rect(x, c[1] - 95, 22, 190), 5.5 + k * 0.15, 6.8 + k * 0.15, 1.6)
    for yy in (c[1] - 70, c[1] + 70):
        d.s(poly((c[0] - 118, yy), (c[0] + 105, yy)), 7.2, 8.0, 1.4, "red")
    for k, ch in enumerate("学而时习之"):
        d.txt(ch, (c[0] - 94 + (k + 1) * 30, c[1] - 30 + (k % 2) * 40), 7.8 + k * 0.15, 17, bold=True)
    d.s(poly((c[0] + 226, c[1] - 226), (c[0] + 290, c[1] - 320), (c[0] + 300, c[1] - 320)), 8.5, 9.3, 1.2, pen=False)
    d.txt("五常 · 仁义礼智信", (c[0] + 310, c[1] - 320), 9.0, 20, anchor="lm")
    d.s(poly((c[0] - 110, c[1] + 95), (c[0] - 330, c[1] + 220), (c[0] - 470, c[1] + 220)), 8.8, 9.6, 1.2, pen=False)
    d.txt("《论语》竹简", (c[0] - 470, c[1] + 248), 9.3, 20, anchor="lm")
    d.txt("图一 · 大道之环", (0, 745), 10.0, 20, anchor="lm")
    return d


def dg_qin():
    d = Diagram()
    ridge = [(0, 640), (80, 560), (150, 600), (240, 500), (330, 580), (420, 470), (520, 560), (600, 500), (700, 590), (790, 520), (880, 600), (1000, 540)]
    d.s(poly(*ridge), 1.0, 3.0, 2.0)
    d.s(poly((0, 700), (140, 650), (300, 690), (460, 640), (640, 690), (820, 650), (1000, 690)), 1.5, 3.5, 1.0)
    R = np.array(ridge, float)
    top = R + np.array([0, -38])
    d.s(top, 2.2, 5.0, 2.0)
    teeth = []
    for i in range(len(R) - 1):
        a, b = top[i], top[i + 1]
        n = int(np.linalg.norm(b - a) / 18)
        for k in range(n):
            p = a + (b - a) * (k + 0.2) / n
            q = a + (b - a) * (k + 0.7) / n
            teeth.append(poly(tuple(p), (p[0], p[1] - 12), (q[0], q[1] - 12), tuple(q)))
    for k, tpts in enumerate(teeth):
        d.s(tpts, 3.0 + k * 0.035, 3.3 + k * 0.035, 1.4, pen=False)
    for i in (3, 5, 7, 9):
        x, y = top[i]
        d.s(rect(x - 20, y - 60, 40, 60), 4.5 + i * 0.1, 5.4 + i * 0.1, 1.8)
        d.s(poly((x - 28, y - 60), (x, y - 82), (x + 28, y - 60)), 5.0 + i * 0.1, 5.6 + i * 0.1, 1.8)
    d.txt("万里长城", (60, 470), 6.0, 22, anchor="lm")
    cc = (500, 190)
    d.s(circle(cc, 70), 5.0, 6.2, 2.4, "red")
    d.txt("秦", cc, 6.3, 56, "red", bold=True)
    states = ["齐", "楚", "燕", "韩", "赵", "魏"]
    for k, nm in enumerate(states):
        p = (cc[0] - 430 + k * 172, cc[1] + 110 - (140 if k in (0, 5) else 0) - (60 if k in (1, 4) else 0) + 40)
        d.s(circle(p, 24), 5.4 + k * 0.2, 6.0 + k * 0.2, 1.6)
        d.txt(nm, p, 5.8 + k * 0.2, 24)
        v = np.array(cc, float) - np.array(p, float)
        v /= np.linalg.norm(v)
        d.s(poly(tuple(np.array(p) + v * 30), tuple(np.array(cc) - v * 78)), 6.4 + k * 0.15, 7.6 + k * 0.15, 1.4, "red")
    coin = (900, 80)
    d.s(circle(coin, 58), 7.5, 8.5, 2.0)
    d.s(circle(coin, 50), 7.7, 8.6, 1.0)
    d.s(rect(coin[0] - 16, coin[1] - 16, 32, 32), 8.3, 8.9, 1.8)
    d.txt("半", (coin[0] - 32, coin[1]), 8.8, 20)
    d.txt("两", (coin[0] + 32, coin[1]), 8.9, 20)
    d.txt("统一货币", (coin[0], coin[1] + 82), 9.1, 18)
    d.txt("书同文 · 车同轨", (100, 80), 8.6, 22, anchor="lm")
    d.s(poly((100, 106), (300, 106)), 8.8, 9.5, 1.2, "red", pen=False)
    d.txt("图二 · 六合归一", (0, 745), 10.0, 20, anchor="lm")
    return d


def dg_cailun():
    d = Diagram()
    xs = [60, 310, 560, 810]
    names = ["树皮麻头", "捣浆", "抄纸", "晾干成纸"]
    y = 190
    for i, x in enumerate(xs):
        t = 1.0 + i * 1.3
        d.s(rect(x - 90, y - 110, 180, 200), t, t + 1.0, 1.8)
        d.txt(f"{'一二三四'[i]}", (x - 72, y - 92), t + 0.3, 18, "red")
        d.txt(names[i], (x, y + 125), t + 0.6, 22)
        if i < 3:
            d.s(poly((x + 100, y), (xs[i + 1] - 100, y)), t + 0.9, t + 1.3, 1.8, "red")
            d.s(poly((xs[i + 1] - 112, y - 8), (xs[i + 1] - 100, y), (xs[i + 1] - 112, y + 8)), t + 1.2, t + 1.4, 1.8, "red", pen=False)
    x = xs[0]
    d.s(poly((x - 25, y + 70), (x - 18, y - 70)), 1.5, 2.2, 2.0)
    d.s(poly((x + 25, y + 70), (x + 18, y - 70)), 1.5, 2.2, 2.0)
    for k in range(5):
        d.s(poly((x - 20, y - 50 + k * 25), (x + 20, y - 40 + k * 25)), 2.0 + k * 0.1, 2.3 + k * 0.1, 1.0, pen=False)
    x = xs[1]
    d.s(bezier((x - 55, y - 10), (x - 55, y + 70), (x + 55, y + 70), (x + 55, y - 10)), 2.8, 3.5, 2.0)
    d.s(poly((x - 55, y - 10), (x + 55, y - 10)), 3.0, 3.4, 1.4)
    d.s(rect(x - 10, y - 90, 20, 70), 3.3, 3.8, 1.8)
    x = xs[2]
    d.s(poly((x - 70, y - 20), (x - 55, y + 70), (x + 55, y + 70), (x + 70, y - 20)), 4.1, 4.8, 2.0)
    d.dyn(lambda t, x=x: [np.stack([np.linspace(x - 64, x + 64, 40), y + 5 + 4 * np.sin(np.linspace(0, 12, 40) + t * 3)], 1)], 4.6, 1.2)
    d.dyn(lambda t, x=x: [rect(x - 50, y - 40 - 25 * (0.5 + 0.5 * math.sin(t * 1.6)), 100, 10)], 4.9, 1.6, "red")
    x = xs[3]
    d.s(poly((x - 70, y - 80), (x + 70, y - 80)), 5.4, 5.8, 2.0)
    d.s(rect(x - 55, y - 70, 110, 140), 5.6, 6.3, 1.6)
    d.dot((x - 40, y - 80), 5.9, 4, "red")
    d.dot((x + 40, y - 80), 6.0, 4, "red")
    # big sheet with fibre mesh and magnifier
    sx, sy = 120, 400
    d.s(rect(sx, sy, 440, 300), 6.4, 7.6, 2.0)
    r = np.random.default_rng(5)
    for k in range(38):
        p = np.array([r.uniform(sx + 20, sx + 420), r.uniform(sy + 20, sy + 280)])
        a = r.uniform(0, math.pi)
        ln = r.uniform(30, 80)
        q = p + ln * np.array([math.cos(a), math.sin(a)])
        m = (p + q) / 2 + r.normal(0, 8, 2)
        d.s(bezier(p, m, m, q, 12), 7.0 + k * 0.04, 7.6 + k * 0.04, 0.9, pen=False)
    mc = (760, 540)
    d.s(circle(mc, 140), 8.0, 9.0, 2.4, "red")
    d.s(poly((mc[0] + 99, mc[1] + 99), (mc[0] + 170, mc[1] + 170)), 8.8, 9.2, 5.0, "red")
    d.s(poly((sx + 360, sy + 150), (mc[0] - 140, mc[1])), 8.6, 9.0, 1.0, dash=True)
    for k in range(9):
        a = r.uniform(0, math.pi)
        p = np.array(mc) + r.uniform(-60, 60, 2)
        q = p + 110 * np.array([math.cos(a), math.sin(a)])
        p2 = p - 60 * np.array([math.cos(a), math.sin(a)])
        m = (p2 + q) / 2 + r.normal(0, 18, 2)
        pts = bezier(p2, m, m, q, 20)
        pts = pts[np.linalg.norm(pts - np.array(mc), axis=1) < 128]
        if len(pts) > 2:
            d.s(pts, 9.0 + k * 0.08, 9.6 + k * 0.08, 1.6, pen=False)
    d.txt("植物纤维交织成页", (mc[0], mc[1] + 175), 9.8, 20)
    d.txt("图三 · 造纸术 · 公元105年", (0, 745), 10.0, 20, anchor="lm")
    return d


def dg_tang():
    d = Diagram()
    gx, gy, gw, gh = 640, 90, 340, 320
    d.s(rect(gx, gy, gw, gh), 1.0, 2.6, 2.6)
    for k in range(1, 10):
        x = gx + gw * k / 10
        d.s(poly((x, gy + (45 if 4 <= k <= 6 else 0)), (x, gy + gh)), 2.0 + k * 0.08, 2.8 + k * 0.08, 0.9, pen=False)
    for k in range(1, 12):
        yy = gy + gh * k / 12
        x0 = gx if yy > gy + 45 else gx
        d.s(poly((x0, yy), (gx + gw, yy)), 2.6 + k * 0.07, 3.4 + k * 0.07, 0.9, pen=False)
    d.s(rect(gx + gw * 0.36, gy, gw * 0.28, 60), 3.2, 3.9, 2.0, "red")
    d.s(poly((gx + gw / 2, gy + 60), (gx + gw / 2, gy + gh)), 3.6, 4.4, 3.2, "red")
    d.txt("朱雀大街", (gx + gw / 2 + 12, gy + gh + 28), 4.4, 18, "red")
    d.txt("长安 · 一百零八坊", (gx + gw / 2, gy - 30), 4.0, 22)
    route = bezier((gx - 10, gy + gh * 0.6), (500, 620), (260, 330), (20, 560), 90)
    d.s(route, 4.6, 8.4, 2.0, "red", dash=True)
    nodes = [(0.0, "长安"), (0.33, "敦煌"), (0.66, "撒马尔罕"), (1.0, "巴格达")]
    for k, (f, nm) in enumerate(nodes):
        p = route[min(len(route) - 1, int(f * (len(route) - 1)))]
        t0 = 4.6 + f * 3.8
        if k:
            d.dot(p, t0, 9, "red")
            d.s(circle(p, 17), t0, t0 + 0.5, 1.2, pen=False)
            d.txt(nm, (p[0], p[1] + 42), t0 + 0.2, 22)
    for k in range(6):
        x = 120 + k * 60
        d.s(poly((x, 690), (x + 20, 670), (x + 30, 690)), 8.4 + k * 0.1, 8.8 + k * 0.1, 1.2, pen=False)
    d.txt("丝绸之路 · 万国来朝", (300, 110), 8.6, 24)
    d.s(poly((180, 136), (420, 136)), 8.9, 9.5, 1.2, "red", pen=False)
    d.dyn(lambda t: [circle((120 + (t * 18) % 400, 690 - 22), 6)], 9.0, 1.4, "red")
    d.txt("图四 · 长安城与丝绸之路", (0, 745), 10.0, 20, anchor="lm")
    return d


def dg_song():
    d = Diagram()
    # movable type
    ox, oy, cs = 20, 190, 70
    for i in range(5):
        d.s(poly((ox, oy + i * cs), (ox + 4 * cs, oy + i * cs)), 1.0 + i * 0.12, 1.8 + i * 0.12, 1.4, pen=False)
        d.s(poly((ox + i * cs, oy), (ox + i * cs, oy + 4 * cs)), 1.2 + i * 0.12, 2.0 + i * 0.12, 1.4, pen=False)
    chars = "天地玄黄宇宙洪荒日月盈昃辰宿列张"
    for k, ch in enumerate(chars):
        d.txt(ch, (ox + (k % 4 + 0.5) * cs, oy + (k // 4 + 0.5) * cs), 2.2 + k * 0.12, 36, "red" if k in (0, 5, 10, 15) else "ink", bold=True)
    d.txt("活字印刷", (ox + 2 * cs, oy + 4 * cs + 50), 4.2, 26, bold=True)
    d.txt("毕昇 · 约1040年", (ox + 2 * cs, oy + 4 * cs + 88), 4.5, 18)
    # compass
    c = (500, 330)
    d.s(circle(c, 150), 3.6, 4.8, 2.4)
    d.s(circle(c, 120), 3.9, 5.0, 1.2)
    for k in range(24):
        a = k * math.pi / 12
        d.s(poly((c[0] + 120 * math.cos(a), c[1] + 120 * math.sin(a)), (c[0] + 150 * math.cos(a), c[1] + 150 * math.sin(a))),
            4.8 + k * 0.03, 5.0 + k * 0.03, 1.0, pen=False)
    for nm, a in (("南", math.pi / 2), ("北", -math.pi / 2), ("东", 0), ("西", math.pi)):
        d.txt(nm, (c[0] + 178 * math.cos(a), c[1] + 178 * math.sin(a)), 5.2, 24, bold=True)

    def needle(t):
        ang = math.pi / 2 + 1.6 * math.exp(-(t - 5.2) * 0.45) * math.cos((t - 5.2) * 2.6) if t > 5.2 else math.pi / 2 + 1.6
        u = np.array([math.cos(ang), math.sin(ang)])
        v = np.array([-u[1], u[0]])
        C = np.array(c)
        tip, tail = C + u * 100, C - u * 70
        return [np.array([tip, C + v * 12, tail, C - v * 12, tip]), np.array([C + u * 100, C])]

    d.dyn(needle, 5.2, 2.2, "red")
    d.dot(c, 5.4, 5, "ink")
    d.txt("指南针", (c[0], c[1] + 230), 6.0, 26, bold=True)
    d.txt("司南 · 罗盘", (c[0], c[1] + 268), 6.3, 18)
    # fire arrow / gunpowder
    base = (780, 620)
    traj = bezier(base, (820, 350), (900, 200), (980, 120), 60)
    d.s(traj, 6.6, 8.6, 1.4, "red", dash=True)
    d.s(poly((760, 640), (800, 640)), 6.4, 6.8, 2.0)

    def rocket(t):
        k = clamp((t - 8.0) / 3.0)
        k = k * k
        i = int(k * (len(traj) - 2))
        p = traj[i]
        dv = traj[i + 1] - traj[i]
        dv /= np.linalg.norm(dv) + 1e-9
        nv = np.array([-dv[1], dv[0]])
        body = [p - dv * 60 + nv * 8, p + nv * 8, p + dv * 20, p - nv * 8, p - dv * 60 - nv * 8, p - dv * 60 + nv * 8]
        shaft = [p - dv * 150, p - dv * 60]
        fin = [p - dv * 150 + nv * 14, p - dv * 135, p - dv * 150 - nv * 14]
        return [np.array(body), np.array(shaft), np.array(fin)]

    d.dyn(rocket, 7.2, 2.0)

    def flame(t):
        k = clamp((t - 8.0) / 3.0) ** 2
        i = int(k * (len(traj) - 2))
        p = traj[i]
        dv = traj[i + 1] - traj[i]
        dv /= np.linalg.norm(dv) + 1e-9
        nv = np.array([-dv[1], dv[0]])
        L = 40 + 14 * math.sin(t * 31)
        out = []
        for s in (-1, 0, 1):
            out.append(np.array([p - dv * 60 + nv * 6 * s, p - dv * (60 + L * (1 - 0.3 * abs(s))) + nv * 10 * s * math.sin(t * 23)]))
        return out

    d.dyn(flame, 8.0, 2.0, "red")
    d.txt("火药", (840, 690), 8.6, 26, bold=True)
    d.txt("火箭 · 火铳", (840, 728), 8.9, 18)
    d.txt("图五 · 三大发明", (0, 745), 10.0, 20, anchor="lm")
    return d


def dg_ming():
    d = Diagram()
    hull = np.vstack([bezier((80, 250), (160, 330), (700, 340), (860, 230), 60)])
    d.s(hull, 1.0, 2.4, 2.8)
    d.s(poly((60, 210), (80, 250)), 1.0, 1.3, 2.4)
    d.s(poly((60, 210), (250, 225), (700, 222), (880, 190), (860, 230)), 1.5, 2.8, 2.2)
    masts = [(170, 150), (300, 210), (430, 240), (560, 220), (690, 170)]
    for k, (x, h) in enumerate(masts):
        yb = 222
        t0 = 2.5 + k * 0.35
        d.s(poly((x, yb), (x, yb - h - 20)), t0, t0 + 0.5, 2.0)
        sw = 40 + h * 0.35
        sail = poly((x - sw * 0.45, yb - 25), (x + sw * 0.55, yb - 25), (x + sw * 0.6, yb - h), (x - sw * 0.35, yb - h), close=True)
        d.s(sail, t0 + 0.4, t0 + 1.2, 1.8, "red")
        n = int(h / 28)
        for j in range(1, n):
            yy = yb - 25 - (h - 25) * j / n
            d.s(poly((x - sw * 0.44 + 0.1 * sw * j / n, yy), (x + sw * 0.57, yy)), t0 + 1.0 + j * 0.04, t0 + 1.3 + j * 0.04, 0.9, pen=False)
    for k in range(10):
        x = 150 + k * 65
        d.s(circle((x, 262), 6), 4.5 + k * 0.05, 4.8 + k * 0.05, 1.0, pen=False)

    def waves(t):
        out = []
        for j in range(3):
            xs = np.linspace(0, 960, 90)
            out.append(np.stack([xs, 330 + j * 20 + 5 * np.sin(xs / 40 + t * (1.5 + 0.3 * j) + j)], 1))
        return out

    d.dyn(waves, 2.0, 1.2)
    d.txt("郑和宝船", (0, 110), 4.8, 24, anchor="lm", bold=True)
    # route map
    route = [(520, 450), (440, 520), (360, 600), (230, 580), (90, 640)]
    rp = np.vstack([bezier(route[i], (np.array(route[i]) * 0.7 + np.array(route[i + 1]) * 0.3) + np.array([0, 25]),
                           (np.array(route[i]) * 0.3 + np.array(route[i + 1]) * 0.7) + np.array([0, 25]), route[i + 1], 20)
                    for i in range(len(route) - 1)])
    d.s(rp, 5.8, 8.8, 2.0, "red", dash=True)
    for k, (p, nm) in enumerate(zip(route, ["南京", "占城", "马六甲", "古里", "东非"])):
        t0 = 5.8 + k * 0.75
        d.dot(p, t0, 7, "red")
        d.txt(nm, (p[0], p[1] - 28), t0 + 0.2, 20)
    d.txt("七下西洋 · 1405—1433", (280, 700), 8.6, 20)
    # Beijing city plan
    cx, cy = 810, 560
    for k, (w_, h_, nm) in enumerate([(300, 290, "内城"), (180, 170, "皇城"), (90, 100, "紫禁城")]):
        t0 = 6.6 + k * 0.8
        d.s(rect(cx - w_ / 2, cy - h_ / 2 + (20 if k else 0), w_, h_), t0, t0 + 1.0, 2.2 if k < 2 else 2.8, "red" if k == 2 else "ink")
        d.txt(nm, (cx + w_ / 2 - 8, cy - h_ / 2 + (20 if k else 0) + 18), t0 + 0.8, 16, anchor="rm")
    d.s(poly((cx, cy - 145), (cx, cy + 145)), 9.0, 9.8, 1.2, dash=True)
    d.txt("营建北京", (cx, cy + 180), 9.2, 22, bold=True)
    d.txt("图六 · 远航与建城", (0, 745), 10.0, 20, anchor="lm")
    return d


def dg_modern():
    d = Diagram()
    d.s(poly((0, 620), (1000, 620)), 1.0, 2.0, 2.4)
    heights = [120, 180, 150, 260, 210, 330, 240, 400, 300, 200]
    for k, h in enumerate(heights):
        x = 30 + k * 52

        def bld(t, x=x, h=h, k=k):
            g = ease_out((t - 1.5 - k * 0.2) / 2.0)
            hh = h * g
            out = [rect(x, 620 - hh, 40, hh)]
            if g > 0.8:
                for j in range(int(hh / 30)):
                    yy = 620 - 15 - j * 30
                    out.append(poly((x + 8, yy), (x + 32, yy)))
            if h == 400 and g > 0.95:
                out.append(poly((x + 20, 620 - hh), (x + 20, 620 - hh - 40)))
            return out

        d.dyn(bld, 1.4 + k * 0.2, 1.6)
    d.txt("城市崛起", (270, 170), 5.0, 22, bold=True)
    # high speed train
    tr_ = poly((20, 700), (520, 700), (600, 690), (640, 672), (620, 655), (520, 648), (20, 648), close=True)
    d.s(tr_, 3.5, 5.0, 2.2)
    d.s(poly((20, 668), (560, 668)), 4.6, 5.2, 1.4, "red")
    for k in range(8):
        d.s(rect(60 + k * 58, 654, 34, 9), 5.0 + k * 0.05, 5.3 + k * 0.05, 1.0, pen=False)
    d.dyn(lambda t: [poly((0 - (t * 300) % 80 + j * 80, 716), (40 - (t * 300) % 80 + j * 80, 716)) for j in range(9)], 5.0, 1.4)
    d.txt("高铁", (330, 745), 5.4, 22, bold=True)
    # rocket + orbit
    ex, ey = 890, 150
    d.s(ellipse((ex, ey), 120, 45, -0.35), 5.5, 7.0, 1.4, dash=True)
    d.s(circle((ex, ey), 30), 5.8, 6.6, 2.0)
    d.s(ellipse((ex, ey), 30, 10), 6.2, 6.8, 1.0, pen=False)

    def sat(t):
        a = t * 1.3
        x = 120 * math.cos(a)
        y = 45 * math.sin(a)
        cr, sr = math.cos(-0.35), math.sin(-0.35)
        p = np.array([ex + x * cr - y * sr, ey + x * sr + y * cr])
        return [rect(p[0] - 6, p[1] - 6, 12, 12), poly(p + (-22, 0), p + (-8, 0)), poly(p + (8, 0), p + (22, 0))]

    d.dyn(sat, 7.0, 1.6, "red")

    def rocket(t):
        lift = max(0.0, t - 8.8) ** 2 * 28
        x, y = 820, 610 - lift
        body = poly((x - 16, y), (x - 16, y - 170), (x, y - 210), (x + 16, y - 170), (x + 16, y), close=True)
        boosters = [poly((x - 16, y), (x - 30, y), (x - 30, y - 80), (x - 16, y - 100)),
                    poly((x + 16, y), (x + 30, y), (x + 30, y - 80), (x + 16, y - 100))]
        bands = [poly((x - 16, y - 60), (x + 16, y - 60)), poly((x - 16, y - 130), (x + 16, y - 130))]
        return [body] + boosters + bands

    d.dyn(rocket, 6.8, 2.0)

    def plume(t):
        if t < 8.6:
            return []
        lift = max(0.0, t - 8.8) ** 2 * 28
        x, y = 820, 610 - lift
        out = []
        for s in range(-3, 4):
            L = 50 + 30 * abs(math.sin(t * 19 + s))
            out.append(poly((x + s * 6, y + 4), (x + s * 13, y + L)))
        return out

    d.dyn(plume, 8.6, 2.0, "red")
    d.s(poly((760, 620), (760, 380), (790, 380)), 6.5, 7.2, 1.4)
    d.txt("航天", (900, 660), 7.4, 22, bold=True)
    d.txt("图七 · 复兴之路", (0, 745), 10.0, 20, anchor="lm")
    return d


def dg_starmap():
    d = Diagram()
    c = (960, 500)
    for k, r in enumerate((430, 330, 220, 110)):
        d.s(circle(c, r), 0.2 + k * 0.35, 2.4 + k * 0.35, 1.6 if k == 0 else 1.0)
    for k in range(24):
        a = k * math.pi / 12
        d.s(poly((c[0] + 110 * math.cos(a), c[1] + 110 * math.sin(a)), (c[0] + 430 * math.cos(a), c[1] + 430 * math.sin(a))),
            1.0 + k * 0.05, 2.6 + k * 0.05, 0.7, pen=False)
    for k in range(120):
        a = k * math.pi / 60
        l = 14 if k % 10 == 0 else 6
        d.s(poly((c[0] + 430 * math.cos(a), c[1] + 430 * math.sin(a)), (c[0] + (430 + l) * math.cos(a), c[1] + (430 + l) * math.sin(a))),
            1.8 + k * 0.01, 2.0 + k * 0.01, 0.9, pen=False)
    r = np.random.default_rng(21)
    for g in range(9):
        a0 = g * 2 * math.pi / 9 + r.uniform(-0.2, 0.2)
        rr = r.uniform(170, 400)
        base = np.array([c[0] + rr * math.cos(a0), c[1] + rr * math.sin(a0)])
        pts = [base]
        for _ in range(r.integers(3, 6)):
            pts.append(pts[-1] + r.normal(0, 50, 2))
        pts = np.array(pts)
        t0 = 2.0 + g * 0.25
        d.s(pts, t0, t0 + 1.2, 1.0, pen=False)
        for p in pts:
            d.dot(tuple(p), t0 + 0.2, r.uniform(2.5, 5))
    names = ["紫微", "太微", "天市", "角", "亢", "氐", "房", "心", "尾", "箕", "斗", "牛"]
    for k, nm in enumerate(names):
        a = -math.pi / 2 + k * 2 * math.pi / 12 + 0.13
        d.txt(nm, (c[0] + 470 * math.cos(a) * 1.02, c[1] + 470 * math.sin(a) * 0.98), 2.8 + k * 0.08, 18)
    return d


DIAGRAMS = None

CHAPTERS = [
    None,
    dict(ch="第一章 · 大道", name="孔子", tag="我们确立大道", year="公元前 551 年",
         desc=["仁者爱人 · 有教无类", "儒家思想绵延两千五百年"]),
    dict(ch="第二章 · 一统", name="秦始皇", tag="我们一统天下", year="公元前 221 年",
         desc=["书同文 · 车同轨 · 统一度量衡", "郡县制奠定大一统格局"]),
    dict(ch="第三章 · 纸", name="蔡伦", tag="我们发明纸张", year="公元 105 年",
         desc=["以树皮、麻头、破布、渔网造纸", "知识从此得以廉价流传"]),
    dict(ch="第四章 · 盛世", name="唐朝", tag="我们盛世开放", year="公元 618 年",
         desc=["长安百万人口 · 万国来朝", "丝绸之路连接东西方"]),
    dict(ch="第五章 · 发明", name="宋朝", tag="我们印刷火药指南针", year="公元 960 年",
         desc=["活字印刷 · 火药 · 指南针", "改变世界的伟大发明"]),
    dict(ch="第六章 · 远航", name="明朝", tag="我们远航建城", year="公元 1405 年",
         desc=["郑和七下西洋 · 远抵东非", "营建北京城与紫禁城"]),
    dict(ch="第七章 · 崛起", name="近代", tag="我们重新崛起", year="1840 年 — 今",
         desc=["百年沧桑 · 自强不息", "高铁 · 航天 · 数字时代"]),
]

TL_YEARS = ["前551", "前221", "105", "618", "960", "1405", "当代"]
TL_POP = [2e7, 2e7, 5e7, 8e7, 1e8, 1.5e8, 1.4e9]
TL_POP_TXT = ["约两千万", "约两千万", "约五千万", "约八千万", "约一亿", "约一亿五千万", "约十四亿"]
TL_X0, TL_X1, TL_Y = 200, 1720, 1000


def tl_x(i):
    return TL_X0 + (TL_X1 - TL_X0) * i / 6


def tl_h(i):
    return 6 + 74 * (i / 6) ** 1.7


def palette(t):
    k = ink_mix(t)
    dk = darkness(t)
    return dict(ink=lerp_col(INK_DAY, INK_NIGHT, k), red=lerp_col(RED_DAY, RED_NIGHT, k),
                bg=lerp_col(PARCH, NIGHT, dk))


# ------------------------------------------------------------ comet
def comet_layer(t, path_fn, t0, t1, scale=1.0):
    layer = Image.new("RGB", (W, H), (0, 0, 0))
    k = (t - t0) / (t1 - t0)
    if k < -0.05 or k > 1.15:
        return None
    dr = ImageDraw.Draw(layer)
    r = np.random.default_rng(int(t * 1000))
    trail = 0.28
    for j in range(260):
        f = j / 260
        kk = k - f * trail
        if kk < 0 or kk > 1:
            continue
        p = np.array(path_fn(kk))
        spread = (6 + 60 * f) * scale
        p = p + r.normal(0, spread * 0.35, 2)
        rad = (16 * (1 - f) ** 1.5 + 2) * scale * r.uniform(0.6, 1.2)
        heat = (1 - f)
        col = (int(255 * min(1, 0.5 + heat)), int(255 * heat ** 1.3 * 0.9 + 30 * heat), int(255 * heat ** 4 * 0.8))
        dr.ellipse([p[0] - rad, p[1] - rad, p[0] + rad, p[1] + rad], fill=col)
    if 0 <= k <= 1:
        p = path_fn(k)
        for rr, col in ((34 * scale, (255, 140, 40)), (20 * scale, (255, 210, 120)), (10 * scale, (255, 255, 235))):
            dr.ellipse([p[0] - rr, p[1] - rr, p[0] + rr, p[1] + rr], fill=col)
    glow = layer.filter(ImageFilter.GaussianBlur(18 * scale))
    mid = layer.filter(ImageFilter.GaussianBlur(4))
    return ImageChops.add(ImageChops.add(glow, glow), mid)


def comet_path_title(k):
    x = lerp(-150, 2100, k)
    y = 160 + 520 * k + 120 * math.sin(k * math.pi)
    return (x, y)


def comet_path_final(k):
    x = lerp(2100, -200, k)
    y = 150 + 380 * k - 100 * math.sin(k * math.pi)
    return (x, y)


# ------------------------------------------------------------ frame composition
def render(fi):
    global DIAGRAMS, STARS, BG
    if DIAGRAMS is None:
        BG = _make_backgrounds()
        STARS = _make_stars()
        DIAGRAMS = [dg_starmap(), dg_confucius(), dg_qin(), dg_cailun(), dg_tang(), dg_song(), dg_ming(), dg_modern()]
    t = fi / FPS
    dk = darkness(t)
    pal = palette(t)
    parch, sky = BG
    base = Image.blend(parch, sky, dk) if 0 < dk < 1 else (sky if dk >= 1 else parch.copy())
    if dk >= 1:
        base = base.copy()

    scene = min(8, int(t // SCENE))
    ts = t - scene * SCENE
    zoom = 1.0 + 0.035 * ease(ts / 15) if scene < 8 else 1.0
    ov = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    ov_fixed = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))

    fade = ease(ts / 0.7) * ease((SCENE - ts) / 0.8) if scene < 8 else 1.0
    ctx = Ctx(ov, pal, fade)
    fx = Ctx(ov_fixed, pal, 1.0)
    pens = []

    # stars
    star_a = clamp((dk - 0.4) / 0.3)
    if star_a > 0:
        sd = ImageDraw.Draw(base)
        bgc = lerp_col(PARCH, NIGHT, dk)
        for x, y, s, ph, sp in STARS:
            tw = 0.6 + 0.4 * math.sin(t * sp + ph)
            a = star_a * tw
            rr = s * 0.7
            sd.ellipse([x - rr, y - rr, x + rr, y + rr], fill=lerp_col(bgc, (255, 248, 230), a))

    comet = None
    if scene == 0:
        draw_diagram(ctx, DIAGRAMS[0], ts, 0, 0, 1.0, pens=pens)
        a = ease((ts - 5.0) / 1.5)
        title_backing(ctx, a)
        ctx.text("薪火", (960, 445), 190, "ink", a, "mm", True, spacing=70)
        ctx.text("燧人取火 · 文明肇始", (960, 612), 26, "red", ease((ts - 6.0) / 1.2), "mm", False, spacing=12)
        ctx.text("中华文明的火种", (960, 672), 40, "ink", ease((ts - 6.8) / 1.2), "mm", False, spacing=14)
        la = ease((ts - 6.4) / 1.0)
        ctx.line([(960 - 300 * la, 560), (960 + 300 * la, 560)], 1.4, "red", la)
        comet = comet_layer(ts, comet_path_title, 1.5, 7.5)
    elif scene <= 7:
        ch = CHAPTERS[scene]
        ctx.text(ch["ch"], (150, 150), 30, "red", ease((ts - 0.3) / 0.8), "lm", True, spacing=6)
        la = ease((ts - 0.6) / 1.0)
        ctx.line([(150, 185), (150 + 420 * la, 185)], 1.4, "ink", la)
        ctx.text(ch["year"], (150, 290), 34, "ink", ease((ts - 0.8) / 0.8), "lm")
        nm = ch["name"]
        ctx.text(nm, (144, 410), 128 if len(nm) <= 2 else 112, "ink", ease((ts - 1.0) / 1.0), "lm", True, spacing=10)
        tag = ch["tag"]
        ctx.text(tag, (150, 545), 54 if len(tag) <= 6 else 44, "red", ease((ts - 1.8) / 1.0), "lm", True)
        for k, line in enumerate(ch["desc"]):
            ctx.text(line, (150, 640 + k * 48), 27, "ink", ease((ts - 2.8 - k * 0.5) / 1.0), "lm")
        draw_diagram(ctx, DIAGRAMS[scene], ts, 800, 130, 1.0, pens=pens)
    else:
        render_finale(ctx, fx, ts, t, pens)
        if ts > 11.2:
            comet = comet_layer(ts, comet_path_final, 11.4, 15.4, 1.3)

    for p in pens:
        ctx.disc(p, 10, "red", 0.25)
        ctx.disc(p, 5, "red", 0.9)

    draw_timeline(fx, t, scene, ts)

    # camera push-in on the scene layer, timeline stays fixed
    if zoom != 1.0:
        cw, chh = W * SS / zoom, H * SS / zoom
        x0, y0 = (W * SS - cw) / 2, (H * SS - chh) * 0.45
        ov = ov.resize((W, H), Image.LANCZOS, box=(x0, y0, x0 + cw, y0 + chh))
    else:
        ov = ov.resize((W, H), Image.LANCZOS)
    ov_fixed = ov_fixed.resize((W, H), Image.LANCZOS)
    out = base.convert("RGBA")
    out.alpha_composite(ov)
    out.alpha_composite(ov_fixed)
    out = out.convert("RGB")
    if comet is not None:
        out = ImageChops.add(out, comet)
    # flash on chapter cut
    fl = 0.0
    if scene >= 1:
        fl = max(0.0, 1 - ts / 0.35) * 0.35 * (0.4 + 0.6 * dk)
    if t >= 132:
        fl = max(fl, max(0.0, 1 - (t - 132) / 0.6) * 0.7)
    if fl > 0:
        out = Image.blend(out, Image.new("RGB", (W, H), (255, 236, 200)), fl)
    return out.tobytes()


_backing = {}


def title_backing(ctx, a):
    if a <= 0:
        return
    col = ctx.pal["bg"]
    if col not in _backing:
        m = Image.new("L", (W // 4, H // 4), 0)
        ImageDraw.Draw(m).ellipse([W / 8 - 150, H / 8 - 40, W / 8 + 150, H / 8 + 40], fill=200)
        m = m.filter(ImageFilter.GaussianBlur(28)).resize((W * SS, H * SS), Image.BICUBIC)
        _backing[col] = (Image.new("RGBA", (W * SS, H * SS), (*col, 255)), m)
    layer, mask = _backing[col]
    k = a * ctx.alpha
    lay = layer.copy()
    lay.putalpha(mask.point(lambda v: int(v * k)))
    ctx.img.alpha_composite(lay)


def draw_timeline(ctx, t, scene, ts):
    a = ease((t - 10.0) / 2.0)
    if a <= 0:
        return
    ctx.alpha = a
    ctx.line([(TL_X0 - 60, TL_Y), (TL_X1 + 60, TL_Y)], 1.4, "ink", 0.7)
    for k in range(0, 61):
        x = TL_X0 - 60 + k * (TL_X1 - TL_X0 + 120) / 60
        ctx.line([(x, TL_Y), (x, TL_Y + (8 if k % 5 == 0 else 4))], 1.0, "ink", 0.5)
    # progress (fractional milestone index)
    if scene <= 1:
        prog = 0.0
    elif scene <= 7:
        prog = (scene - 2) + ease(ts / 1.6)
    else:
        prog = 6.0
    for i in range(7):
        x = tl_x(i)
        active = (scene >= 1 and i <= prog + 1e-6)
        ctx.disc((x, TL_Y), 7 if active else 5, "red" if active else "ink", 1.0 if active else 0.6, fill=active, w=1.4)
        ctx.text(TL_YEARS[i], (x, TL_Y + 32), 20, "ink", 1.0 if active else 0.55, "mm")
    if scene >= 1:
        # rising scale curve (population, log scale)
        pts = []
        steps = 80
        for s in range(steps + 1):
            f = prog * s / steps
            i0 = int(f)
            i1 = min(6, i0 + 1)
            k = f - i0
            pts.append((lerp(tl_x(i0), tl_x(i1), k), TL_Y - lerp(tl_h(i0), tl_h(i1), ease(k))))
        pts.insert(0, (tl_x(0), TL_Y))
        ctx.line(pts, 2.0, "red", 0.9)
        for s in range(1, len(pts), 3):
            ctx.line([pts[s], (pts[s][0], TL_Y)], 0.8, "red", 0.25)
        head = pts[-1]
        ctx.disc(head, 14, "red", 0.25 + 0.15 * math.sin(t * 6))
        ctx.disc(head, 6, "red", 1.0)
        ci = int(round(prog))
        ctx.text("人口 " + TL_POP_TXT[ci], (head[0] + (18 if head[0] < 1600 else -18), head[1] - 26), 18, "red", 1.0, "lm" if head[0] < 1600 else "rm")
    ctx.text("文明尺度", (TL_X0 - 60, TL_Y - 88), 16, "ink", 0.6, "lm", spacing=4)
    ctx.line([(TL_X0 - 60, TL_Y - 75), (TL_X0 - 60, TL_Y)], 1.0, "ink", 0.5)
    ctx.alpha = 1.0


LEGACY = ["儒学", "一统", "纸", "开放", "印刷", "火药", "指南针", "远航", "复兴"]


def render_finale(ctx, fx, ts, t, pens):
    # 0-5.5s: accelerating montage of all seven chapters
    durs = [1.1, 0.95, 0.82, 0.72, 0.66, 0.62, 0.58]
    starts = np.concatenate([[0.2], 0.2 + np.cumsum(durs)])
    ctx.text("终章 · 不朽", (150, 150), 30, "red", ease((ts - 0.1) / 0.5) * ease((12.0 - ts) / 0.8), "lm", True, spacing=6)
    for i in range(7):
        s0, s1 = starts[i], starts[i + 1]
        if s0 <= ts < s1 + 0.15:
            k = (ts - s0) / (s1 - s0)
            a = ease(k / 0.15) * ease((1.15 - k) / 0.3)
            sc = 0.74 + 0.08 * k
            ctx.alpha = a
            draw_diagram(ctx, DIAGRAMS[i + 1], 12.0 + 3 * k, 960 - 500 * sc, 570 - 380 * sc, sc)
            ch = CHAPTERS[i + 1]
            ctx.text(ch["name"], (960, 150), 64, "ink", a, "mm", True, spacing=8)
            ctx.text(ch["tag"], (960, 225), 30, "red", a, "mm")
            ctx.alpha = 1.0
    # 5.8-11.5: constellation ring of legacies around a central title
    if ts >= 5.6:
        ga = ease((ts - 5.6) / 1.0) * ease((12.2 - ts) / 1.0)
        rot = (ts - 5.6) * 0.12
        cx, cy = 960, 470
        ctx.alpha = ga
        for i in range(7):
            a = rot - math.pi / 2 + i * 2 * math.pi / 7
            px, py = cx + 590 * math.cos(a), cy + 330 * math.sin(a)
            sc = 0.2
            draw_diagram(ctx, DIAGRAMS[i + 1], 20.0, px - 500 * sc, py - 380 * sc, sc)
            ctx.line([(cx + 150 * math.cos(a), cy + 90 * math.sin(a)), (px - 110 * math.cos(a), py - 80 * math.sin(a))], 0.8, "ink", 0.4)
        ctx.line(ellipse((cx, cy), 590, 330, n=200), 0.8, "ink", 0.35)
        ctx.alpha = 1.0
        ctx.text("不朽遗产", (cx, cy - 10), 120 * (0.9 + 0.1 * ease((ts - 5.8) / 1.5)), "ink", ga * ease((ts - 6.0) / 1.0), "mm", True, spacing=18)
        words = " · ".join(LEGACY)
        ctx.text(words, (cx, cy + 105), 26, "red", ga * ease((ts - 7.0) / 1.2), "mm")
        yr = int(lerp(-551, 2026, ease((ts - 5.8) / 5.0)))
        ys = f"公元前 {-yr} 年" if yr < 0 else f"公元 {yr} 年"
        ctx.text(ys, (cx, cy - 120), 24, "ink", ga * 0.8, "mm", spacing=4)
    # 12-16: comet, final title
    if ts >= 12.0:
        a = ease((ts - 12.4) / 1.2)
        title_backing(ctx, a)
        ctx.text("薪火", (960, 445), 190, "ink", a, "mm", True, spacing=70)
        ctx.text("薪火相传 · 生生不息", (960, 630), 40, "red", ease((ts - 13.2) / 1.0), "mm", False, spacing=12)
        la = ease((ts - 13.0) / 1.0)
        ctx.line([(960 - 300 * la, 560), (960 + 300 * la, 560)], 1.4, "red", la)


def main():
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    end = int(sys.argv[2]) if len(sys.argv) > 2 else int(DUR * FPS)
    out = sys.argv[3] if len(sys.argv) > 3 else "build/video.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(4) as pool:
        for k, buf in enumerate(pool.imap(render, range(start, end), chunksize=4)):
            p.stdin.write(buf)
            if k % 150 == 0:
                print(f"frame {start + k}/{end}", flush=True)
    p.stdin.close()
    p.wait()


if __name__ == "__main__":
    main()
