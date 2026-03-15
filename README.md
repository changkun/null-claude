# null-claude

A terminal-based life simulator and simulation sandbox — cellular automata,
fluid dynamics, quantum circuits, neural networks, ecology, and more.
Built entirely with Python's standard library.

## Requirements

- Python 3.10+
- A terminal with color support
- [uv](https://docs.astral.sh/uv/) (recommended) or any Python package manager

## Quick start

```bash
git clone https://github.com/changkun/null-claude.git
cd null-claude
uv run life
```

Or without uv:

```bash
python life.py
```

## Usage

```bash
uv run life                        # Launch the simulator
uv run life --pattern glider       # Start with a specific pattern
uv run life --rows 100 --cols 200  # Custom grid size
uv run life --list-patterns        # List all built-in patterns
uv run python -m life              # Alternative invocation
```

Press `m` in the simulator to open the interactive mode browser,
or `?` for the help screen.

## What's inside

Simulation modes across 10 categories:

| Category | Examples |
|----------|---------|
| Classic CA | Conway's Life, Wolfram 1D, Hexagonal, Wireworld |
| Particle & Swarm | Boids, Particle Life, Physarum, Ant Colony |
| Physics & Waves | Wave Equation, Pendulum, N-Body Gravity, Ising Model |
| Fluid Dynamics | Lattice Boltzmann, Navier-Stokes, SPH, Smoke & Fire |
| Chemical & Biological | Reaction-Diffusion, BZ Reaction, Chemotaxis, SIR Epidemic |
| Game Theory & Social | Prisoner's Dilemma, Schelling Segregation, Rock-Paper-Scissors |
| Fractals & Chaos | Mandelbrot/Julia, Strange Attractors, L-Systems, IFS Fractals |
| Procedural & Computational | Sorting Visualizer, Quantum Circuit, Tierra, WFC |
| Complex Simulations | Ecosystem Evolution, Civilization, Coral Reef, Stock Market |
| Meta Modes | Mashup, Layer Compositing, Portal System, Recording & Export |

All modes run in the terminal using only curses — no GPU, no browser, no external dependencies.

## Project structure

```
life.py            # Convenience entry point
life/              # Main package
  __init__.py      # Package init and main() export
  __main__.py      # python -m life support
  app.py           # Core application class (~330K)
  grid.py          # Grid/world management
  colors.py        # Terminal color definitions
  constants.py     # Shared constants
  patterns.py      # Built-in pattern library
  registry.py      # Mode registry and categories
  rules.py         # CA rule engine
  sound.py         # Audio synthesis
  multiplayer.py   # TCP multiplayer
  utils.py         # Shared utilities
  modes/           # Simulation mode modules
    __init__.py
    boids.py
    fluid_dynamics.py
    quantum_circuit.py
    ...
```

## License

[MIT](LICENSE)
