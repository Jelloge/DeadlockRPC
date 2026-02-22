## todo: maybe dynamic portrait changes ?
## dynamic reaction portraits based on player low health / killstreak

from __future__ import annotations

import logging
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Callable, Optional

from game_state import GamePhase, GameState, MatchMode

logger = logging.getLogger(__name__)


class LogWatcher:
    def __init__(
        self,
        log_path: str | Path,
        state: GameState,
        patterns: dict[str, str],
        hideout_maps: list[str],
        process_names: list[str],
        resync_max_bytes: int = 100 * 1024,
        map_to_mode: Optional[dict[str, str]] = None,
        on_state_change: Optional[Callable[[GameState], None]] = None,
    ):
        self.log_path = Path(log_path)
        self.state = state
        self.on_state_change = on_state_change
        self.hideout_maps = [m.lower() for m in hideout_maps]
        self.process_names = process_names
        self.resync_max_bytes = resync_max_bytes
        self._stop_flag = False
        self.patterns: dict[str, re.Pattern] = {}

        # map_name -> MatchMode
        self.map_to_mode: dict[str, MatchMode] = {}
        raw_map_to_mode = map_to_mode or {}
        for map_name, mode_name in raw_map_to_mode.items():
            try:
                enum_key = str(mode_name).strip().upper()
                self.map_to_mode[str(map_name).lower()] = MatchMode[enum_key]
            except KeyError:
                logger.warning("Unknown mode '%s' for map '%s' in map_to_mode", mode_name, map_name)

        for name, pattern_str in patterns.items():
            if name.startswith("_"):
                continue
            try:
                self.patterns[name] = re.compile(pattern_str, re.IGNORECASE)
            except re.error as e:
                logger.warning("Invalid regex for '%s': %s — skipping", name, e)

        self._file_handle = None
        self._last_size = 0
        self._bot_init_count = 0
        self._hideout_loaded = False
        self._game_was_running = False

    def is_game_running(self) -> bool:
        """Check if Deadlock is running via tasklist (Windows)."""
        if os.name != "nt":
            try:
                result = subprocess.run(
                    ["pgrep", "-f", "deadlock"],
                    capture_output=True,
                    timeout=3,
                )
                return result.returncode == 0
            except Exception:
                return self.log_path.exists()

        for proc_name in self.process_names:
            try:
                result = subprocess.run(
                    ["tasklist", "/FI", f"IMAGENAME eq {proc_name}", "/NH"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                if proc_name.lower() in result.stdout.lower():
                    return True
            except Exception:
                continue

        return False

    def resync(self) -> None:
        """Read the tail of console.log to sync state to current game state."""
        if not self.log_path.exists():
            return

        try:
            file_size = self.log_path.stat().st_size
            read_start = max(0, file_size - self.resync_max_bytes)

            with open(self.log_path, "r", encoding="utf-8", errors="replace") as f:
                if read_start > 0:
                    f.seek(read_start)
                    f.readline()
                content = f.read()

            lines = content.splitlines()
            logger.info("Resyncing from %d lines (last %d KB)", len(lines), self.resync_max_bytes // 1024)

            for line in lines:
                line = line.strip()
                if line:
                    self._process_line(line)

            self._last_size = file_size
            self._notify()

        except Exception as e:
            logger.error("Resync error: %s", e)

    def _open_log(self) -> bool:
        try:
            if self._file_handle:
                self._file_handle.close()

            if not self.log_path.exists():
                self._file_handle = None
                return False

            self._file_handle = open(self.log_path, "r", encoding="utf-8", errors="replace")
            self._file_handle.seek(0, 2)  # seek to end
            self._last_size = self._file_handle.tell()
            logger.info("Opened console log at byte %d", self._last_size)
            return True

        except OSError as e:
            logger.error("Cannot open log: %s", e)
            self._file_handle = None
            return False

    def _check_file_rotated(self) -> bool:
        try:
            stat = os.stat(self.log_path)
            if stat.st_size < self._last_size:
                return True
            self._last_size = stat.st_size
            return False
        except OSError:
            return True

    def start(self, poll_interval: float = 1.0) -> None:
        """Blocking loop. Run in a thread for non-blocking behavior."""
        logger.info("Watching for %s ...", self.log_path)

        while not self._stop_flag:
            game_running = self.is_game_running()

            if game_running and not self._game_was_running:
                logger.info("Deadlock detected!")
                self._game_was_running = True
                self.state.enter_main_menu()
                self._notify()

                self.resync()
                self._open_log()

            elif not game_running and self._game_was_running:
                logger.info("Deadlock closed.")
                self._game_was_running = False
                self.state.reset()
                self._notify()
                if self._file_handle:
                    self._file_handle.close()
                    self._file_handle = None
                time.sleep(poll_interval * 3)
                continue

            elif not game_running:
                time.sleep(poll_interval * 3)
                continue

            if self._file_handle is None or self._check_file_rotated():
                if not self._open_log():
                    time.sleep(poll_interval)
                    continue
                self.resync()

            new_lines = self._file_handle.readlines()
            if new_lines:
                changed = False
                for line in new_lines:
                    line = line.strip()
                    if line:
                        changed |= self._process_line(line)
                if changed:
                    self._notify()

            time.sleep(poll_interval)

    def _apply_map(self, map_name: str) -> None:
        """Apply map-derived phase/mode updates from any map signal."""
        map_name = map_name.lower().strip()
        if not map_name or map_name == "<empty>":
            return

        self.state.map_name = map_name

        # Map -> mode (only for maps with a known specific mode, e.g. sandbox)
        # dl_midtown is shared by all match types so it maps to UNKNOWN
        mapped_mode = self.map_to_mode.get(map_name)
        if mapped_mode and mapped_mode != MatchMode.UNKNOWN:
            self.state.match_mode = mapped_mode

        # Hideout maps
        if map_name in self.hideout_maps:
            self.state.phase = GamePhase.PARTY_HIDEOUT if self.state.in_party else GamePhase.HIDEOUT
            self._hideout_loaded = True
            self._bot_init_count = 0
            return

        # Any map in map_to_mode counts as a match map
        if map_name in self.map_to_mode:
            self.state.phase = GamePhase.IN_MATCH
            if self.state.match_start_time is None:
                self.state.match_start_time = time.time()
            self._hideout_loaded = False

    def _process_line(self, line: str) -> bool:
        old_phase = self.state.phase
        old_hero = self.state.hero_key
        old_mode = self.state.match_mode
        old_transformed = self.state.is_transformed

        # Map signals (supports both classic map line and "Created physics for <map>")
        if m := self._match("map_info", line):
            self._apply_map(m.group(1))

        elif m := self._match("map_created_physics", line):
            self._apply_map(m.group(1))

        # Matchmaking start
        elif self._match("mm_start", line):
            if self.state.phase in (GamePhase.HIDEOUT, GamePhase.PARTY_HIDEOUT, GamePhase.MAIN_MENU):
                self.state.enter_queue()

        # Matchmaking stop
        elif self._match("mm_stop", line):
            if self.state.phase == GamePhase.IN_QUEUE:
                self.state.leave_queue()

        # If we connect to a real server while queued, stop queue timer
        elif m := self._match("server_connect", line):
            addr = m.group(1)
            self.state.connect_to_server(addr)

            if self.state.phase == GamePhase.IN_QUEUE and "loopback" not in addr.lower():
                self.state.queue_start_time = None

        # Hero loading — local server (hideout / sandbox / bots)
        elif m := self._match("loaded_hero", line):
            hero_norm = m.group(1).lower().replace("hero_", "")

            in_menu_like = self.state.phase in (
                GamePhase.MAIN_MENU,
                GamePhase.HIDEOUT,
                GamePhase.PARTY_HIDEOUT,
            )

            bogus_startup_atlas = (
                in_menu_like and hero_norm == "atlas" and self.state.hero_key is None
            )

            if not bogus_startup_atlas:
                self.state.set_hero(hero_norm)

        # Hero loading — client-side VMDL signal (works in remote matches)
        elif m := self._match("client_hero_vmdl", line):
            hero_norm = m.group(1).lower()
            self.state.set_hero(hero_norm)

        elif self._match("silver_wolf_form_on", line):
            self.state.is_transformed = True

        elif self._match("silver_wolf_form_off", line):
            self.state.is_transformed = False

        # Disconnect / back to menu
        elif m := self._match("server_disconnect", line):
            reason = m.group(1)
            if "EXITING" in reason.upper():
                self.state.reset()
            elif self.state.phase == GamePhase.IN_MATCH:
                self.state.phase = GamePhase.MAIN_MENU
                self.state.hero_key = None
                self.state.match_start_time = None
                self.state.map_name = None
                self.state.match_mode = MatchMode.UNKNOWN
                self.state.bot_difficulty = None

        elif self._match("loop_mode_menu", line):
            if self.state.phase == GamePhase.IN_MATCH:
                self.state.phase = GamePhase.MAIN_MENU
                self.state.hero_key = None
                self.state.match_start_time = None
                self.state.map_name = None
                self.state.match_mode = MatchMode.UNKNOWN
                self.state.bot_difficulty = None

        elif m := self._match("change_game_state", line):
            state_name = m.group(1).lower()
            state_id = int(m.group(2))
            self.state.game_state_id = state_id

            if not self._hideout_loaded:
                if state_name == "matchintro" or state_id == 4:
                    self.state.enter_match_intro()
                elif state_name in ("gameinprogress", "inprogress") or state_id in (7,):
                    self.state.start_match()
                elif state_name == "postgame" or state_id == 6:
                    self.state.end_match()

        # Hideout lobby state
        elif m := self._match("hideout_lobby_state", line):
            lobby_id = int(m.group(2))
            if lobby_id == 0:
                self.state.party_size = 1
            elif lobby_id > 0:
                self.state.set_party_size(max(2, self.state.party_size))

            # Keep hideout phase label in sync with party status
            if self.state.phase in (GamePhase.HIDEOUT, GamePhase.PARTY_HIDEOUT):
                self.state.phase = GamePhase.PARTY_HIDEOUT if self.state.in_party else GamePhase.HIDEOUT

        # Bot mode
        elif m := self._match("bot_init", line):
            difficulty = m.group(1).replace("k_ECitadelBotDifficulty_", "")
            self._bot_init_count += 1
            self.state.bot_difficulty = difficulty
            self.state.match_mode = MatchMode.BOT_MATCH

        # Host activate (map fully loaded)
        elif m := self._match("host_activate", line):
            map_name = m.group(1).lower().strip()
            if map_name in self.hideout_maps:
                self._hideout_loaded = True

        # Server shutdown
        elif m := self._match("server_shutdown", line):
            reason = m.group(1)
            if "EXITING" in reason.upper():
                self.state.reset()

        # App shutdown
        elif self._match("app_shutdown", line) or self._match("source2_shutdown", line):
            self.state.reset()

        # Player info — also infer match mode from player count
        # Standard 6v6: 12 online, 6 co-op bots
        # Street Brawl 4v4: 8 online, 4 co-op bots
        elif m := self._match("player_info", line):
            self.state.player_count = int(m.group(1))
            self.state.bot_count = int(m.group(2))

            count = self.state.player_count
            if count in (6, 12):
                self.state.match_mode = MatchMode.UNRANKED
            elif count in (4, 8):
                self.state.match_mode = MatchMode.STREET_BRAWL

        # (>0 means real match loading)
        elif m := self._match("precaching_heroes", line):
            count = int(m.group(1))
            if count > 0:
                self._hideout_loaded = False

        return (
            self.state.phase != old_phase
            or self.state.hero_key != old_hero
            or self.state.match_mode != old_mode
            or self.state.is_transformed != old_transformed
        )

    def _match(self, pattern_name: str, line: str) -> Optional[re.Match]:
        pattern = self.patterns.get(pattern_name)
        if pattern is None:
            return None
        return pattern.search(line)

    def _notify(self) -> None:
        self.state.last_update = time.time()
        if self.on_state_change:
            try:
                self.on_state_change(self.state)
            except Exception as e:
                logger.error("Callback error: %s", e)

    def stop(self) -> None:
        self._stop_flag = True
        if self._file_handle:
            self._file_handle.close()
            self._file_handle = None