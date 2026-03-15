"""Grid class for cellular automaton simulation."""
import hashlib

class Grid:
    """Finite grid with wrapping (toroidal) boundaries."""

    # Topology constants
    TOPO_PLANE = "plane"
    TOPO_TORUS = "torus"
    TOPO_KLEIN = "klein_bottle"
    TOPO_MOBIUS = "mobius_strip"
    TOPO_PROJECTIVE = "projective_plane"
    TOPOLOGIES = [TOPO_PLANE, TOPO_TORUS, TOPO_KLEIN, TOPO_MOBIUS, TOPO_PROJECTIVE]

    def __init__(self, rows: int, cols: int):
        self.rows = rows
        self.cols = cols
        # cells[r][c] = 0 means dead; >0 means alive (value = age in gens)
        self.cells = [[0] * cols for _ in range(rows)]
        self.generation = 0
        self.population = 0
        # Birth/survival rules (default: Conway's B3/S23)
        self.birth = {3}
        self.survival = {2, 3}
        # Hex mode: use 6 neighbors instead of 8
        self.hex_mode = False
        # Topology: controls how coordinates wrap at boundaries
        # Default is "torus" which matches the original modulo wrapping
        self.topology = self.TOPO_TORUS

    def set_alive(self, r: int, c: int):
        if 0 <= r < self.rows and 0 <= c < self.cols:
            if self.cells[r][c] == 0:
                self.population += 1
            self.cells[r][c] = max(self.cells[r][c], 1)

    def set_dead(self, r: int, c: int):
        if 0 <= r < self.rows and 0 <= c < self.cols:
            if self.cells[r][c] > 0:
                self.population -= 1
            self.cells[r][c] = 0

    def toggle(self, r: int, c: int):
        if self.cells[r][c]:
            self.set_dead(r, c)
        else:
            self.set_alive(r, c)

    def clear(self):
        self.cells = [[0] * self.cols for _ in range(self.rows)]
        self.generation = 0
        self.population = 0

    def load_pattern(self, name: str, offset_r: int = 0, offset_c: int = 0):
        pattern = PATTERNS.get(name)
        if not pattern:
            return
        for r, c in pattern["cells"]:
            self.set_alive((r + offset_r) % self.rows, (c + offset_c) % self.cols)

    def _wrap(self, r: int, c: int):
        """Map raw (r, c) to grid coordinates based on active topology.

        Returns (nr, nc) or None if the coordinate is off-grid (plane edges).

        Topology summary:
          plane           – no wrapping; cells beyond edges are dead
          torus           – both axes wrap (standard modulo)
          klein_bottle    – columns wrap normally; rows wrap with horizontal flip
          mobius_strip     – columns wrap with vertical flip; rows have hard edges
          projective_plane – both axes wrap with a flip on the opposite axis
        """
        rows, cols = self.rows, self.cols
        topo = self.topology

        if topo == self.TOPO_TORUS:
            return r % rows, c % cols

        if topo == self.TOPO_PLANE:
            if 0 <= r < rows and 0 <= c < cols:
                return r, c
            return None

        if topo == self.TOPO_KLEIN:
            # Columns wrap normally
            nc = c % cols
            # Rows: wrapping flips the column
            if 0 <= r < rows:
                return r, nc
            nr = r % rows
            nc = (cols - 1 - nc) % cols
            return nr, nc

        if topo == self.TOPO_MOBIUS:
            # Rows have hard edges (no wrap)
            if r < 0 or r >= rows:
                return None
            # Columns wrap with vertical flip
            if 0 <= c < cols:
                return r, c
            nc = c % cols
            nr = rows - 1 - r
            return nr, nc

        if topo == self.TOPO_PROJECTIVE:
            # Both axes wrap with a flip on the opposite axis
            nr, nc = r, c
            if nr < 0 or nr >= rows:
                nr = nr % rows
                nc = (cols - 1 - nc) % cols
            if nc < 0 or nc >= cols:
                nc = nc % cols
                nr = (rows - 1 - nr) % rows
            return nr, nc

        # Fallback: torus
        return r % rows, c % cols

    def _count_neighbours(self, r: int, c: int) -> int:
        count = 0
        if self.hex_mode:
            offsets = HEX_NEIGHBORS_EVEN if r % 2 == 0 else HEX_NEIGHBORS_ODD
            for dr, dc in offsets:
                coord = self._wrap(r + dr, c + dc)
                if coord is not None and self.cells[coord[0]][coord[1]]:
                    count += 1
        else:
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    coord = self._wrap(r + dr, c + dc)
                    if coord is not None and self.cells[coord[0]][coord[1]]:
                        count += 1
        return count

    def to_dict(self) -> dict:
        """Serialize grid state to a dictionary."""
        alive_cells = []
        for r in range(self.rows):
            for c in range(self.cols):
                if self.cells[r][c] > 0:
                    alive_cells.append((r, c, self.cells[r][c]))
        return {
            "rows": self.rows,
            "cols": self.cols,
            "generation": self.generation,
            "cells": alive_cells,
            "rule": rule_string(self.birth, self.survival),
        }

    def load_dict(self, data: dict):
        """Restore grid state from a dictionary."""
        self.rows = data["rows"]
        self.cols = data["cols"]
        self.generation = data["generation"]
        self.cells = [[0] * self.cols for _ in range(self.rows)]
        self.population = 0
        for r, c, age in data["cells"]:
            if 0 <= r < self.rows and 0 <= c < self.cols:
                self.cells[r][c] = age
                self.population += 1
        # Restore rule if present in save data
        if "rule" in data:
            parsed = parse_rule_string(data["rule"])
            if parsed:
                self.birth, self.survival = parsed

    def state_hash(self) -> str:
        """Return a hash of the current alive-cell positions for cycle detection."""
        # Build a compact bytes representation of alive cell positions
        alive = []
        for r in range(self.rows):
            for c in range(self.cols):
                if self.cells[r][c] > 0:
                    alive.append(r * self.cols + c)
        data = b"".join(int.to_bytes(v, 4, "little") for v in alive)
        return hashlib.md5(data).hexdigest()

    def step(self):
        """Advance one generation."""
        new = [[0] * self.cols for _ in range(self.rows)]
        pop = 0
        for r in range(self.rows):
            for c in range(self.cols):
                n = self._count_neighbours(r, c)
                alive = self.cells[r][c] > 0
                if alive and n in self.survival:
                    new[r][c] = self.cells[r][c] + 1
                    pop += 1
                elif not alive and n in self.birth:
                    new[r][c] = 1
                    pop += 1
        self.cells = new
        self.generation += 1
        self.population = pop


# ── Sound engine ─────────────────────────────────────────────────────────────

# Pentatonic scale intervals (semitones from root): C D E G A
_PENTATONIC = [0, 2, 4, 7, 9]


