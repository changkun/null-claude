# Life Simulator

A terminal-based life simulator built entirely with Python's standard library.
Cellular automata, fluid dynamics, quantum circuits, neural networks, ecology,
and more — all rendered with curses. No external dependencies.

## Quick Start

```bash
uv run life
```

Press `m` to open the mode browser, `?` for help, `q` to quit.

## Requirements

- Python 3.10+
- A terminal with color support (256-color recommended)
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Installation

```bash
git clone https://github.com/changkun/null-claude.git
cd null-claude

# Using uv (recommended)
uv sync

# Or with pip
pip install -e .
```

## Usage

```bash
uv run life                          # Launch (opens dashboard)
uv run life --pattern glider         # Start with a specific pattern
uv run life --rows 100 --cols 200    # Custom grid size
uv run life --no-dashboard           # Skip dashboard, start in Game of Life
uv run life --screensaver            # Demo reel mode (auto-cycles all modes)
uv run life --screensaver-interval 5 # 5 seconds per mode
uv run life --list-patterns          # List all built-in patterns
uv run life --host                   # Host a multiplayer game
uv run life --connect HOST:PORT      # Join a multiplayer game
```

Or without uv:

```bash
python life.py
```

## Simulation Modes

Press `m` at any time to open the mode browser. Modes span:

- **Classic CA** — Game of Life, Wolfram 1D, Langton's Ant, Lenia, Wireworld, Turmites, and more
- **Particle & Swarm** — Boids, Physarum, N-Body gravity, falling sand, DLA
- **Physics & Waves** — Wave equation, Ising model, double pendulum, FDTD, black holes, orrery
- **Fluid Dynamics** — Lattice Boltzmann, Navier-Stokes, SPH, MHD plasma, weather, ocean currents
- **Chemical & Biological** — Reaction-diffusion, epidemics, neural networks, ecosystems, abiogenesis
- **Game Theory & Social** — Prisoner's dilemma, Schelling segregation, stock market, civilization
- **Fractals & Chaos** — Mandelbrot/Julia, strange attractors, L-systems, sandpiles, IFS
- **Procedural & Computational** — WFC, ray marching, sorting visualizer, Tierra, quantum circuits
- **Complex & Audio-Visual** — Galaxy formation, traffic flow, fireworks, music visualizer, aquarium
- **Meta Modes** — Screensaver, mashup, portal, layer compositing, evolution lab, neural CA

For formulations and references, see the **[Scientific Guide](docs/README.md)**.

## Controls

| Key | Action |
|-----|--------|
| `Space` | Play / pause |
| `n` / `.` | Step one generation |
| `+` / `-` | Adjust speed |
| Arrow keys / `hjkl` | Move cursor |
| `e` | Toggle cell |
| `d` / `x` | Draw / erase mode |
| `p` | Pattern library |
| `t` | Stamp pattern at cursor |
| `r` | Randomize grid |
| `c` | Clear grid |
| `R` | Rule editor |
| `i` | Import RLE file |
| `s` / `o` | Save / load state |
| `u` | Undo (rewind one generation) |
| `[` / `]` | Scrub timeline +-10 steps |
| `b` / `B` | Bookmark / bookmark list |
| `H` | Heatmap overlay |
| `I` | 3D isometric view |
| `G` | GIF recording |
| `m` | Mode browser |
| `?` / `h` | Help screen |
| `q` | Quit |

## Project Structure

```
life.py            # Entry point
life/
  app.py           # Core application
  grid.py          # Grid / world management
  colors.py        # Terminal color definitions
  constants.py     # Shared constants
  patterns.py      # Built-in pattern library
  registry.py      # Mode registry and categories
  rules.py         # CA rule engine
  sound.py         # Audio synthesis
  multiplayer.py   # TCP multiplayer
  modes/           # Simulation mode modules
docs/              # Scientific guide
```

## License

[MIT](LICENSE) — Changkun Ou
