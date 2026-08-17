# NEON CIRCUIT

A single-player cyberpunk street racer you can open in a modern browser. Night city, neon barriers, rain, four machines, and a closed 3-lap circuit with a timer and saved best time.

## Play

ES modules need a local static server (opening `index.html` as a file will not load `js/`).

```bash
python3 -m http.server 8080
```

Then open [http://localhost:8080](http://localhost:8080).

Any other static server is fine (`npx serve`, VS Code Live Server, etc.). No build step.

## Controls

| Input | Action |
| --- | --- |
| `W` / `↑` | Accelerate |
| `S` / `↓` | Brake / reverse |
| `A` `D` / `←` `→` | Steer |
| `Enter` / `Space` | Start or race again |
| `R` | Restart the race |
| `Esc` | Back to garage |
| `M` | Mute engine |
| `F` | Fullscreen |

On the garage screen, `A` / `D` or click a card to pick a car.

## Machines

- **NEXUS GT** — balanced street racer
- **RONIN X** — top speed, loose rear
- **VOLT WAGON** — heavy grip
- **SPECTRE** — hard launch out of slow corners

Stay on the wet asphalt. Dirt and the neon rails will cost you time. Cross start/finish after every sector to count a lap. Best time is stored in this browser.

## Stack

Static HTML / CSS / JS. [Three.js](https://threejs.org/) 0.170 from jsDelivr (including bloom). No npm install, no bundler.
