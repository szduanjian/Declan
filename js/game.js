import * as THREE from "three";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { CARS, createCarMesh, updateCarVisual } from "./cars.js";
import { createCarState, resetCarState, updateCar, speedKmh } from "./physics.js";
import {
  TOTAL_LAPS,
  buildSamples,
  querySurface,
  getSpawn,
  createLapTracker,
  updateLap,
  formatTime,
} from "./circuit.js";
import { addTrack } from "./track.js";
import { createWorld, addRain, updateRain } from "./world.js";
import { EngineAudio } from "./audio.js";

const BEST_KEY = "neon-circuit-best";
const BEST_CAR_KEY = "neon-circuit-best-car";

const keys = new Set();
window.addEventListener("keydown", (e) => {
  keys.add(e.code);
  if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Space"].includes(e.code)) {
    e.preventDefault();
  }
});
window.addEventListener("keyup", (e) => keys.delete(e.code));

function inputFromKeys() {
  const up = keys.has("KeyW") || keys.has("ArrowUp");
  const down = keys.has("KeyS") || keys.has("ArrowDown");
  const left = keys.has("KeyA") || keys.has("ArrowLeft");
  const right = keys.has("KeyD") || keys.has("ArrowRight");
  return {
    throttle: up ? 1 : 0,
    brake: down ? 1 : 0,
    // Chase cam lookAt: at heading 0, screen right is world -X. Positive steer yaws the nose left on screen.
    steer: (left ? 1 : 0) + (right ? -1 : 0),
  };
}

const el = {
  hud: document.getElementById("hud"),
  menu: document.getElementById("menu"),
  cars: document.getElementById("car-grid"),
  countdown: document.getElementById("countdown"),
  finish: document.getElementById("finish"),
  finishBody: document.getElementById("finish-body"),
  speed: document.getElementById("speed-value"),
  gear: document.getElementById("gear-value"),
  lap: document.getElementById("lap-value"),
  time: document.getElementById("time-value"),
  best: document.getElementById("best-value"),
  sector: document.getElementById("sector-value"),
  carName: document.getElementById("car-name"),
  minimap: document.getElementById("minimap"),
  toast: document.getElementById("toast"),
};

const samples = buildSamples(420);
const spawn = getSpawn(samples);

let mode = "menu";
let selected = 0;
let carSpec = CARS[0];
let carState = createCarState(spawn);
let lap = createLapTracker();
let raceTime = 0;
let bestTime = loadBest();
let countdown = 0;
let last = performance.now();

const audio = new EngineAudio();
let muted = false;

const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
document.getElementById("viewport").appendChild(renderer.domElement);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 600);
camera.position.set(0, 8, -16);

const composer = new EffectComposer(renderer);
composer.addPass(new RenderPass(scene, camera));
const bloom = new UnrealBloomPass(new THREE.Vector2(window.innerWidth, window.innerHeight), 0.62, 0.5, 0.72);
composer.addPass(bloom);

createWorld(scene, samples);
addTrack(scene, samples);
const rain = addRain(scene);

let carMesh = createCarMesh(carSpec);
scene.add(carMesh);

const camTarget = new THREE.Vector3();
const camPos = new THREE.Vector3();

function loadBest() {
  const n = Number(localStorage.getItem(BEST_KEY));
  return Number.isFinite(n) && n > 0 ? n : null;
}

function saveBest(time, carId) {
  const prev = loadBest();
  if (!prev || time < prev) {
    localStorage.setItem(BEST_KEY, String(time));
    localStorage.setItem(BEST_CAR_KEY, carId);
    bestTime = time;
    return true;
  }
  return false;
}

function buildMenu() {
  el.cars.innerHTML = "";
  CARS.forEach((car, i) => {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "car-card" + (i === selected ? " selected" : "");
    card.dataset.index = String(i);
    card.innerHTML = `
      <div class="swatch" style="--c:#${car.color.toString(16).padStart(6, "0")};--a:#${car.accent.toString(16).padStart(6, "0")}"></div>
      <div class="meta">
        <strong>${car.name}</strong>
        <span class="tag">${car.tag}</span>
        <p>${car.blurb}</p>
        <small>TOP ${Math.round(car.maxSpeed * 5.05)} · GRIP ${car.grip.toFixed(0)} · ACCEL ${car.accel}</small>
      </div>`;
    card.addEventListener("click", () => {
      selected = i;
      highlightMenu();
      previewCar();
    });
    el.cars.appendChild(card);
  });
  highlightMenu();
}

function highlightMenu() {
  [...el.cars.children].forEach((n, i) => n.classList.toggle("selected", i === selected));
}

