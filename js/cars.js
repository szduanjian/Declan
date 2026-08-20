import * as THREE from "three";

export const CARS = [
  {
    id: "nexus",
    name: "NEXUS GT",
    tag: "BALANCED",
    blurb: "All-round street racer. Easy to place, hard to outdrive.",
    color: 0xff2bd6,
    accent: 0x3de7ff,
    cabin: 0x14061c,
    maxSpeed: 64,
    accel: 44,
    brake: 46,
    reverse: 15,
    reverseMax: 14,
    grip: 13.2,
    steer: 0.6,
    roll: 0.55,
    drag: 0.011,
    wheelBase: 2.7,
  },
  {
    id: "ronin",
    name: "RONIN X",
    tag: "TOP SPEED",
    blurb: "Long-gear monster. Loose rear, lethal on the straight.",
    color: 0xff4b1f,
    accent: 0xffd166,
    cabin: 0x1a0806,
    maxSpeed: 76,
    accel: 40,
    brake: 40,
    reverse: 13,
    reverseMax: 12,
    grip: 9.4,
    steer: 0.5,
    roll: 0.42,
    drag: 0.0085,
    wheelBase: 2.95,
  },
  {
    id: "volt",
    name: "VOLT WAGON",
    tag: "GRIP",
    blurb: "Heavy hauler. Plants itself in the rain and refuses to slide.",
    color: 0x39ff88,
    accent: 0xb8ff3d,
    cabin: 0x06140c,
    maxSpeed: 56,
    accel: 36,
    brake: 54,
    reverse: 16,
    reverseMax: 13,
    grip: 16.8,
    steer: 0.66,
    roll: 0.7,
    drag: 0.014,
    wheelBase: 3.05,
  },
  {
    id: "spectre",
    name: "SPECTRE",
    tag: "LAUNCH",
    blurb: "Canopy hypercar. Hits hard out of slow corners.",
    color: 0xc8b6ff,
    accent: 0x7b2cbf,
    cabin: 0x070614,
    maxSpeed: 68,
    accel: 54,
    brake: 44,
    reverse: 14,
    reverseMax: 13,
    grip: 11.1,
    steer: 0.56,
    roll: 0.5,
    drag: 0.01,
    wheelBase: 2.55,
  },
];

