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
from logger import LogWatcher
from presence import DiscordRPC
from server_query import query_server

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


def find_tray_icon() -> Path | None:
    """Find the tray icon in the assets folder."""
    assets_dir = SCRIPT_DIR / "assets"
    for name in ["deadlock.ico", "deadlock.png"]:
        p = assets_dir / name
        if p.exists():
            return p
    return None


def create_tray_icon(app: "DeadlockRPC"):
    """Create and run the system tray icon."""
    try:
        import pystray
        from PIL import Image
    except ImportError:
        logger.warning(
            "pystray or Pillow not installed. running without system tray. "
            "Install with: pip install pystray Pillow"
        )
        return None

    icon_path = find_tray_icon()
    if icon_path:
        logger.info("Tray icon: %s", icon_path)
        image = Image.open(icon_path)
    else:
        logger.warning(
            "No icon found in assets/."
        )
        image = Image.new("RGB", (64, 64), color=(139, 92, 246))  # purple square

    def get_status_text():
        phase = app.state.phase.name.replace("_", " ").title()
        hero = app.state.hero_display_name or "None"
        mode = app.state.mode_display() if app.state.is_in_match else "—"
        return f"Phase: {phase}\nHero: {hero}\nMode: {mode}"

    def on_status(icon, item):
        """Show current status as a notification."""
        status = get_status_text()
        try:
            icon.notify(status, "Deadlock RPC Status")
        except Exception:
            logger.info("Status:\n%s", status)

    def on_open_log(icon, item):
        """Open the log file."""
        log_file = LOG_DIR / "deadlock_rpc.log"
        if log_file.exists():
            if platform.system() == "Windows":
                os.startfile(str(log_file))
            elif platform.system() == "Darwin":
                os.system(f'open "{log_file}"')
            else:
                os.system(f'xdg-open "{log_file}"')

    def on_quit(icon, item):
        """Quit the application."""
        logger.info("Quit requested from tray")
        app.running = False
        icon.stop()

    # Build menu
    menu = pystray.Menu(
        pystray.MenuItem("Deadlock RPC", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Show Status", on_status),
        pystray.MenuItem("Open Log", on_open_log),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", on_quit),
    )

    icon = pystray.Icon(
        name="deadlock-rpc",
        icon=image,
        title="Deadlock RPC",
        menu=menu,
    )

    # update tooltip dynamically
    def update_tooltip():
        while app.running:
            try:
                phase = app.state.phase.name.replace("_", " ").title()
                hero = app.state.hero_display_name
                if hero:
                    icon.title = f"Deadlock RPC — {hero} ({phase})"
                else:
                    icon.title = f"Deadlock RPC — {phase}"
            except Exception:
                pass
            time.sleep(5)

    tooltip_thread = threading.Thread(target=update_tooltip, daemon=True, name="tooltip")
    tooltip_thread.start()

    return icon

class DeadlockRPC:

    def __init__(self, config_path: str = "config.json"):
        with open(config_path) as f:
            self.config = json.load(f)

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
            match_maps=self.config.get("match_maps", []),
            hideout_maps=self.config.get("hideout_maps", ["dl_hideout"]),
            process_names=self.config.get("process_names", ["project8.exe", "deadlock.exe"]),
            resync_max_bytes=self.config.get("resync_max_bytes", 100 * 1024),
            on_state_change=self._on_state_change,
        )

        # log watcher thread
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

    # create assets dir if missing
    (SCRIPT_DIR / "assets").mkdir(exist_ok=True)

    app = DeadlockRPC(config_path)

    # start the RPC
    app.start()

    #Create system tray icon, systray or console, because why not. also, good practice ?
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