function previewCar() {
  scene.remove(carMesh);
  carSpec = CARS[selected];
  carMesh = createCarMesh(carSpec);
  scene.add(carMesh);
  resetCarState(carState, spawn);
  updateCarVisual(carMesh, carState, carSpec, 0.016);
}

function startRace(force = false) {
  if ((mode === "countdown" || mode === "racing") && !force) return;
  audio.unlock();
  document.activeElement?.blur();
  carSpec = CARS[selected];
  if (carMesh.name !== carSpec.id) previewCar();
  resetCarState(carState, spawn);
  snapChaseCam();
  lap = createLapTracker();
  raceTime = 0;
  mode = "countdown";
  countdown = 3.05;
  el.menu.classList.add("hidden");
  el.finish.classList.add("hidden");
  el.hud.classList.remove("hidden");
  el.carName.textContent = carSpec.name;
  el.best.textContent = formatTime(bestTime ?? NaN);
  toast(`${carSpec.name} · 3 LAPS`);
}

function finishRace() {
  mode = "finish";
  audio.stop();
  const record = saveBest(raceTime, carSpec.id);
  el.finish.classList.remove("hidden");
  el.finishBody.innerHTML = `
    <h2>${record ? "NEW BEST" : "FINISH"}</h2>
    <p class="big">${formatTime(raceTime)}</p>
    <p>${carSpec.name} · ${TOTAL_LAPS} laps</p>
    <p>Best ${formatTime(bestTime ?? NaN)}</p>
    <p class="hint">ENTER or R to race again · ESC for garage</p>`;
}

function returnToMenu() {
  mode = "menu";
  audio.stop();
  resetCarState(carState, spawn);
  el.menu.classList.remove("hidden");
  el.hud.classList.add("hidden");
  el.finish.classList.add("hidden");
  el.countdown.textContent = "";
  highlightMenu();
}

function toast(text) {
  el.toast.textContent = text;
  el.toast.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.toast.classList.remove("show"), 1400);
}

window.addEventListener("keydown", (e) => {
  audio.unlock();
  if (e.code === "KeyM") {
    muted = !muted;
    toast(muted ? "AUDIO OFF" : "AUDIO ON");
  }
  if (e.code === "KeyF") {
    if (!document.fullscreenElement) document.documentElement.requestFullscreen?.();
    else document.exitFullscreen?.();
  }
  if (mode === "menu") {
    if (e.code === "ArrowLeft" || e.code === "KeyA") {
      selected = (selected + CARS.length - 1) % CARS.length;
      highlightMenu();
      previewCar();
    }
    if (e.code === "ArrowRight" || e.code === "KeyD") {
      selected = (selected + 1) % CARS.length;
      highlightMenu();
      previewCar();
    }
    if (e.code === "Enter" || e.code === "Space") startRace(true);
  } else if (mode === "racing" || mode === "countdown") {
    if (e.code === "KeyR") startRace(true);
    if (e.code === "Escape") returnToMenu();
  } else if (mode === "finish") {
    if (e.code === "Enter" || e.code === "KeyR" || e.code === "Space") startRace(true);
    if (e.code === "Escape") returnToMenu();
  }
});

document.getElementById("start-btn").addEventListener("click", () => startRace(true));
document.getElementById("again-btn").addEventListener("click", () => startRace(true));
document.getElementById("garage-btn").addEventListener("click", returnToMenu);

function snapChaseCam() {
  const hx = Math.sin(carState.heading);
  const hz = Math.cos(carState.heading);
  camPos.set(carState.x - hx * 9.2, 3.6, carState.z - hz * 9.2);
  camTarget.set(carState.x + hx * 10, 1.1, carState.z + hz * 10);
  camera.position.copy(camPos);
  camera.lookAt(camTarget);
}

function updateCamera(dt) {
  const look = 10 + Math.abs(carState.speed) * 0.12;
  const back = 9.2 + Math.abs(carState.speed) * 0.04;
  const height = 3.6 + Math.abs(carState.speed) * 0.01;
  const hx = Math.sin(carState.heading);
  const hz = Math.cos(carState.heading);
  camTarget.set(carState.x + hx * look, 1.1, carState.z + hz * look);
  const desired = new THREE.Vector3(
    carState.x - hx * back,
    height,
    carState.z - hz * back
  );
  const t = 1 - Math.exp(-5.2 * dt);
  camPos.lerp(desired, mode === "menu" ? 0.08 : t);
  camera.position.copy(camPos);
  camera.lookAt(camTarget);
  camera.fov = THREE.MathUtils.lerp(camera.fov, 58 + Math.abs(carState.speed) * 0.22, 0.08);
  camera.updateProjectionMatrix();
}

