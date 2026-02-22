from __future__ import annotations
import json
import logging
import os
import platform
import re
import signal
import sys
import threading
import time
from pathlib import Path

from game_state import GamePhase, GameState
from console_log import LogWatcher
from presence import DiscordRPC
from systray import create_tray_icon

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOG_LEVEL = os.environ.get("DEADLOCK_RPC_LOG", "INFO").upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "deadlock_rpc.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("deadlock-rpc")
SCRIPT_DIR = Path(__file__).parent

def find_deadlock_path(config: dict) -> Path | None:
    if config.get("deadlock_install_path"):
        p = Path(config["deadlock_install_path"])
        if p.exists():
            return p

    system = platform.system()
    candidates: list[Path] = []

    if system == "Windows":
        candidates = [
            Path(r"C:\Program Files (x86)\Steam\steamapps\common\Deadlock"),
            Path(r"C:\Program Files\Steam\steamapps\common\Deadlock"),
            Path(r"D:\SteamLibrary\steamapps\common\Deadlock"),
            Path(r"E:\SteamLibrary\steamapps\common\Deadlock"),
        ]
        vdf_path = Path(r"C:\Program Files (x86)\Steam\steamapps\libraryfolders.vdf")
        if vdf_path.exists():
            try:
                text = vdf_path.read_text(errors="replace")
                for m in re.finditer(r'"path"\s+"([^"]+)"', text):
                    candidates.append(Path(m.group(1)) / "steamapps" / "common" / "Deadlock")
            except Exception:
                pass
    elif system == "Linux":
        home = Path.home()
        candidates = [
            home / ".steam/steam/steamapps/common/Deadlock",
            home / ".local/share/Steam/steamapps/common/Deadlock",
        ]

    for c in candidates:
        if c.exists():
            return c
    return None

class DeadlockRPC:

    def __init__(self, config: dict):
        self.config = config

        self.state = GameState()
        self.running = False

        self.deadlock_path = find_deadlock_path(self.config)
        if self.deadlock_path:
            self.console_log_path = (
                self.deadlock_path / self.config.get("console_log_relative_path", "game/citadel/console.log")
            )
            logger.info("Deadlock: %s", self.deadlock_path)
            logger.info("Log: %s", self.console_log_path)
        else:
            logger.warning("Could not find Deadlock. Set deadlock_install_path in config.json.")
            self.console_log_path = None

        self.rpc = DiscordRPC(
            application_id=self.config["discord_application_id"],
            assets_config=self.config.get("discord_assets", {}),
            hero_prefix=self.config.get("hero_asset_prefix", "hero_"),
        )

        self.watcher: LogWatcher | None = None
        self.watcher_thread: threading.Thread | None = None

    def start(self) -> None:
        self.running = True

        logger.info("Connecting to Discord...")
        if not self.rpc.connect():
            logger.error("Could not connect to Discord. Is Discord running?")
            sys.exit(1)
        logger.info("✓ Connected to Discord")

        if not self.console_log_path:
            logger.error("No console log path. Cannot continue.")
            sys.exit(1)

        self.watcher = LogWatcher(
            log_path=self.console_log_path,
            state=self.state,
            patterns=self.config.get("log_patterns", {}),
            map_to_mode=self.config.get("map_to_mode", {}),
            hideout_maps=self.config.get("hideout_maps", ["dl_hideout"]),
            process_names=self.config.get("process_names", ["project8.exe", "deadlock.exe"]),
            resync_max_bytes=self.config.get("resync_max_bytes", 100 * 1024),
            on_state_change=self._on_state_change,
        )

        # log reader
        self.watcher_thread = threading.Thread(
            target=self.watcher.start,
            kwargs={"poll_interval": 1.0},
            daemon=True,
            name="log-watcher",
        )
        self.watcher_thread.start()

        # periodic RPC refresh
        update_interval = self.config.get("update_interval_seconds", 5)
        refresh_thread = threading.Thread(
            target=self._refresh_loop,
            args=(update_interval,),
            daemon=True,
            name="rpc-refresh",
        )
        refresh_thread.start()

    def _refresh_loop(self, interval: float) -> None:
        """Periodic RPC refresh (runs in its own thread)."""
        while self.running:
            try:
                self.rpc.update(self.state)
            except Exception as e:
                logger.error("Refresh error: %s", e)
            time.sleep(interval)

    def stop(self) -> None:
        self.running = False
        if self.watcher:
            self.watcher.stop()
        self.rpc.disconnect()
        logger.info("Stopped.")

    def _on_state_change(self, state: GameState) -> None:
        hero = state.hero_display_name or "—"
        mode = state.mode_display() if state.is_in_match else "—"
        logger.info(
            "%-15s | Hero: %-20s | Mode: %-15s | Map: %s",
            state.phase.name, hero, mode, state.map_name or "—"
        )
        self.rpc.update(state)

def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.json"

    #resolve relative to script directory 
    if not Path(config_path).is_absolute():
        config_path = str(SCRIPT_DIR / config_path)

    if not Path(config_path).exists():
        logger.error("Config not found: %s", config_path)
        sys.exit(1)

    with open(config_path) as f:
        cfg = json.load(f)
    if cfg.get("discord_application_id", "").startswith("YOUR_"):
        logger.error("Set your Discord Application ID in config.json")
        logger.info("Create one at https://discord.com/developers/applications")
        sys.exit(1)

    logger.info("Starting Deadlock Discord Rich Presence...")

    app = DeadlockRPC(cfg)

    # start the RPC
    app.start()

    #Create system tray icon, systray or console
    tray_icon = create_tray_icon(app)

    if tray_icon:
        logger.info("Running in system tray. Right-click the icon to see options.")
        try:
            tray_icon.run()
        except KeyboardInterrupt:
            pass
        finally:
            app.stop()
    else:
        #no tray
        logger.info("Running in console mode. Press Ctrl+C to quit.")

        def handle_signal(sig, frame):
            app.running = False

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        try:
            while app.running:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            app.stop()


if __name__ == "__main__":
    main()