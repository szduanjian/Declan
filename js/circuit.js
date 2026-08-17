/** Closed neon street circuit: geometry queries and lap logic. No renderer deps. */

export const HALF_WIDTH = 8.2;
export const SHOULDER = 3.4;
export const BARRIER = 12.4;
export const TOTAL_LAPS = 3;
export const CHECKPOINTS = 8;

/** Control points as [x, z]. Closed loop. */
export const CONTROL_POINTS = [
  [0, 118],
  [46, 122],
  [96, 116],
  [138, 96],
  [168, 58],
  [176, 10],
  [162, -36],
  [128, -68],
  [78, -86],
  [24, -90],
  [-18, -74],
  [-36, -42],
  [-22, -8],
  [-48, 16],
  [-92, 22],
  [-128, 8],
  [-150, 36],
  [-146, 78],
  [-118, 108],
  [-68, 122],
  [-24, 120],
];

function catmullRom(p0, p1, p2, p3, t) {
  const t2 = t * t;
  const t3 = t2 * t;
  return 0.5 * (
    2 * p1 +
    (-p0 + p2) * t +
    (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 +
    (-p0 + 3 * p1 - 3 * p2 + p3) * t3
  );
}

export function buildSamples(count = 420) {
  const pts = CONTROL_POINTS;
  const n = pts.length;
  const samples = [];

  for (let i = 0; i < count; i++) {
    const u = (i / count) * n;
    const i1 = Math.floor(u) % n;
    const t = u - Math.floor(u);
    const i0 = (i1 - 1 + n) % n;
    const i2 = (i1 + 1) % n;
    const i3 = (i1 + 2) % n;
    const x = catmullRom(pts[i0][0], pts[i1][0], pts[i2][0], pts[i3][0], t);
    const z = catmullRom(pts[i0][1], pts[i1][1], pts[i2][1], pts[i3][1], t);
    samples.push({ x, z, t: i / count, tx: 1, tz: 0, nx: 0, nz: 1, segLen: 1 });
  }

  let length = 0;
  for (let i = 0; i < count; i++) {
    const a = samples[i];
    const b = samples[(i + 1) % count];
    let tx = b.x - a.x;
    let tz = b.z - a.z;
    const seg = Math.hypot(tx, tz) || 1;
    tx /= seg;
    tz /= seg;
    a.tx = tx;
    a.tz = tz;
    a.nx = -tz;
    a.nz = tx;
    a.segLen = seg;
    length += seg;
  }
  samples.lengthMeters = length;
  return samples;
}

export function querySurface(samples, x, z) {
  let best = 0;
  let bestD = Infinity;
  for (let i = 0; i < samples.length; i++) {
    const dx = x - samples[i].x;
    const dz = z - samples[i].z;
    const d = dx * dx + dz * dz;
    if (d < bestD) {
      bestD = d;
      best = i;
    }
  }

  const s = samples[best];
  const dx = x - s.x;
  const dz = z - s.z;
  const lateral = dx * s.nx + dz * s.nz;
  const dist = Math.abs(lateral);
  const sign = lateral >= 0 ? 1 : -1;

  return {
    index: best,
    t: s.t,
    tx: s.tx,
    tz: s.tz,
    nx: s.nx,
    nz: s.nz,
    lateral,
    dist,
    onTrack: dist < HALF_WIDTH,
    onShoulder: dist >= HALF_WIDTH && dist < HALF_WIDTH + SHOULDER,
    beyondBarrier: dist > BARRIER,
    inwardX: -sign * s.nx,
    inwardZ: -sign * s.nz,
    penetration: dist > BARRIER ? dist - BARRIER : 0,
  };
}

export function getSpawn(samples) {
  const s = samples[4];
  return {
    x: s.x,
    z: s.z,
    heading: Math.atan2(s.tx, s.tz),
  };
}

export function createLapTracker() {
  return {
    next: 1,
    lap: 1,
    finished: false,
    justLapped: false,
  };
}

export function updateLap(tracker, progress) {
  tracker.justLapped = false;
  if (tracker.finished) return tracker;

  const n = CHECKPOINTS;
  const target = tracker.next / n;
  let diff = progress - target;
  if (diff > 0.5) diff -= 1;
  if (diff < -0.5) diff += 1;

  if (Math.abs(diff) < 0.065) {
    if (tracker.next === 0) {
      if (tracker.lap >= TOTAL_LAPS) {
        tracker.finished = true;
        tracker.justLapped = true;
      } else {
        tracker.lap += 1;
        tracker.justLapped = true;
        tracker.next = 1;
      }
    } else {
      tracker.next += 1;
      if (tracker.next >= n) tracker.next = 0;
    }
  }
  return tracker;
}

export function formatTime(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return "--:--.--";
  const m = Math.floor(seconds / 60);
  const s = seconds - m * 60;
  return `${String(m).padStart(2, "0")}:${s.toFixed(2).padStart(5, "0")}`;
}
