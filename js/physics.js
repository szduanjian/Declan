/** Arcade bicycle-model driving: accel, brake, speed-sensitive steer, grip, drift. */

export function createCarState(spawn) {
  return {
    x: spawn.x,
    z: spawn.z,
    heading: spawn.heading,
    speed: 0,
    vx: 0,
    vz: 0,
    steer: 0,
    accelG: 0,
  };
}

export function resetCarState(state, spawn) {
  state.x = spawn.x;
  state.z = spawn.z;
  state.heading = spawn.heading;
  state.speed = 0;
  state.vx = 0;
  state.vz = 0;
  state.steer = 0;
  state.accelG = 0;
}

/**
 * @param {object} state
 * @param {{throttle:number, brake:number, steer:number}} input  steer in [-1,1]
 * @param {object} spec  car performance
 * @param {number} dt
 * @param {object} surface  from querySurface
 */
export function updateCar(state, input, spec, dt, surface) {
  dt = Math.min(Math.max(dt, 0), 0.05);
  const prevSpeed = state.speed;

  const speedAbs = Math.abs(state.speed);
  const speedNorm = Math.min(1, speedAbs / spec.maxSpeed);
  const steerLimit = spec.steer * (1 - speedNorm * 0.28);
  const steerTarget = clamp(input.steer, -1, 1) * steerLimit;
  state.steer += (steerTarget - state.steer) * Math.min(1, 9 * dt);

  let force = 0;
  if (input.throttle > 0) {
    const band = 1 - Math.pow(Math.max(0, state.speed) / spec.maxSpeed, 1.15);
    force += spec.accel * input.throttle * Math.max(0.12, band);
  }
  if (input.brake > 0) {
    if (state.speed > 1.2) force -= spec.brake * input.brake;
    else force -= spec.reverse * input.brake;
  }

  force -= state.speed * spec.roll * 0.72;
  force -= state.speed * Math.abs(state.speed) * spec.drag * 0.7;

  if (!surface.onTrack) {
    const dirt = surface.onShoulder ? 1.15 : 2.6;
    force -= state.speed * dirt;
  }

  state.speed += force * dt;
  if (state.speed > spec.maxSpeed) state.speed = spec.maxSpeed;
  if (state.speed < -spec.reverseMax) state.speed = -spec.reverseMax;

  const wheelBase = spec.wheelBase;
  if (speedAbs > 0.2) {
    const turn = (state.speed / wheelBase) * Math.tan(state.steer);
    state.heading += turn * dt;
  }

  const fwdX = Math.sin(state.heading);
  const fwdZ = Math.cos(state.heading);
  const desiredVx = fwdX * state.speed;
  const desiredVz = fwdZ * state.speed;

  let grip = spec.grip;
  if (!surface.onTrack) grip *= surface.onShoulder ? 0.45 : 0.22;
  if (input.brake > 0.4 && speedAbs > 10) grip *= 0.72;
  grip *= 1 - Math.min(0.35, Math.abs(state.steer) * speedNorm * 0.45);

  const blend = 1 - Math.exp(-grip * dt);
  state.vx += (desiredVx - state.vx) * blend;
  state.vz += (desiredVz - state.vz) * blend;

  state.speed = state.vx * fwdX + state.vz * fwdZ;

  state.x += state.vx * dt;
  state.z += state.vz * dt;

  if (surface.beyondBarrier && surface.penetration > 0) {
    state.x += surface.inwardX * surface.penetration;
    state.z += surface.inwardZ * surface.penetration;
    const vn = state.vx * -surface.inwardX + state.vz * -surface.inwardZ;
    if (vn > 0) {
      state.vx -= vn * 1.35 * -surface.inwardX;
      state.vz -= vn * 1.35 * -surface.inwardZ;
      state.speed *= 0.82;
    }
  }

  state.accelG = (state.speed - prevSpeed) / Math.max(dt, 0.0001);
  return state;
}

export function speedKmh(speed) {
  return Math.max(0, speed) * 5.05;
}

function clamp(v, a, b) {
  return Math.max(a, Math.min(b, v));
}
