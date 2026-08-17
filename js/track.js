import * as THREE from "three";
import { HALF_WIDTH, BARRIER } from "./circuit.js";

function roadTexture() {
  const c = document.createElement("canvas");
  c.width = 256;
  c.height = 512;
  const ctx = c.getContext("2d");
  ctx.fillStyle = "#14141c";
  ctx.fillRect(0, 0, 256, 512);

  const g = ctx.createLinearGradient(0, 0, 256, 0);
  g.addColorStop(0, "#2a0a28");
  g.addColorStop(0.08, "#16161f");
  g.addColorStop(0.92, "#16161f");
  g.addColorStop(1, "#0a2230");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 256, 512);

  ctx.strokeStyle = "rgba(80,80,96,0.35)";
  ctx.lineWidth = 2;
  for (let y = 0; y < 512; y += 18) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(256, y);
    ctx.stroke();
  }

  ctx.fillStyle = "#3de7ff";
  ctx.globalAlpha = 0.9;
  ctx.fillRect(10, 0, 8, 512);
  ctx.fillStyle = "#ff2bd6";
  ctx.fillRect(238, 0, 8, 512);
  ctx.globalAlpha = 1;

  ctx.fillStyle = "#e8e8f0";
  for (let y = 0; y < 512; y += 40) {
    ctx.fillRect(122, y, 12, 22);
  }

  const tex = new THREE.CanvasTexture(c);
  tex.wrapS = THREE.RepeatWrapping;
  tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(1, 28);
  tex.anisotropy = 8;
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

export function addTrack(scene, samples) {
  const group = new THREE.Group();
  group.name = "track";

  const n = samples.length;
  const positions = [];
  const normals = [];
  const uvs = [];
  const indices = [];
  const hw = HALF_WIDTH + 0.35;

  for (let i = 0; i < n; i++) {
    const s = samples[i];
    const lx = s.x + s.nx * hw;
    const lz = s.z + s.nz * hw;
    const rx = s.x - s.nx * hw;
    const rz = s.z - s.nz * hw;
    positions.push(lx, 0.04, lz, rx, 0.04, rz);
    normals.push(0, 1, 0, 0, 1, 0);
    const v = i / n * 28;
    uvs.push(0, v, 1, v);
  }
  for (let i = 0; i < n; i++) {
    const a = i * 2;
    const b = a + 1;
    const c = ((i + 1) % n) * 2;
    const d = c + 1;
    indices.push(a, c, b, b, c, d);
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geo.setAttribute("normal", new THREE.Float32BufferAttribute(normals, 3));
  geo.setAttribute("uv", new THREE.Float32BufferAttribute(uvs, 2));
  geo.setIndex(indices);

  const mat = new THREE.MeshStandardMaterial({
    map: roadTexture(),
    roughness: 0.32,
    metalness: 0.55,
    envMapIntensity: 0.8,
  });
  const road = new THREE.Mesh(geo, mat);
  road.receiveShadow = true;
  group.add(road);

  addRails(group, samples, hw + 0.6);
  addStartGate(group, samples);
  addLamps(group, samples);
  scene.add(group);
  return group;
}

function addRails(group, samples, offset) {
  const left = [];
  const right = [];
  for (let i = 0; i < samples.length; i += 1) {
    const s = samples[i];
    left.push(new THREE.Vector3(s.x + s.nx * offset, 0.42, s.z + s.nz * offset));
    right.push(new THREE.Vector3(s.x - s.nx * offset, 0.42, s.z - s.nz * offset));
  }
  left.push(left[0].clone());
  right.push(right[0].clone());

  const leftCurve = new THREE.CatmullRomCurve3(left, true);
  const rightCurve = new THREE.CatmullRomCurve3(right, true);
  const tubeL = new THREE.Mesh(
    new THREE.TubeGeometry(leftCurve, samples.length, 0.09, 6, true),
    new THREE.MeshStandardMaterial({
      color: 0xff2bd6,
      emissive: 0xff2bd6,
      emissiveIntensity: 1.8,
      roughness: 0.25,
      metalness: 0.4,
    })
  );
  const tubeR = new THREE.Mesh(
    new THREE.TubeGeometry(rightCurve, samples.length, 0.09, 6, true),
    new THREE.MeshStandardMaterial({
      color: 0x3de7ff,
      emissive: 0x3de7ff,
      emissiveIntensity: 1.8,
      roughness: 0.25,
      metalness: 0.4,
    })
  );
  group.add(tubeL, tubeR);

  const postMat = new THREE.MeshStandardMaterial({
    color: 0x1a1220,
    metalness: 0.6,
    roughness: 0.4,
    emissive: 0x3de7ff,
    emissiveIntensity: 0.15,
  });
  for (let i = 0; i < samples.length; i += 10) {
    const s = samples[i];
    for (const side of [1, -1]) {
      const p = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.85, 0.12), postMat);
      p.position.set(s.x + s.nx * offset * side, 0.42, s.z + s.nz * offset * side);
      group.add(p);
    }
  }
}

