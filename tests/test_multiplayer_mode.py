"""Tests for multiplayer mode — deep validation against commit 7a1baf9."""
import random
import time
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_mock_app
from life.modes.multiplayer_mode import register
from life.grid import Grid
from life.constants import MP_PLANNING_TIME, MP_SIM_GENS


class TestMultiplayerMode:
    def setup_method(self):
        random.seed(42)
        self.app = make_mock_app()
        register(type(self.app))

    # ── Registration ────────────────────────────────────────────────────

    def test_register_binds_all_methods(self):
        """All multiplayer methods must be bound after register()."""
        expected = [
            "_mp_init_owner_grid",
            "_mp_enter_host",
            "_mp_enter_client",
            "_mp_exit",
            "_mp_start_planning",
            "_mp_start_sim",
            "_mp_place_cell",
            "_mp_step",
            "_mp_calc_scores",
            "_mp_finish",
            "_mp_send_state",
            "_mp_recv_state",
            "_mp_poll",
            "_mp_lobby_tick",
            "_mp_planning_tick",
            "_mp_set_ready",
            "_mp_sim_tick",
            "_handle_mp_planning_key",
            "_mp_apply_draw_mode",
            "_handle_mp_running_key",
            "_handle_mp_finished_key",
            "_draw_mp_lobby",
            "_draw_mp_grid",
            "_draw_mp_planning",
            "_draw_mp_game",
            "_draw_mp_finished",
        ]
        for name in expected:
            assert hasattr(self.app, name), f"Missing method: {name}"

    # ── Owner grid init ─────────────────────────────────────────────────

    def test_init_owner_grid(self):
        self.app._mp_init_owner_grid()
        assert len(self.app.mp_owner) == self.app.grid.rows
        assert len(self.app.mp_owner[0]) == self.app.grid.cols
        assert all(c == 0 for row in self.app.mp_owner for c in row)

    # ── Phase transitions ───────────────────────────────────────────────

    def test_start_planning_phase(self):
        """_mp_start_planning should set phase, clear grid, init owner grid."""
        self.app.mp_mode = True
        self.app.mp_player = 1
        self.app.mp_round = 0
        self.app.grid.set_alive(0, 0)
        self.app._mp_start_planning()
        assert self.app.mp_phase == "planning"
        assert self.app.mp_round == 1
        assert self.app.mp_ready == [False, False]
        # Grid should be cleared
        assert self.app.grid.cells[0][0] == 0
        # Owner grid should be initialized
        assert len(self.app.mp_owner) == self.app.grid.rows

    def test_start_planning_centers_cursor_p1(self):
        self.app.mp_player = 1
        self.app._mp_start_planning()
        half = self.app.grid.cols // 2
        assert self.app.cursor_c == half // 2
        assert self.app.cursor_r == self.app.grid.rows // 2

    def test_start_planning_centers_cursor_p2(self):
        self.app.mp_player = 2
        self.app._mp_start_planning()
        half = self.app.grid.cols // 2
        assert self.app.cursor_c == half + half // 2
        assert self.app.cursor_r == self.app.grid.rows // 2

    def test_start_sim_phase(self):
        self.app.mp_mode = True
        self.app.grid.generation = 10
        self.app._mp_start_sim()
        assert self.app.mp_phase == "running"
        assert self.app.mp_start_gen == 10
        assert self.app.mp_scores == [0, 0]
        assert self.app.mp_territory_bonus == [0, 0]
        assert self.app.running is True
        assert self.app.speed_idx == 3  # 4x speed

    def test_finish_phase(self):
        self.app.mp_mode = True
        self.app.mp_phase = "running"
        self.app.mp_player = 1
        self.app.mp_role = "host"
        self.app.mp_net = None  # no network
        self.app._mp_init_owner_grid()
        self.app._mp_finish()
        assert self.app.mp_phase == "finished"
        assert self.app.running is False

    def test_exit_resets_state(self):
        self.app.mp_mode = True
        self.app.mp_phase = "running"
        self.app.mp_role = "host"
        self.app.mp_player = 1
        self.app.mp_net = None
        self.app._mp_exit()
        assert self.app.mp_mode is False
        assert self.app.mp_phase == "idle"
        assert self.app.mp_player == 0
        assert self.app.mp_role is None
        assert self.app.mp_owner == []
        assert self.app.mp_scores == [0, 0]
        assert self.app.mp_round == 0
        assert self.app.mp_ready == [False, False]

    def test_exit_sends_quit_and_stops_net(self):
        mock_net = MagicMock()
        self.app.mp_mode = True
        self.app.mp_net = mock_net
        self.app._mp_exit()
        mock_net.send.assert_called_once_with({"type": "quit"})
        mock_net.stop.assert_called_once()

    # ── Territory / cell placement ──────────────────────────────────────

    def test_place_cell_p1_left_side(self):
        self.app.mp_mode = True
        self.app.mp_player = 1
        self.app.mp_net = None
        self.app._mp_init_owner_grid()
        half = self.app.grid.cols // 2
        self.app._mp_place_cell(5, half - 1, True)
        assert self.app.grid.cells[5][half - 1] > 0
        assert self.app.mp_owner[5][half - 1] == 1

    def test_place_cell_p1_rejected_right_side(self):
        self.app.mp_mode = True
        self.app.mp_player = 1
        self.app.mp_net = None
        self.app._mp_init_owner_grid()
        half = self.app.grid.cols // 2
        self.app._mp_place_cell(5, half, True)
        # Should be rejected — cell stays dead
        assert self.app.grid.cells[5][half] == 0
        assert "LEFT" in self.app.message

    def test_place_cell_p2_right_side(self):
        self.app.mp_mode = True
        self.app.mp_player = 2
        self.app.mp_net = None
        self.app._mp_init_owner_grid()
        half = self.app.grid.cols // 2
        self.app._mp_place_cell(5, half + 1, True)
        assert self.app.grid.cells[5][half + 1] > 0
        assert self.app.mp_owner[5][half + 1] == 2

    def test_place_cell_p2_rejected_left_side(self):
        self.app.mp_mode = True
        self.app.mp_player = 2
        self.app.mp_net = None
        self.app._mp_init_owner_grid()
        self.app._mp_place_cell(5, 0, True)
        assert self.app.grid.cells[5][0] == 0
        assert "RIGHT" in self.app.message

    def test_place_cell_remove(self):
        self.app.mp_mode = True
        self.app.mp_player = 1
        self.app.mp_net = None
        self.app._mp_init_owner_grid()
        self.app._mp_place_cell(5, 3, True)
        assert self.app.grid.cells[5][3] > 0
        self.app._mp_place_cell(5, 3, False)
        assert self.app.grid.cells[5][3] == 0
        assert self.app.mp_owner[5][3] == 0

    def test_place_cell_sends_network_msg(self):
        mock_net = MagicMock()
        self.app.mp_mode = True
        self.app.mp_player = 1
        self.app.mp_net = mock_net
        self.app._mp_init_owner_grid()
        self.app._mp_place_cell(5, 3, True)
        mock_net.send.assert_called_once_with({
            "type": "place", "r": 5, "c": 3, "alive": True, "player": 1
        })

    # ── Simulation step with ownership tracking ─────────────────────────

    def test_mp_step_survival_keeps_owner(self):
        """A surviving cell retains its owner."""
        self.app.mp_mode = True
        self.app.mp_player = 1
        self.app._mp_init_owner_grid()
        # Create a block pattern (stable in B3/S23)
        for r, c in [(5, 5), (5, 6), (6, 5), (6, 6)]:
            self.app.grid.set_alive(r, c)
            self.app.mp_owner[r][c] = 1
        self.app._mp_step()
        # Block is stable — all cells should still be owned by P1
        for r, c in [(5, 5), (5, 6), (6, 5), (6, 6)]:
            assert self.app.grid.cells[r][c] > 0
            assert self.app.mp_owner[r][c] == 1

    def test_mp_step_birth_inherits_majority_owner(self):
        """A new cell inherits ownership from majority of alive neighbors."""
        self.app.mp_mode = True
        self.app._mp_init_owner_grid()
        # Three P1 cells in a row -> birth above/below center
        for c in [10, 11, 12]:
            self.app.grid.set_alive(5, c)
            self.app.mp_owner[5][c] = 1
        self.app._mp_step()
        # New cells born at (4,11) and (6,11) should be owned by P1
        assert self.app.grid.cells[4][11] > 0
        assert self.app.mp_owner[4][11] == 1
        assert self.app.grid.cells[6][11] > 0
        assert self.app.mp_owner[6][11] == 1

    def test_mp_step_contested_birth(self):
        """When birth neighbors are split evenly, owner should be 0 (contested)."""
        self.app.mp_mode = True
        self.app._mp_init_owner_grid()
        # Create an L-shape where a birth cell has equal P1 and P2 neighbors
        # P1 cells at (5,10) and P2 cell at (5,12), empty at (5,11)
        # Need exactly 3 neighbors for birth: put cells in specific config
        # Let's have (4,10)=P1, (4,11)=P2, (5,10)=P1 -> birth at (5,11)
        # neighbors of (5,11): (4,10)=P1, (4,11)=P2, (4,12)=dead
        #                      (5,10)=P1, (5,12)=dead
        #                      (6,10)=dead, (6,11)=dead, (6,12)=dead
        # That's only 3 neighbors -> birth. P1=2, P2=1 -> P1 wins
        # For a true tie: (4,10)=P1, (4,12)=P2, (5,11)=P1 ->
        # Let's just test with equal counts
        self.app.grid.set_alive(4, 10)
        self.app.mp_owner[4][10] = 1
        self.app.grid.set_alive(4, 12)
        self.app.mp_owner[4][12] = 2
        self.app.grid.set_alive(6, 11)
        self.app.mp_owner[6][11] = 0  # neutral
        # Cell at (5,11) has 3 neighbors: (4,10)=P1, (4,12)=P2, (6,11)=neutral
        # P1=1, P2=1 -> tie -> contested (0)
        self.app._mp_step()
        assert self.app.grid.cells[5][11] > 0
        assert self.app.mp_owner[5][11] == 0  # contested

    def test_mp_step_increments_generation(self):
        self.app.mp_mode = True
        self.app._mp_init_owner_grid()
        gen_before = self.app.grid.generation
        self.app._mp_step()
        assert self.app.grid.generation == gen_before + 1

    # ── Scoring logic ───────────────────────────────────────────────────

    def test_calc_scores_basic(self):
        """Score = alive cells per player."""
        self.app.mp_mode = True
        self.app._mp_init_owner_grid()
        half = self.app.grid.cols // 2
        # P1 has 3 cells on left side
        for r in range(3):
            self.app.grid.set_alive(r, 0)
            self.app.mp_owner[r][0] = 1
        # P2 has 5 cells on right side
        for r in range(5):
            self.app.grid.set_alive(r, half + 1)
            self.app.mp_owner[r][half + 1] = 2
        self.app._mp_calc_scores()
        assert self.app.mp_scores == [3, 5]
        assert self.app.mp_territory_bonus == [0, 0]

    def test_calc_scores_territory_bonus(self):
        """Cells in enemy territory earn territory bonus."""
        self.app.mp_mode = True
        self.app._mp_init_owner_grid()
        half = self.app.grid.cols // 2
        # P1 cell in P2's territory (right side)
        self.app.grid.set_alive(0, half + 1)
        self.app.mp_owner[0][half + 1] = 1
        # P2 cell in P1's territory (left side)
        self.app.grid.set_alive(1, 0)
        self.app.mp_owner[1][0] = 2
        # Normal cells
        self.app.grid.set_alive(2, 0)
        self.app.mp_owner[2][0] = 1
        self.app.grid.set_alive(3, half + 2)
        self.app.mp_owner[3][half + 2] = 2
        self.app._mp_calc_scores()
        assert self.app.mp_scores == [2, 2]
        assert self.app.mp_territory_bonus == [1, 1]

    def test_finish_scoring_total_with_territory_double(self):
        """Territory bonus is worth double in final scoring (original: s + b*2)."""
        self.app.mp_mode = True
        self.app.mp_role = "host"
        self.app.mp_net = None
        self.app._mp_init_owner_grid()
        half = self.app.grid.cols // 2
        # P1: 5 cells on home side + 2 in enemy territory
        for r in range(5):
            self.app.grid.set_alive(r, 0)
            self.app.mp_owner[r][0] = 1
        for r in range(2):
            self.app.grid.set_alive(r, half + 1)
            self.app.mp_owner[r][half + 1] = 1
        # P2: 3 cells on home side
        for r in range(3):
            self.app.grid.set_alive(r, half + 5)
            self.app.mp_owner[r][half + 5] = 2
        self.app._mp_finish()
        s1, s2 = self.app.mp_scores
        b1, b2 = self.app.mp_territory_bonus
        assert s1 == 7  # 5 + 2 cells alive
        assert s2 == 3
        assert b1 == 2  # 2 cells in enemy territory
        assert b2 == 0
        total1 = s1 + b1 * 2  # 7 + 4 = 11
        total2 = s2 + b2 * 2  # 3 + 0 = 3
        assert total1 == 11
        assert total2 == 3
        # Verify flash message shows winner
        assert "Player 1" in self.app.message or "P1" in self.app.message

    def test_finish_tie(self):
        self.app.mp_mode = True
        self.app.mp_role = "host"
        self.app.mp_net = None
        self.app._mp_init_owner_grid()
        half = self.app.grid.cols // 2
        # Equal cells, no territory bonus
        self.app.grid.set_alive(0, 0)
        self.app.mp_owner[0][0] = 1
        self.app.grid.set_alive(0, half + 1)
        self.app.mp_owner[0][half + 1] = 2
        self.app._mp_finish()
        assert "TIE" in self.app.message

    def test_finish_host_sends_result(self):
        mock_net = MagicMock()
        self.app.mp_mode = True
        self.app.mp_role = "host"
        self.app.mp_net = mock_net
        self.app._mp_init_owner_grid()
        self.app._mp_finish()
        mock_net.send.assert_called_once()
        msg = mock_net.send.call_args[0][0]
        assert msg["type"] == "finished"
        assert "scores" in msg
        assert "bonus" in msg

    # ── Ready / planning timer ──────────────────────────────────────────

    def test_set_ready(self):
        self.app.mp_mode = True
        self.app.mp_player = 1
        self.app.mp_ready = [False, False]
        self.app.mp_net = MagicMock()
        self.app._mp_set_ready()
        assert self.app.mp_ready[0] is True
        self.app.mp_net.send.assert_called_once_with({"type": "ready"})

    def test_set_ready_both_starts_sim(self):
        self.app.mp_mode = True
        self.app.mp_player = 1
        self.app.mp_role = "host"
        self.app.mp_ready = [False, True]  # opponent already ready
        mock_net = MagicMock()
        self.app.mp_net = mock_net
        self.app.grid.generation = 5
        self.app._mp_set_ready()
        assert self.app.mp_ready == [True, True]
        assert self.app.mp_phase == "running"
        # Host should send start_sim
        calls = [c[0][0] for c in mock_net.send.call_args_list]
        types = [c["type"] for c in calls]
        assert "ready" in types
        assert "start_sim" in types

    def test_planning_tick_auto_ready_when_expired(self):
        self.app.mp_mode = True
        self.app.mp_player = 1
        self.app.mp_ready = [False, False]
        self.app.mp_net = MagicMock()
        # Deadline in the past
        self.app.mp_planning_deadline = time.monotonic() - 1.0
        self.app._mp_planning_tick()
        assert self.app.mp_ready[0] is True

    def test_planning_tick_no_auto_ready_when_time_left(self):
        self.app.mp_mode = True
        self.app.mp_player = 1
        self.app.mp_ready = [False, False]
        self.app.mp_planning_deadline = time.monotonic() + 100.0
        self.app._mp_planning_tick()
        assert self.app.mp_ready[0] is False

    # ── Network polling ─────────────────────────────────────────────────

    def test_poll_quit_message(self):
        mock_net = MagicMock()
        mock_net.poll.return_value = [{"type": "quit"}]
        mock_net.connected = True
        self.app.mp_mode = True
        self.app.mp_phase = "running"
        self.app.mp_net = mock_net
        self.app._mp_poll()
        # Should have exited multiplayer
        assert self.app.mp_mode is False

    def test_poll_place_message(self):
        mock_net = MagicMock()
        mock_net.poll.return_value = [
            {"type": "place", "r": 3, "c": 4, "alive": True, "player": 2}
        ]
        mock_net.connected = True
        self.app.mp_mode = True
        self.app.mp_phase = "planning"
        self.app.mp_net = mock_net
        self.app._mp_init_owner_grid()
        self.app._mp_poll()
        assert self.app.grid.cells[3][4] > 0
        assert self.app.mp_owner[3][4] == 2

    def test_poll_ready_message(self):
        mock_net = MagicMock()
        mock_net.poll.return_value = [{"type": "ready"}]
        mock_net.connected = True
        self.app.mp_mode = True
        self.app.mp_phase = "planning"
        self.app.mp_player = 1
        self.app.mp_ready = [False, False]
        self.app.mp_net = mock_net
        self.app._mp_init_owner_grid()
        self.app._mp_poll()
        assert self.app.mp_ready[1] is True  # peer = P2
        assert "Opponent is ready" in self.app.message

    def test_poll_start_sim_message(self):
        mock_net = MagicMock()
        mock_net.poll.return_value = [{"type": "start_sim"}]
        mock_net.connected = True
        self.app.mp_mode = True
        self.app.mp_phase = "planning"
        self.app.mp_player = 2
        self.app.mp_net = mock_net
        self.app._mp_init_owner_grid()
        self.app._mp_poll()
        assert self.app.mp_phase == "running"

    def test_poll_state_message(self):
        mock_net = MagicMock()
        mock_net.poll.return_value = [{
            "type": "state",
            "gen": 42,
            "cells": [[3, 4, 2, 1], [5, 6, 1, 2]],
            "scores": [10, 8],
            "bonus": [3, 1],
        }]
        mock_net.connected = True
        self.app.mp_mode = True
        self.app.mp_phase = "running"
        self.app.mp_net = mock_net
        self.app._mp_init_owner_grid()
        self.app._mp_poll()
        assert self.app.grid.generation == 42
        assert self.app.grid.cells[3][4] == 2
        assert self.app.mp_owner[3][4] == 1
        assert self.app.grid.cells[5][6] == 1
        assert self.app.mp_owner[5][6] == 2
        assert self.app.mp_scores == [10, 8]
        assert self.app.mp_territory_bonus == [3, 1]

    def test_poll_finished_message(self):
        mock_net = MagicMock()
        mock_net.poll.return_value = [{
            "type": "finished",
            "scores": [20, 15],
            "bonus": [5, 2],
        }]
        mock_net.connected = True
        self.app.mp_mode = True
        self.app.mp_phase = "running"
        self.app.mp_net = mock_net
        self.app._mp_poll()
        assert self.app.mp_phase == "finished"
        assert self.app.running is False
        assert self.app.mp_scores == [20, 15]
        assert self.app.mp_territory_bonus == [5, 2]

    def test_poll_hello_resizes_grid(self):
        mock_net = MagicMock()
        mock_net.poll.return_value = [{
            "type": "hello",
            "rows": 50,
            "cols": 80,
            "max_gens": 300,
        }]
        mock_net.connected = True
        self.app.mp_mode = True
        self.app.mp_phase = "lobby"
        self.app.mp_net = mock_net
        self.app._mp_poll()
        assert self.app.grid.rows == 50
        assert self.app.grid.cols == 80
        assert self.app.mp_sim_gens == 300

    def test_poll_disconnection_triggers_exit(self):
        mock_net = MagicMock()
        mock_net.poll.return_value = []
        mock_net.connected = False
        self.app.mp_mode = True
        self.app.mp_phase = "running"
        self.app.mp_net = mock_net
        self.app._mp_poll()
        assert self.app.mp_mode is False

    def test_poll_disconnection_ignored_in_lobby(self):
        mock_net = MagicMock()
        mock_net.poll.return_value = []
        mock_net.connected = False
        self.app.mp_mode = True
        self.app.mp_phase = "lobby"
        self.app.mp_net = mock_net
        self.app._mp_poll()
        # Should NOT exit in lobby (host waits for connection)
        assert self.app.mp_mode is True

    def test_poll_start_planning_message(self):
        mock_net = MagicMock()
        mock_net.poll.return_value = [{"type": "start_planning"}]
        mock_net.connected = True
        self.app.mp_mode = True
        self.app.mp_phase = "lobby"
        self.app.mp_player = 2
        self.app.mp_net = mock_net
        self.app._mp_poll()
        assert self.app.mp_phase == "planning"

    # ── Send/recv state ─────────────────────────────────────────────────

    def test_send_state_host_only(self):
        mock_net = MagicMock()
        self.app.mp_mode = True
        self.app.mp_role = "client"
        self.app.mp_net = mock_net
        self.app._mp_init_owner_grid()
        self.app._mp_send_state()
        mock_net.send.assert_not_called()

    def test_send_state_includes_cells(self):
        mock_net = MagicMock()
        self.app.mp_mode = True
        self.app.mp_role = "host"
        self.app.mp_net = mock_net
        self.app._mp_init_owner_grid()
        self.app.grid.set_alive(2, 3)
        self.app.mp_owner[2][3] = 1
        self.app._mp_send_state()
        msg = mock_net.send.call_args[0][0]
        assert msg["type"] == "state"
        assert len(msg["cells"]) == 1
        assert msg["cells"][0] == (2, 3, 1, 1)

    def test_recv_state_applies_correctly(self):
        self.app.mp_mode = True
        self.app._mp_init_owner_grid()
        msg = {
            "gen": 100,
            "cells": [[1, 2, 5, 2], [3, 4, 1, 1]],
            "scores": [10, 15],
            "bonus": [2, 3],
        }
        self.app._mp_recv_state(msg)
        assert self.app.grid.generation == 100
        assert self.app.grid.cells[1][2] == 5
        assert self.app.mp_owner[1][2] == 2
        assert self.app.grid.cells[3][4] == 1
        assert self.app.mp_owner[3][4] == 1
        assert self.app.grid.population == 2
        assert self.app.mp_scores == [10, 15]
        assert self.app.mp_territory_bonus == [2, 3]

    # ── Lobby tick ──────────────────────────────────────────────────────

    def test_lobby_tick_host_connected_starts_planning(self):
        mock_net = MagicMock()
        mock_net.connected = True
        self.app.mp_mode = True
        self.app.mp_role = "host"
        self.app.mp_net = mock_net
        self.app.mp_phase = "lobby"
        self.app.mp_player = 1
        self.app._mp_lobby_tick()
        assert self.app.mp_phase == "planning"
        # Should have sent hello and start_planning
        calls = [c[0][0] for c in mock_net.send.call_args_list]
        types = [c["type"] for c in calls]
        assert "hello" in types
        assert "start_planning" in types

    def test_lobby_tick_client_waits(self):
        mock_net = MagicMock()
        mock_net.connected = True
        self.app.mp_mode = True
        self.app.mp_role = "client"
        self.app.mp_net = mock_net
        self.app.mp_phase = "lobby"
        self.app._mp_lobby_tick()
        # Client just waits — no sends
        mock_net.send.assert_not_called()

    # ── Sim tick ────────────────────────────────────────────────────────

    def test_sim_tick_host_runs_step(self):
        mock_net = MagicMock()
        self.app.mp_mode = True
        self.app.mp_role = "host"
        self.app.mp_phase = "running"
        self.app.mp_net = mock_net
        self.app.mp_start_gen = 0
        self.app.mp_sim_gens = MP_SIM_GENS
        self.app._mp_init_owner_grid()
        gen_before = self.app.grid.generation
        self.app._mp_sim_tick()
        assert self.app.grid.generation == gen_before + 1

    def test_sim_tick_client_does_nothing(self):
        self.app.mp_mode = True
        self.app.mp_role = "client"
        self.app.mp_phase = "running"
        self.app._mp_init_owner_grid()
        gen_before = self.app.grid.generation
        self.app._mp_sim_tick()
        assert self.app.grid.generation == gen_before  # unchanged

    def test_sim_tick_broadcasts_every_3_gens(self):
        mock_net = MagicMock()
        self.app.mp_mode = True
        self.app.mp_role = "host"
        self.app.mp_net = mock_net
        self.app.mp_start_gen = 0
        self.app.mp_sim_gens = 1000
        self.app._mp_init_owner_grid()
        # Run 6 ticks and check broadcasts
        for _ in range(6):
            mock_net.reset_mock()
            self.app._mp_sim_tick()
            gen = self.app.grid.generation
            if gen % 3 == 0:
                assert mock_net.send.called, f"Expected broadcast at gen {gen}"
            else:
                assert not mock_net.send.called, f"Unexpected broadcast at gen {gen}"

    def test_sim_tick_finishes_after_sim_gens(self):
        mock_net = MagicMock()
        self.app.mp_mode = True
        self.app.mp_role = "host"
        self.app.mp_net = mock_net
        self.app.mp_start_gen = 0
        self.app.mp_sim_gens = 5
        self.app._mp_init_owner_grid()
        for _ in range(5):
            self.app._mp_sim_tick()
        assert self.app.mp_phase == "finished"

    # ── Key handlers ────────────────────────────────────────────────────

    def test_planning_key_quit(self):
        self.app.mp_mode = True
        self.app.mp_phase = "planning"
        self.app.mp_net = None
        ret = self.app._handle_mp_planning_key(ord("q"))
        assert ret is True
        assert self.app.mp_mode is False

    def test_planning_key_movement(self):
        self.app.mp_mode = True
        self.app.mp_phase = "planning"
        self.app._mp_init_owner_grid()
        self.app.cursor_r = 5
        self.app.cursor_c = 5
        self.app._handle_mp_planning_key(ord("k"))  # up
        assert self.app.cursor_r == 4
        self.app._handle_mp_planning_key(ord("j"))  # down
        assert self.app.cursor_r == 5
        self.app._handle_mp_planning_key(ord("h"))  # left
        assert self.app.cursor_c == 4
        self.app._handle_mp_planning_key(ord("l"))  # right
        assert self.app.cursor_c == 5

    def test_planning_key_toggle_cell(self):
        self.app.mp_mode = True
        self.app.mp_player = 1
        self.app.mp_phase = "planning"
        self.app.mp_net = None
        self.app._mp_init_owner_grid()
        self.app.cursor_r = 5
        self.app.cursor_c = 3
        self.app._handle_mp_planning_key(ord(" "))
        assert self.app.grid.cells[5][3] > 0

    def test_planning_key_ready(self):
        self.app.mp_mode = True
        self.app.mp_player = 1
        self.app.mp_phase = "planning"
        self.app.mp_ready = [False, False]
        self.app.mp_net = MagicMock()
        self.app._handle_mp_planning_key(10)  # Enter
        assert self.app.mp_ready[0] is True

    def test_planning_key_random_fill(self):
        self.app.mp_mode = True
        self.app.mp_player = 1
        self.app.mp_phase = "planning"
        self.app.mp_net = None
        self.app._mp_init_owner_grid()
        self.app._handle_mp_planning_key(ord("r"))
        # Should have some cells on left half
        half = self.app.grid.cols // 2
        left_count = sum(
            1 for r in range(self.app.grid.rows)
            for c in range(0, half)
            if self.app.grid.cells[r][c] > 0
        )
        assert left_count > 0
        assert "Random fill" in self.app.message

    def test_planning_key_clear(self):
        self.app.mp_mode = True
        self.app.mp_player = 1
        self.app.mp_phase = "planning"
        self.app.mp_net = None
        self.app._mp_init_owner_grid()
        # Place some cells first
        half = self.app.grid.cols // 2
        for c in range(half):
            self.app.grid.set_alive(0, c)
            self.app.mp_owner[0][c] = 1
        self.app._handle_mp_planning_key(ord("c"))
        # All left side should be cleared
        for c in range(half):
            assert self.app.grid.cells[0][c] == 0
        assert "Cleared" in self.app.message

    def test_planning_key_noop(self):
        """Key -1 should be a no-op."""
        self.app.mp_mode = True
        self.app.mp_phase = "planning"
        ret = self.app._handle_mp_planning_key(-1)
        assert ret is True

    def test_running_key_pause_toggle(self):
        self.app.mp_mode = True
        self.app.mp_phase = "running"
        self.app.running = True
        self.app._handle_mp_running_key(ord(" "))
        assert self.app.running is False
        self.app._handle_mp_running_key(ord(" "))
        assert self.app.running is True

    def test_running_key_speed_up_down(self):
        self.app.mp_mode = True
        self.app.mp_phase = "running"
        self.app.speed_idx = 3
        self.app._handle_mp_running_key(ord("+"))
        assert self.app.speed_idx == 4
        self.app._handle_mp_running_key(ord("-"))
        assert self.app.speed_idx == 3

    def test_running_key_quit(self):
        self.app.mp_mode = True
        self.app.mp_phase = "running"
        self.app.mp_net = None
        self.app._handle_mp_running_key(ord("q"))
        assert self.app.mp_mode is False

    def test_finished_key_quit(self):
        self.app.mp_mode = True
        self.app.mp_phase = "finished"
        self.app.mp_net = None
        self.app._handle_mp_finished_key(ord("q"))
        assert self.app.mp_mode is False

    def test_finished_key_esc(self):
        self.app.mp_mode = True
        self.app.mp_phase = "finished"
        self.app.mp_net = None
        self.app._handle_mp_finished_key(27)
        assert self.app.mp_mode is False

    def test_finished_key_enter_host_restarts(self):
        mock_net = MagicMock()
        self.app.mp_mode = True
        self.app.mp_phase = "finished"
        self.app.mp_role = "host"
        self.app.mp_player = 1
        self.app.mp_net = mock_net
        self.app._handle_mp_finished_key(10)  # Enter
        assert self.app.mp_phase == "planning"
        calls = [c[0][0] for c in mock_net.send.call_args_list]
        types = [c["type"] for c in calls]
        assert "start_planning" in types

    def test_finished_key_enter_client_waits(self):
        mock_net = MagicMock()
        self.app.mp_mode = True
        self.app.mp_phase = "finished"
        self.app.mp_role = "client"
        self.app.mp_net = mock_net
        self.app._handle_mp_finished_key(10)
        # Client can't restart, just flash
        assert "Waiting" in self.app.message
        assert self.app.mp_phase == "finished"

    # ── Draw mode during planning ───────────────────────────────────────

    def test_draw_mode_toggle(self):
        self.app.mp_mode = True
        self.app.mp_player = 1
        self.app.mp_phase = "planning"
        self.app.mp_net = None
        self.app._mp_init_owner_grid()
        self.app.cursor_r = 5
        self.app.cursor_c = 3
        self.app._handle_mp_planning_key(ord("d"))
        assert self.app.draw_mode == "draw"
        self.app._handle_mp_planning_key(ord("d"))
        assert self.app.draw_mode is None

    def test_erase_mode_toggle(self):
        self.app.mp_mode = True
        self.app.mp_player = 1
        self.app.mp_phase = "planning"
        self.app.mp_net = None
        self.app._mp_init_owner_grid()
        self.app.cursor_r = 5
        self.app.cursor_c = 3
        self.app._handle_mp_planning_key(ord("x"))
        assert self.app.draw_mode == "erase"
        self.app._handle_mp_planning_key(ord("x"))
        assert self.app.draw_mode is None

    def test_esc_cancels_draw_mode(self):
        self.app.mp_mode = True
        self.app.draw_mode = "draw"
        self.app._handle_mp_planning_key(27)
        assert self.app.draw_mode is None

    def test_apply_draw_mode_respects_territory(self):
        self.app.mp_mode = True
        self.app.mp_player = 1
        self.app.mp_phase = "planning"
        self.app.mp_ready = [False, False]
        self.app.mp_net = None
        self.app._mp_init_owner_grid()
        self.app.draw_mode = "draw"
        half = self.app.grid.cols // 2
        # In territory — should place
        self.app.cursor_r = 5
        self.app.cursor_c = 3
        self.app._mp_apply_draw_mode()
        assert self.app.grid.cells[5][3] > 0
        # Out of territory — should NOT place
        self.app.cursor_c = half + 1
        self.app._mp_apply_draw_mode()
        assert self.app.grid.cells[5][half + 1] == 0

    def test_apply_draw_mode_noop_when_ready(self):
        self.app.mp_mode = True
        self.app.mp_player = 1
        self.app.mp_phase = "planning"
        self.app.mp_ready = [True, False]
        self.app.mp_net = None
        self.app._mp_init_owner_grid()
        self.app.draw_mode = "draw"
        self.app.cursor_r = 5
        self.app.cursor_c = 3
        self.app._mp_apply_draw_mode()
        assert self.app.grid.cells[5][3] == 0  # nothing placed

    def test_apply_draw_mode_noop_outside_planning(self):
        self.app.mp_mode = True
        self.app.mp_phase = "running"
        self.app.draw_mode = "draw"
        self.app._mp_init_owner_grid()
        self.app.cursor_r = 5
        self.app.cursor_c = 3
        self.app._mp_apply_draw_mode()
        assert self.app.grid.cells[5][3] == 0

    # ── Enter host/client (prompt interaction) ──────────────────────────

    def test_enter_host_exit_toggle(self):
        """If already in mp_mode, entering host again should exit."""
        self.app.mp_mode = True
        self.app.mp_net = None
        self.app._mp_enter_host()
        assert self.app.mp_mode is False

    def test_enter_client_exit_toggle(self):
        """If already in mp_mode, entering client again should exit."""
        self.app.mp_mode = True
        self.app.mp_net = None
        self.app._mp_enter_client()
        assert self.app.mp_mode is False

    def test_enter_host_cancelled_prompt(self):
        """When _prompt_text returns None, should do nothing."""
        self.app.mp_mode = False
        # _prompt_text returns None by default in mock
        self.app._mp_enter_host()
        assert self.app.mp_mode is False

    def test_enter_client_empty_addr(self):
        """When _prompt_text returns empty string, should do nothing."""
        self.app.mp_mode = False
        self.app._prompt_text = lambda p: ""
        self.app._mp_enter_client()
        assert self.app.mp_mode is False

    # ── Full round integration ──────────────────────────────────────────

    def test_full_round_lifecycle(self):
        """Simulate a complete round: planning -> running -> finished."""
        self.app.mp_mode = True
        self.app.mp_role = "host"
        self.app.mp_player = 1
        self.app.mp_net = None
        self.app.mp_sim_gens = 10

        # Planning phase
        self.app._mp_start_planning()
        assert self.app.mp_phase == "planning"

        # Place some cells
        for c in range(5):
            self.app._mp_place_cell(10, c, True)

        # Start sim
        self.app._mp_start_sim()
        assert self.app.mp_phase == "running"

        # Run all generations
        for _ in range(10):
            self.app._mp_sim_tick()

        assert self.app.mp_phase == "finished"
        assert self.app.running is False
