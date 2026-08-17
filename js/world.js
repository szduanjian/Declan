import * as THREE from "three";
import { BARRIER, querySurface } from "./circuit.js";

function windowTexture(seed) {
  const c = document.createElement("canvas");
  c.width = 64;
  c.height = 128;
  const ctx = c.getContext("2d");
  ctx.fillStyle = "#07060c";
  ctx.fillRect(0, 0, 64, 128);
  let r = seed;
  const rand = () => {
    r = (r * 16807) % 2147483647;
    return (r - 1) / 2147483646;
  };
  for (let y = 4; y < 124; y += 7) {
    for (let x = 4; x < 60; x += 6) {
      if (rand() > 0.38) continue;
      const neon = rand() > 0.7 ? (rand() > 0.5 ? "#3de7ff" : "#ff2bd6") : "#ffe9a8";
      ctx.fillStyle = neon;
      ctx.globalAlpha = 0.45 + rand() * 0.55;
      ctx.fillRect(x, y, 3, 4);
    }
  }
  ctx.globalAlpha = 1;
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.wrapS = THREE.RepeatWrapping;
  tex.wrapT = THREE.RepeatWrapping;
  return tex;
}

function signTexture(text, color) {
  const c = document.createElement("canvas");
  c.width = 256;
  c.height = 64;
  const ctx = c.getContext("2d");
  ctx.fillStyle = "#05040a";
  ctx.fillRect(0, 0, 256, 64);
  ctx.strokeStyle = color;
  ctx.lineWidth = 3;
  ctx.strokeRect(3, 3, 250, 58);
  ctx.fillStyle = color;
  ctx.font = "bold 28px Orbitron, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.shadowColor = color;
  ctx.shadowBlur = 12;
  ctx.fillText(text, 128, 34);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

export function createWorld(scene, samples) {
  scene.background = new THREE.Color(0x05010a);
  scene.fog = new THREE.FogExp2(0x090414, 0.011);

  const hemi = new THREE.HemisphereLight(0x3a2060, 0x050208, 0.55);
  scene.add(hemi);
  const moon = new THREE.DirectionalLight(0x8aa0ff, 0.35);
  moon.position.set(-40, 80, 20);
  scene.add(moon);

  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(900, 900),
    new THREE.MeshStandardMaterial({
      color: 0x08060e,
      roughness: 0.95,
      metalness: 0.05,
    })
  );
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = -0.02;
  ground.receiveShadow = true;
  scene.add(ground);

  addGrid(scene);
  addBuildings(scene, samples);
  addRain(scene);
  addSkyline(scene);
}

function addGrid(scene) {
  const grid = new THREE.GridHelper(700, 70, 0x3de7ff, 0x1a1030);
  grid.position.y = 0.01;
  grid.material.transparent = true;
  grid.material.opacity = 0.12;
  scene.add(grid);
}

function addBuildings(scene, samples) {
  const signs = ["NEXUS", "RONIN", "VOLT", "KAIRO", "PULSE", "NOVA", "DRIFT", "YEN-9"];
  const colors = [0xff2bd6, 0x3de7ff, 0xff4b1f, 0x39ff88, 0xc8b6ff];
  let seed = 17;
  const rand = () => {
    seed = (seed * 16807) % 2147483647;
    return (seed - 1) / 2147483646;
  };

  const group = new THREE.Group();
  group.name = "city";

  for (let gx = -11; gx <= 11; gx++) {
    for (let gz = -11; gz <= 11; gz++) {
      const x = gx * 20 + (rand() - 0.5) * 8;
      const z = gz * 20 + (rand() - 0.5) * 8;
      const surface = querySurface(samples, x, z);
      if (surface.dist < BARRIER + 10) continue;
      if (Math.hypot(x, z) < 28) continue;

      const h = 8 + rand() * 28 + (rand() > 0.85 ? 18 : 0);
      const w = 6 + rand() * 7;
      const d = 6 + rand() * 7;
      const tex = windowTexture(Math.floor(rand() * 9999) + 2);
      tex.repeat.set(1, Math.max(1, h / 12));
      const mat = new THREE.MeshStandardMaterial({
        color: 0x101018,
        map: tex,
        roughness: 0.7,
        metalness: 0.35,
        emissive: 0x0a0614,
        emissiveIntensity: 0.4,
      });
      const b = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat);
      b.position.set(x, h / 2, z);
      group.add(b);

      if (rand() > 0.62) {
        const color = colors[Math.floor(rand() * colors.length)];
        const edge = new THREE.Mesh(
          new THREE.BoxGeometry(w + 0.12, 0.14, d + 0.12),
          new THREE.MeshStandardMaterial({
            color,
            emissive: color,
            emissiveIntensity: 1.6,
          })
        );
        edge.position.set(x, h + 0.05, z);
        group.add(edge);
      }

      if (rand() > 0.78) {
        const label = signs[Math.floor(rand() * signs.length)];
        const hex = "#" + colors[Math.floor(rand() * colors.length)].toString(16).padStart(6, "0");
        const plane = new THREE.Mesh(
          new THREE.PlaneGeometry(w * 0.9, 1.3),
          new THREE.MeshBasicMaterial({ map: signTexture(label, hex), transparent: true })
        );
        plane.position.set(x, 6 + rand() * (h - 8), z + d / 2 + 0.08);
        group.add(plane);
      }
    }
  }
  scene.add(group);
}

function addSkyline(scene) {
  const mat = new THREE.MeshStandardMaterial({
    color: 0x0c0814,
    emissive: 0x3de7ff,
    emissiveIntensity: 0.08,
    roughness: 0.9,
  });
  for (let i = 0; i < 36; i++) {
    const a = (i / 36) * Math.PI * 2;
    const r = 240 + (i % 5) * 8;
    const h = 20 + (i * 17) % 40;
    const m = new THREE.Mesh(new THREE.BoxGeometry(10, h, 10), mat);
    m.position.set(Math.cos(a) * r, h / 2, Math.sin(a) * r);
    scene.add(m);
  }
}

export function addRain(scene) {
  const count = 1400;
  const positions = new Float32Array(count * 3);
  for (let i = 0; i < count; i++) {
    positions[i * 3] = (Math.random() - 0.5) * 180;
    positions[i * 3 + 1] = Math.random() * 40;
    positions[i * 3 + 2] = (Math.random() - 0.5) * 180;
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  const mat = new THREE.PointsMaterial({
    color: 0x9ad8ff,
    size: 0.12,
    transparent: true,
    opacity: 0.55,
    depthWrite: false,
  });
  const rain = new THREE.Points(geo, mat);
  rain.name = "rain";
  scene.add(rain);
  return rain;
}

export function updateRain(rain, car, dt) {
  if (!rain) return;
  const pos = rain.geometry.attributes.position;
  const arr = pos.array;
  for (let i = 0; i < pos.count; i++) {
    arr[i * 3 + 1] -= (18 + (i % 7)) * dt;
    if (arr[i * 3 + 1] < 0) {
      arr[i * 3] = car.x + (Math.random() - 0.5) * 90;
      arr[i * 3 + 1] = 18 + Math.random() * 22;
      arr[i * 3 + 2] = car.z + (Math.random() - 0.5) * 90;
    }
  }
  pos.needsUpdate = true;
  rain.position.set(0, 0, 0);
}
