"""Shared constants for the life simulation package."""
import os

SAVE_DIR = os.path.expanduser("~/.life_saves")
SNAPSHOT_DIR = os.path.join(SAVE_DIR, "snapshots")
BLUEPRINT_FILE = os.path.join(SAVE_DIR, "blueprints.json")

CELL_CHAR = "\u2588\u2588"  # Full block × 2 for squarish cells
HEX_CELL = "\u2b22 "       # Hexagon character for hex mode
HEX_DEAD = "\u00b7 "       # Middle dot for empty hex cells

# Hex neighbor offsets for offset-row (even-q) coordinates
# Even rows: neighbors are at these (dr, dc) offsets
HEX_NEIGHBORS_EVEN = [(-1, 0), (-1, 1), (0, -1), (0, 1), (1, 0), (1, 1)]
# Odd rows: neighbors are at these (dr, dc) offsets
HEX_NEIGHBORS_ODD = [(-1, -1), (-1, 0), (0, -1), (0, 1), (1, -1), (1, 0)]

# Zoom levels: 1 = normal (1:1), 2 = zoom out (2×2 → 1 glyph), 4 = (4×4 → 1 glyph), etc.
ZOOM_LEVELS = [1, 2, 4, 8]
# Density glyphs for zoomed-out rendering (maps alive-cell fraction to visual)
DENSITY_CHARS = ["  ", "░░", "▒▒", "▓▓", CELL_CHAR]
DEAD_CHAR = "  "

SPEEDS = [2.0, 1.0, 0.5, 0.25, 0.1, 0.05, 0.02, 0.01]
SPEED_LABELS = ["0.5×", "1×", "2×", "4×", "10×", "20×", "50×", "100×"]

SPARKLINE_CHARS = "▁▂▃▄▅▆▇█"

MP_DEFAULT_PORT = 7654
MP_PLANNING_TIME = 30  # seconds for planning phase
MP_SIM_GENS = 200  # generations per round
