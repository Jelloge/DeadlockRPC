import time
import logging
import threading
from pypresence import Presence, DiscordNotFound, PipeClosed

from steam_utils import install_gsi_config, is_deadlock_running
from src.server import GSIServer
from heroes import lookup_hero, get_game_mode_display

logger = logging.getLogger("deadlock-rpc")

DISCORD_APP_ID = "1474302474474094634"
GSI_PORT = 3000
UPDATE_INTERVAL = 30  # seconds

class DeadlockRPC:
    def __init__(self):
        self.rpc: Presence | None = None
        self.gsi: GSIServer | None = None
        self.connected = False
        self.enabled = True
        self.match_start: float | None = None
        self._running = True
        self._status = "Starting..."
        self._lock = threading.Lock()

    @property
    def status(self) -> str:
        with self._lock: return self._status

    @status.setter
    def status(self, val: str):
        with self._lock: self._status = val

    def connect_discord(self) -> bool:
        if DISCORD_APP_ID == "YOUR_DISCORD_APP_ID_HERE":
            self.status = "⚠ Developer: set DISCORD_APP_ID"
            logger.error("DISCORD_APP_ID not set! Edit the source before building.")
            return False
        try:
            self.rpc = Presence(DISCORD_APP_ID)
            self.rpc.connect()
            self.connected = True
            self.status = "Connected to Discord"
            logger.info("Connected to Discord RPC.")
            return True
        except DiscordNotFound:
            self.status = "Waiting for Discord..."
            return False
        except Exception as e:
            self.status = f"Discord error: {e}"
            return False

    def disconnect_discord(self):
        if self.rpc:
            try:
                self.rpc.clear()
                self.rpc.close()
            except Exception: pass
        self.rpc = None
        self.connected = False

    def start_gsi(self):
        self.gsi = GSIServer(port=GSI_PORT)
        self.gsi.start()

    def _build_presence(self) -> dict:
        kwargs: dict = {}
        state_parts: list[str] = []
        details_parts: list[str] = []

        gsi = self.gsi.state if self.gsi and not self.gsi.state.is_stale else None

        hero_raw = gsi.get_hero_name() if gsi else None
        if hero_raw:
            hero = lookup_hero(hero_raw)
            if hero:
                details_parts.append(f"Playing {hero['name']}")
                kwargs["large_image"] = hero["image"]
                kwargs["large_text"] = hero["name"]
            else:
                details_parts.append(f"Playing {hero_raw}")

        if not details_parts:
            details_parts.append("In Match")

        kda = gsi.get_kda() if gsi else None
        if kda: state_parts.append(f"{kda[0]}/{kda[1]}/{kda[2]} KDA")

        score = gsi.get_team_score() if gsi else None
        if score: state_parts.append(f"Score: {score[0]} - {score[1]}")

        level = gsi.get_player_level() if gsi else None
        if level is not None: state_parts.append(f"Lvl {level}")

        souls = gsi.get_souls() if gsi else None
        if souls is not None: state_parts.append(f"{souls:,} Souls")

        mode = gsi.get_game_mode() if gsi else None
        if mode:
            kwargs["small_image"] = "deadlock_logo"
            kwargs["small_text"] = get_game_mode_display(mode)

        if self.match_start: kwargs["start"] = int(self.match_start)

        kwargs["details"] = " · ".join(details_parts)
        if state_parts: kwargs["state"] = " | ".join(state_parts)

        if "large_image" not in kwargs:
            kwargs["large_image"] = "deadlock_logo"
            kwargs["large_text"] = "Deadlock"

        return kwargs

    def tick(self):
        if not self.enabled: return
        if not self.connected:
            if not self.connect_discord(): return

        game_running = is_deadlock_running()
        if not game_running:
            if self.match_start is not None:
                self.match_start = None
                try: self.rpc.clear()
                except Exception: pass
            self.status = "Waiting for Deadlock..."
            return
            
        gsi = self.gsi.state if self.gsi and not self.gsi.state.is_stale else None
        if gsi:
            phase = gsi.get_game_state()
            if phase and phase.lower() in ("playing", "ingame", "in_progress"):
                if self.match_start is None: self.match_start = time.time()

        if self.match_start is None: self.match_start = time.time()
        kwargs = self._build_presence()

        try:
            self.rpc.update(**kwargs)
            hero_part = kwargs.get("details", "")
            kda_part = kwargs.get("state", "")
            self.status = f"🎮 {hero_part}" + (f" — {kda_part}" if kda_part else "")
        except (PipeClosed, BrokenPipeError):
            self.connected = False
            self.status = "Reconnecting to Discord..."
        except Exception: pass

    def run_loop(self):
        install_gsi_config()
        self.start_gsi()
        self.connect_discord()
        self.status = "Waiting for Deadlock..."
        logger.info("Ready — waiting for Deadlock to launch.")

        while self._running:
            try: self.tick()
            except Exception as e: logger.error("Loop error: %s", e)
            time.sleep(UPDATE_INTERVAL)
        self.disconnect_discord()

    def stop(self):
        self._running = False