export function createCarMesh(spec) {
  const g = new THREE.Group();
  g.name = spec.id;

  const bodyMat = new THREE.MeshStandardMaterial({
    color: spec.color,
    metalness: 0.72,
    roughness: 0.28,
    emissive: spec.color,
    emissiveIntensity: 0.12,
  });
  const accentMat = new THREE.MeshStandardMaterial({
    color: spec.accent,
    metalness: 0.4,
    roughness: 0.2,
    emissive: spec.accent,
    emissiveIntensity: 0.85,
  });
  const cabinMat = new THREE.MeshStandardMaterial({
    color: spec.cabin,
    metalness: 0.2,
    roughness: 0.15,
    emissive: spec.accent,
    emissiveIntensity: 0.08,
    transparent: true,
    opacity: 0.88,
  });
  const darkMat = new THREE.MeshStandardMaterial({
    color: 0x111118,
    metalness: 0.6,
    roughness: 0.4,
  });

  const low = spec.id === "spectre";
  const tall = spec.id === "volt";
  const long = spec.id === "ronin";

  const body = new THREE.Mesh(
    new THREE.BoxGeometry(long ? 2.05 : 1.9, tall ? 0.55 : low ? 0.32 : 0.42, long ? 4.4 : 3.9),
    bodyMat
  );
  body.position.y = tall ? 0.55 : 0.48;
  g.add(body);

  const cabin = new THREE.Mesh(
    new THREE.BoxGeometry(1.55, tall ? 0.55 : 0.38, tall ? 1.7 : 1.45),
    cabinMat
  );
  cabin.position.set(0, tall ? 0.95 : 0.78, tall ? -0.15 : -0.25);
  g.add(cabin);

  if (spec.id === "ronin") {
    const spoiler = new THREE.Mesh(new THREE.BoxGeometry(1.9, 0.08, 0.42), accentMat);
    spoiler.position.set(0, 0.92, -1.95);
    g.add(spoiler);
    const stalkL = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.28, 0.08), darkMat);
    stalkL.position.set(-0.7, 0.78, -1.85);
    const stalkR = stalkL.clone();
    stalkR.position.x = 0.7;
    g.add(stalkL, stalkR);
  }

  if (spec.id === "spectre") {
    const nose = new THREE.Mesh(new THREE.BoxGeometry(1.5, 0.18, 1.1), bodyMat);
    nose.position.set(0, 0.4, 1.7);
    g.add(nose);
  }

  const stripe = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.02, 3.4), accentMat);
  stripe.position.set(0, body.position.y + (tall ? 0.29 : 0.22), 0.1);
  g.add(stripe);

  const glow = new THREE.Mesh(
    new THREE.BoxGeometry(1.7, 0.04, 3.5),
    new THREE.MeshStandardMaterial({
      color: spec.accent,
      emissive: spec.accent,
      emissiveIntensity: 1.6,
      transparent: true,
      opacity: 0.7,
    })
  );
  glow.position.y = 0.08;
  g.add(glow);

  const lightGeo = new THREE.BoxGeometry(0.28, 0.1, 0.08);
  const lightMat = new THREE.MeshStandardMaterial({
    color: 0xfff4cc,
    emissive: 0xfff1b8,
    emissiveIntensity: 2.4,
  });
  const hl = new THREE.Mesh(lightGeo, lightMat);
  hl.position.set(-0.62, 0.46, 1.96);
  const hr = hl.clone();
  hr.position.x = 0.62;
  g.add(hl, hr);

  const tailMat = new THREE.MeshStandardMaterial({
    color: 0xff1a4a,
    emissive: 0xff1a4a,
    emissiveIntensity: 1.4,
  });
  const tl = new THREE.Mesh(new THREE.BoxGeometry(0.38, 0.08, 0.06), tailMat);
  tl.position.set(-0.58, 0.5, -1.96);
  const tr = tl.clone();
  tr.position.x = 0.58;
  g.add(tl, tr);

  const wheels = new THREE.Group();
  wheels.name = "wheels";
  const wheelMat = new THREE.MeshStandardMaterial({
    color: 0x1a1a22,
    metalness: 0.3,
    roughness: 0.55,
  });
  const rimMat = new THREE.MeshStandardMaterial({
    color: spec.accent,
    emissive: spec.accent,
    emissiveIntensity: 0.45,
    metalness: 0.8,
    roughness: 0.25,
  });

  const places = [
    [-0.86, 0.28, 1.25],
    [0.86, 0.28, 1.25],
    [-0.86, 0.28, -1.25],
    [0.86, 0.28, -1.25],
  ];
  for (const [x, y, z] of places) {
    const w = new THREE.Group();
    const tire = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.3, 0.22, 14), wheelMat);
    tire.rotation.z = Math.PI / 2;
    const rim = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.16, 0.24, 10), rimMat);
    rim.rotation.z = Math.PI / 2;
    w.add(tire, rim);
    w.position.set(x, y, z);
    wheels.add(w);
  }
  g.add(wheels);

  const lamp = new THREE.SpotLight(0xfff3c4, 10, 46, 0.5, 0.4, 1.1);
  lamp.position.set(0, 0.85, 1.7);
  lamp.target.position.set(0, 0, 14);
  g.add(lamp, lamp.target);

  g.userData.wheels = wheels;
  g.userData.tail = [tl, tr];
  return g;
}

export function updateCarVisual(mesh, state, dt) {
  mesh.position.set(state.x, 0, state.z);
  mesh.rotation.y = state.heading;
  const roll = -state.steer * Math.min(1, Math.abs(state.speed) / 20) * 0.35;
  const pitch = THREE.MathUtils.clamp(-state.accelG * 0.004, -0.08, 0.1);
  mesh.rotation.z = THREE.MathUtils.lerp(mesh.rotation.z, roll, 1 - Math.exp(-8 * dt));
  mesh.rotation.x = THREE.MathUtils.lerp(mesh.rotation.x, pitch, 1 - Math.exp(-8 * dt));

  const spin = (state.speed / 0.3) * dt;
  if (mesh.userData.wheels) {
    for (const w of mesh.userData.wheels.children) {
      w.rotation.x += spin;
    }
  }
  if (mesh.userData.tail) {
    const braking = state.accelG < -8;
    for (const t of mesh.userData.tail) {
      t.material.emissiveIntensity = braking ? 3.2 : 1.2;
    }
  }
}