function drawMinimap() {
  const ctx = el.minimap.getContext("2d");
  const w = el.minimap.width;
  const h = el.minimap.height;
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = "rgba(6,4,12,0.72)";
  ctx.fillRect(0, 0, w, h);

  let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity;
  for (const s of samples) {
    if (s.x < minX) minX = s.x;
    if (s.x > maxX) maxX = s.x;
    if (s.z < minZ) minZ = s.z;
    if (s.z > maxZ) maxZ = s.z;
  }
  const pad = 18;
  const sx = (w - pad * 2) / (maxX - minX);
  const sz = (h - pad * 2) / (maxZ - minZ);
  const sxy = Math.min(sx, sz);
  const mapX = (x) => pad + (x - minX) * sxy;
  const mapY = (z) => h - pad - (z - minZ) * sxy;

  ctx.strokeStyle = "#3de7ff";
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.moveTo(mapX(samples[0].x), mapY(samples[0].z));
  for (const s of samples) ctx.lineTo(mapX(s.x), mapY(s.z));
  ctx.closePath();
  ctx.stroke();

  ctx.fillStyle = "#ffe566";
  ctx.fillRect(mapX(samples[2].x) - 3, mapY(samples[2].z) - 3, 6, 6);

  ctx.fillStyle = `#${carSpec.color.toString(16).padStart(6, "0")}`;
  ctx.beginPath();
  ctx.arc(mapX(carState.x), mapY(carState.z), 4, 0, Math.PI * 2);
  ctx.fill();
}

function updateHud() {
  el.speed.textContent = String(Math.round(speedKmh(carState.speed))).padStart(3, "0");
  const gear = carState.speed < 0.4 ? "N" : carState.speed < 0 ? "R" : String(1 + Math.min(5, Math.floor(Math.abs(carState.speed) / 10)));
  el.gear.textContent = gear;
  el.lap.textContent = lap.finished ? `${TOTAL_LAPS}/${TOTAL_LAPS}` : `${lap.lap}/${TOTAL_LAPS}`;
  el.time.textContent = formatTime(raceTime);
  el.best.textContent = formatTime(bestTime ?? NaN);
  el.sector.textContent = `S${lap.next === 0 ? TOTAL_LAPS : Math.max(1, lap.next)}`;
}

function tick(now) {
  const dt = Math.min(0.033, (now - last) / 1000);
  last = now;

  if (mode === "menu") {
    carMesh.rotation.y += dt * 0.55;
    const orbit = now * 0.00025;
    camPos.set(
      spawn.x + Math.sin(orbit) * 7.4,
      2.6,
      spawn.z + Math.cos(orbit) * 7.4
    );
    camera.position.copy(camPos);
    camera.lookAt(spawn.x, 0.55, spawn.z);
    camera.fov = 58;
    camera.updateProjectionMatrix();
    updateRain(rain, { x: spawn.x, z: spawn.z }, dt);
  } else {
    const input = inputFromKeys();
    if (mode === "countdown") {
      countdown -= dt;
      if (countdown > 0) {
        el.countdown.textContent = String(Math.max(1, Math.ceil(countdown)));
      } else {
        el.countdown.textContent = "GO";
        mode = "racing";
        toast("RACE");
      }
      updateCarVisual(carMesh, carState, carSpec, dt);
    } else if (mode === "racing") {
      raceTime += dt;
      const surface = querySurface(samples, carState.x, carState.z);
      updateCar(carState, input, carSpec, dt, surface);
      updateLap(lap, surface.t);
      if (lap.justLapped && !lap.finished) toast(`LAP ${lap.lap - 1}  ${formatTime(raceTime)}`);
      if (lap.finished) finishRace();
      if (countdown > -0.7) {
        countdown -= dt;
        el.countdown.textContent = countdown > -0.7 ? "GO" : "";
      } else {
        el.countdown.textContent = "";
      }
      updateCarVisual(carMesh, carState, carSpec, dt);
      audio.update(carState.speed, input.throttle, muted);
    } else if (mode === "finish") {
      const surface = querySurface(samples, carState.x, carState.z);
      updateCar(carState, { throttle: 0, brake: 0.35, steer: 0 }, carSpec, dt, surface);
      updateCarVisual(carMesh, carState, carSpec, dt);
    }
    updateCamera(dt);
    updateRain(rain, carState, dt);
    updateHud();
    drawMinimap();
  }

  composer.render();
  requestAnimationFrame(tick);
}

function onResize() {
  const w = window.innerWidth;
  const h = window.innerHeight;
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h);
  composer.setSize(w, h);
  bloom.setSize(w, h);
}
window.addEventListener("resize", onResize);

buildMenu();
previewCar();
el.hud.classList.add("hidden");
el.best.textContent = formatTime(bestTime ?? NaN);
requestAnimationFrame(tick);
