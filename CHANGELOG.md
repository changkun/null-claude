# Changelog

All notable changes to this project are documented in this file.

## 2026-03-15

### Added: Particle Collider / Hadron Collider (Ctrl+Shift+Z)

A CERN-inspired particle physics simulation — beams orbit an elliptical accelerator ring and collide at detector interaction points, producing showers of decay products.

**What it does:**
- Elliptical accelerator ring drawn with box-drawing characters and pulsing energy animation
- Beam particles (clockwise and counter-clockwise) orbiting with trailing dots
- 4 detector interaction points modeled after real LHC experiments (ATLAS, CMS, ALICE, LHCb) with collision flash effects
- Collision showers: 4–25 decay product particles spray outward with physics-based deceleration and lifetime decay
- 12 detectable particles: Higgs boson, W/Z bosons, top/charm quarks, muons, taus, photons, gluons, pions, kaons, B mesons — with measured mass and energy
- 4 presets: LHC Standard (13.6 TeV p-p), Heavy Ion (dense showers), Electron-Positron (clean jets), Discovery Mode (high luminosity/rare particles)
- CERN-aesthetic UI: beam status readout, scrolling detector event log, flash detection banner
- Controls: `Space` (pause), `c` (force collision), `+`/`-` (speed), `r` (reset), `R` (menu), `i` (info overlay), `q` (quit)

**Why:** The project had physics modes (gravity, fluids, electromagnetism) but nothing at the subatomic scale. This adds high-energy particle physics with a fun, educational CERN aesthetic.

**Category:** Physics & Math (~550 lines added to life.py)

### Added: ASCII Aquarium / Fish Tank (Ctrl+Shift+Y)

A relaxing, screensaver-style "zen mode" — the project's first purely ambient simulation.

**What it does:**
- 8 fish species with unique ASCII sprites (Minnow, Guppy, Tetra, Angelfish, Clownfish, Pufferfish, Swordfish, Whale), each with distinct size, speed, and directional art
- 4 presets: Tropical Reef, Deep Ocean, Koi Pond, Goldfish Bowl
- Procedural environment: swaying seaweed, rising bubble streams, surface light ripples, caustic light patterns, sandy bottom with height variation
- Interactive: feed fish (`f`), tap glass to startle (`t`), add/remove fish (`a`/`d`), add bubble streams (`b`), adjust speed (`+`/`-`), toggle info (`i`), pause (`Space`)

**Why:** The project had 60+ modes covering physics, biology, fractals, and chaos — but nothing purely ambient or meditative. This fills the "zen mode" gap.

**Category:** Audio & Visual (~560 lines added to life.py)

## Previous additions (selected)

| Date | Mode | Key |
|------|------|-----|
| — | ASCII Aquarium / Fish Tank | Ctrl+Shift+Y |
| — | Kaleidoscope / Symmetry Patterns | Ctrl+Shift+V |
| — | Ant Farm Simulation | — |
| — | Matrix Digital Rain | — |
| — | Maze Solving Algorithm Visualizer | — |
| — | Lissajous Curve / Harmonograph | — |
| — | Fluid Rope / Honey Coiling | — |
| — | Snowfall & Blizzard | — |
| — | Fourier Epicycle Drawing | — |
| — | DNA Helix & Genetic Algorithm | — |
| — | Sorting Algorithm Visualizer | — |