function addStartGate(group, samples) {
  const s = samples[2];
  const w = HALF_WIDTH + 1.4;
  const mat = new THREE.MeshStandardMaterial({
    color: 0x16101c,
    metalness: 0.7,
    roughness: 0.3,
  });
  const neon = new THREE.MeshStandardMaterial({
    color: 0xffe566,
    emissive: 0xffe566,
    emissiveIntensity: 2.2,
  });

  const left = new THREE.Mesh(new THREE.BoxGeometry(0.35, 5.2, 0.35), mat);
  left.position.set(s.x + s.nx * w, 2.6, s.z + s.nz * w);
  const right = left.clone();
  right.position.set(s.x - s.nx * w, 2.6, s.z - s.nz * w);
  const beam = new THREE.Mesh(new THREE.BoxGeometry(w * 2 + 0.4, 0.28, 0.28), neon);
  beam.position.set(s.x, 5.15, s.z);

  const stripe = new THREE.Mesh(
    new THREE.PlaneGeometry(w * 2, 1.4),
    new THREE.MeshStandardMaterial({
      color: 0xffffff,
      emissive: 0xffffff,
      emissiveIntensity: 0.35,
      roughness: 0.6,
    })
  );
  stripe.rotation.x = -Math.PI / 2;
  stripe.position.set(s.x, 0.06, s.z);
  stripe.rotation.z = Math.atan2(s.tx, s.tz);

  group.add(left, right, beam, stripe);

  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 96;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#0a0610";
  ctx.fillRect(0, 0, 512, 96);
  ctx.fillStyle = "#3de7ff";
  ctx.font = "bold 48px Orbitron, sans-serif";
  ctx.textAlign = "center";
  ctx.fillText("START / FINISH", 256, 62);
  const signTex = new THREE.CanvasTexture(canvas);
  signTex.colorSpace = THREE.SRGBColorSpace;
  const sign = new THREE.Mesh(
    new THREE.PlaneGeometry(w * 1.8, 0.7),
    new THREE.MeshBasicMaterial({ map: signTex, transparent: true })
  );
  sign.position.set(s.x, 4.55, s.z);
  sign.lookAt(s.x + s.tx, 4.55, s.z + s.tz);
  group.add(sign);
}

function addLamps(group, samples) {
  const poleMat = new THREE.MeshStandardMaterial({ color: 0x101018, metalness: 0.7, roughness: 0.35 });
  for (let i = 0; i < samples.length; i += 14) {
    const s = samples[i];
    const side = i % 28 === 0 ? 1 : -1;
    const color = side > 0 ? 0xff2bd6 : 0x3de7ff;
    const x = s.x + s.nx * (BARRIER + 1.6) * side;
    const z = s.z + s.nz * (BARRIER + 1.6) * side;
    const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.1, 6.2, 6), poleMat);
    pole.position.set(x, 3.1, z);
    const head = new THREE.Mesh(
      new THREE.SphereGeometry(0.22, 8, 8),
      new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 2.4 })
    );
    head.position.set(x, 6.25, z);
    group.add(pole, head);
    if (i % 42 === 0) {
      const light = new THREE.PointLight(color, 8, 32, 2);
      light.position.set(x, 6.1, z);
      group.add(light);
    }
  }
}
