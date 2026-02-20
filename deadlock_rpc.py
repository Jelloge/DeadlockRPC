#!/usr/bin/env python3
"""
Deadlock Discord Rich Presence — System Tray Application

Download, run, and forget. Shows your live Deadlock match info on Discord.
Sits quietly in the system tray and does everything automatically.
"""

import ctypes
import json
import logging
import os
import platform
import shutil
import sys
import threading
import time
from pathlib import Path

import psutil

try:
    from pypresence import Presence, DiscordNotFound, PipeClosed
except ImportError:
    sys.exit("pypresence not installed. Run: pip install pypresence")

try:
    import pystray
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    sys.exit("pystray/Pillow not installed. Run: pip install pystray Pillow")

from heroes import lookup_hero, get_game_mode_display
from gsi_server import GSIServer

# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIGURATION — The only thing YOU (the developer) need to set up once.
#
#  1. Go to https://discord.com/developers/applications
#  2. Create a new application named "Deadlock"
#  3. Paste the Application ID below
#  4. Go to Rich Presence > Art Assets and upload:
#       - "deadlock_icon"    → Deadlock game icon (fallback when no hero selected)
#       - "hero_abrams"      → Abrams portrait
#       - "hero_haze"        → Haze portrait
#       - ... (see heroes.py for the full asset key list)
#  5. Build the exe with: pyinstaller deadlock_rpc.spec
#  6. Distribute the exe. Users just run it — zero setup.
# ═══════════════════════════════════════════════════════════════════════════════

DISCORD_APP_ID = "YOUR_DISCORD_APP_ID_HERE"  # ← REPLACE THIS BEFORE BUILDING

# ─── Constants ─────────────────────────────────────────────────────────────────

APP_NAME = "Deadlock Rich Presence"
VERSION = "1.0.0"
DEADLOCK_STEAM_ID = 1422450
GSI_PORT = 3000
UPDATE_INTERVAL = 15  # seconds

DEADLOCK_PROCESS_NAMES = {
    "project8.exe", "deadlock.exe", "citadel.exe",
    "project8", "deadlock", "citadel",
}

GSI_CFG_CONTENT = '''"Deadlock Discord RPC"
{
    "uri"           "http://127.0.0.1:3000/"
    "timeout"       "5.0"
    "buffer"        "0.1"
    "throttle"      "0.5"
    "heartbeat"     "30.0"
    "data"
    {
        "provider"      "1"
        "map"           "1"
        "player"        "1"
        "hero"          "1"
        "abilities"     "1"
        "items"         "1"
        "allplayers"    "1"
    }
    "auth"
    {
        "token"     "deadlock_discord_rpc_token"
    }
}
'''

# ─── Logging ───────────────────────────────────────────────────────────────────

LOG_DIR = Path.home() / ".deadlock-rpc"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_DIR / "deadlock_rpc.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("deadlock-rpc")


# ═══════════════════════════════════════════════════════════════════════════════
#  AUTO-SETUP: Find Deadlock & install GSI config
# ═══════════════════════════════════════════════════════════════════════════════

def find_steam_path() -> Path | None:
    """Locate the Steam installation directory."""
    system = platform.system()

    if system == "Windows":
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
            steam_path, _ = winreg.QueryValueEx(key, "SteamPath")
            winreg.CloseKey(key)
            return Path(steam_path)
        except Exception:
            pass
        # Fallback paths
        for p in [
            Path(r"C:\Program Files (x86)\Steam"),
            Path(r"C:\Program Files\Steam"),
            Path(r"D:\Steam"),
            Path(r"D:\SteamLibrary"),
        ]:
            if p.exists():
                return p

    elif system == "Linux":
        for p in [
            Path.home() / ".steam" / "steam",
            Path.home() / ".local" / "share" / "Steam",
        ]:
            if p.exists():
                return p

    elif system == "Darwin":
        p = Path.home() / "Library" / "Application Support" / "Steam"
        if p.exists():
            return p

    return None


def find_steam_library_folders(steam_path: Path) -> list[Path]:
    """Parse libraryfolders.vdf to find all Steam library locations."""
    folders = [steam_path]
    vdf_path = steam_path / "steamapps" / "libraryfolders.vdf"
    if not vdf_path.exists():
        # Try alternate location
        vdf_path = steam_path / "config" / "libraryfolders.vdf"

    if vdf_path.exists():
        try:
            text = vdf_path.read_text(encoding="utf-8", errors="ignore")
            # Simple VDF parser — look for "path" entries
            import re
            for match in re.finditer(r'"path"\s+"([^"]+)"', text):
                p = Path(match.group(1))
                if p.exists() and p not in folders:
                    folders.append(p)
        except Exception:
            pass

    return folders


def find_deadlock_install() -> Path | None:
    """Find the Deadlock game installation directory."""
    steam_path = find_steam_path()
    if not steam_path:
        return None

    libraries = find_steam_library_folders(steam_path)

    for lib in libraries:
        # Deadlock's internal name is "Deadlock" but folder could vary
        for name in ["Deadlock", "deadlock"]:
            game_dir = lib / "steamapps" / "common" / name
            if game_dir.exists():
                return game_dir

    return None


def install_gsi_config() -> bool:
    """Auto-install the GSI config file into Deadlock's directory."""
    game_dir = find_deadlock_install()
    if not game_dir:
        logger.warning("Could not find Deadlock installation — GSI auto-install skipped.")
        logger.info("You can manually place the GSI config. See README for details.")
        return False

    # Deadlock uses Source 2 — cfg path is game/citadel/cfg/gamestate_integration/
    gsi_dir = game_dir / "game" / "citadel" / "cfg" / "gamestate_integration"

    try:
        gsi_dir.mkdir(parents=True, exist_ok=True)
        cfg_path = gsi_dir / "gamestate_integration_discord_rpc.cfg"

        # Only write if it doesn't exist or content differs
        if cfg_path.exists():
            existing = cfg_path.read_text(encoding="utf-8", errors="ignore")
            if existing.strip() == GSI_CFG_CONTENT.strip():
                logger.info("GSI config already installed at %s", cfg_path)
                return True

        cfg_path.write_text(GSI_CFG_CONTENT, encoding="utf-8")
        logger.info("GSI config installed to %s", cfg_path)
        return True

    except PermissionError:
        logger.error("Permission denied writing GSI config to %s", gsi_dir)
        return False
    except Exception as e:
        logger.error("Failed to install GSI config: %s", e)
        return False


# ═══════════════════════════════════════════════════════════════════════════════
#  PROCESS DETECTION
# ═══════════════════════════════════════════════════════════════════════════════

def is_deadlock_running() -> bool:
    for proc in psutil.process_iter(["name"]):
        try:
            name = proc.info.get("name", "")
            if name and name.lower() in DEADLOCK_PROCESS_NAMES:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False


# ═══════════════════════════════════════════════════════════════════════════════
#  TRAY ICON
# ═══════════════════════════════════════════════════════════════════════════════

def create_tray_icon_image() -> Image.Image:
    """
    Generate a simple Deadlock-themed tray icon.
    If you have a proper .ico, place it at assets/icon.ico or assets/icon.png
    and this will load it instead.
    """
    # Try to load a custom icon from bundled assets
    for icon_name in ["icon.ico", "icon.png"]:
        for search_dir in [
            Path(__file__).parent / "assets",
            Path(getattr(sys, "_MEIPASS", "")) / "assets",  # PyInstaller bundle
            LOG_DIR / "assets",
        ]:
            icon_path = search_dir / icon_name
            if icon_path.exists():
                try:
                    return Image.open(icon_path).resize((64, 64))
                except Exception:
                    pass

    # Fallback: generate a simple icon programmatically
    # Dark circle with "DL" text — recognisable in the tray
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Dark background circle
    draw.ellipse([2, 2, size - 2, size - 2], fill=(30, 30, 35, 255))

    # Amber/gold ring (Deadlock's colour palette)
    draw.ellipse([2, 2, size - 2, size - 2], outline=(218, 165, 32, 255), width=3)

    # "DL" text in the centre
    try:
        font = ImageFont.truetype("arial.ttf", 22)
    except OSError:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
        except OSError:
            font = ImageFont.load_default()

    text = "DL"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size - tw) // 2
    y = (size - th) // 2 - 2
    draw.text((x, y), text, fill=(218, 165, 32, 255), font=font)

    return img


# ═══════════════════════════════════════════════════════════════════════════════
#  DISCORD RPC ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class DeadlockRPC:
    """Core engine that ties GSI, process detection, and Discord together."""

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
        with self._lock:
            return self._status

    @status.setter
    def status(self, val: str):
        with self._lock:
            self._status = val

    # ── Discord connection ─────────────────────────────────────────────

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
            logger.warning("Discord not running — will retry.")
            return False
        except Exception as e:
            self.status = f"Discord error: {e}"
            logger.error("Discord connection failed: %s", e)
            return False

    def disconnect_discord(self):
        if self.rpc:
            try:
                self.rpc.clear()
                self.rpc.close()
            except Exception:
                pass
        self.rpc = None
        self.connected = False

    # ── GSI ─────────────────────────────────────────────────────────────

    def start_gsi(self):
        self.gsi = GSIServer(port=GSI_PORT)
        self.gsi.start()

    # ── Presence building ──────────────────────────────────────────────

    def _build_presence(self) -> dict:
        """Build RPC kwargs from all available data."""
        kwargs: dict = {}
        state_parts: list[str] = []
        details_parts: list[str] = []

        gsi = self.gsi.state if self.gsi and not self.gsi.state.is_stale else None

        # Hero
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

        # KDA
        kda = gsi.get_kda() if gsi else None
        if kda:
            state_parts.append(f"{kda[0]}/{kda[1]}/{kda[2]} KDA")

        # Score
        score = gsi.get_team_score() if gsi else None
        if score:
            state_parts.append(f"Score: {score[0]} - {score[1]}")

        # Level
        level = gsi.get_player_level() if gsi else None
        if level is not None:
            state_parts.append(f"Lvl {level}")

        # Souls
        souls = gsi.get_souls() if gsi else None
        if souls is not None:
            state_parts.append(f"{souls:,} Souls")

        # Game mode (small image)
        mode = gsi.get_game_mode() if gsi else None
        if mode:
            kwargs["small_image"] = "deadlock_icon"
            kwargs["small_text"] = get_game_mode_display(mode)

        # Elapsed timer
        if self.match_start:
            kwargs["start"] = int(self.match_start)

        # Assemble text lines
        kwargs["details"] = " · ".join(details_parts)
        if state_parts:
            kwargs["state"] = " | ".join(state_parts)

        # Fallback images
        if "large_image" not in kwargs:
            kwargs["large_image"] = "deadlock_icon"
            kwargs["large_text"] = "Deadlock"

        return kwargs

    # ── Main update tick ───────────────────────────────────────────────

    def tick(self):
        if not self.enabled:
            return

        # Ensure Discord is connected
        if not self.connected:
            if not self.connect_discord():
                return

        game_running = is_deadlock_running()

        # Game not running → clear
        if not game_running:
            if self.match_start is not None:
                logger.info("Deadlock closed — clearing presence.")
                self.match_start = None
                try:
                    self.rpc.clear()
                except Exception:
                    pass
            self.status = "Waiting for Deadlock..."
            return

        # Track match start
        gsi = self.gsi.state if self.gsi and not self.gsi.state.is_stale else None
        if gsi:
            phase = gsi.get_game_state()
            if phase and phase.lower() in ("playing", "ingame", "in_progress"):
                if self.match_start is None:
                    self.match_start = time.time()

        if self.match_start is None:
            self.match_start = time.time()

        # Build and push
        kwargs = self._build_presence()

        try:
            self.rpc.update(**kwargs)
            hero_part = kwargs.get("details", "")
            kda_part = kwargs.get("state", "")
            self.status = f"🎮 {hero_part}" + (f" — {kda_part}" if kda_part else "")
            logger.debug("Presence → %s", kwargs)
        except (PipeClosed, BrokenPipeError):
            logger.warning("Discord pipe closed — will reconnect.")
            self.connected = False
            self.status = "Reconnecting to Discord..."
        except Exception as e:
            logger.warning("Update failed: %s", e)

    # ── Background loop ────────────────────────────────────────────────

    def run_loop(self):
        """Runs in a background thread."""
        # Auto-install GSI config
        install_gsi_config()

        # Start GSI server
        self.start_gsi()

        # Initial Discord connection attempt
        self.connect_discord()

        self.status = "Waiting for Deadlock..."
        logger.info("Ready — waiting for Deadlock to launch.")

        while self._running:
            try:
                self.tick()
            except Exception as e:
                logger.error("Loop error: %s", e)
            time.sleep(UPDATE_INTERVAL)

        # Cleanup
        self.disconnect_discord()

    def stop(self):
        self._running = False


# ═══════════════════════════════════════════════════════════════════════════════
#  SYSTEM TRAY APPLICATION
# ═══════════════════════════════════════════════════════════════════════════════

class TrayApp:
    """Wraps the RPC engine in a system tray icon."""

    def __init__(self):
        self.engine = DeadlockRPC()
        self.icon: pystray.Icon | None = None
        self._worker: threading.Thread | None = None

    def _build_menu(self):
        def toggle_enabled(icon, item):
            self.engine.enabled = not self.engine.enabled
            if not self.engine.enabled:
                self.engine.disconnect_discord()
                self.engine.status = "Paused"
            icon.update_menu()

        def on_quit(icon, item):
            self.engine.stop()
            icon.stop()

        return pystray.Menu(
            pystray.MenuItem(
                lambda item: f"Status: {self.engine.status}",
                None, enabled=False,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                lambda item: "✓ Enabled" if self.engine.enabled else "  Paused",
                toggle_enabled,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                f"v{VERSION}",
                None, enabled=False,
            ),
            pystray.MenuItem("Quit", on_quit),
        )

    def _update_tooltip(self):
        """Periodically refresh the tooltip text."""
        while self.engine._running:
            if self.icon:
                try:
                    self.icon.title = f"{APP_NAME}\n{self.engine.status}"
                except Exception:
                    pass
            time.sleep(3)

    def run(self):
        logger.info("%s v%s starting...", APP_NAME, VERSION)

        # Hide console window on Windows
        if platform.system() == "Windows":
            try:
                ctypes.windll.user32.ShowWindow(
                    ctypes.windll.kernel32.GetConsoleWindow(), 0
                )
            except Exception:
                pass

        # Start RPC engine in background
        self._worker = threading.Thread(target=self.engine.run_loop, daemon=True)
        self._worker.start()

        # Start tooltip updater
        threading.Thread(target=self._update_tooltip, daemon=True).start()

        # Create and run tray icon (blocks on main thread)
        image = create_tray_icon_image()
        self.icon = pystray.Icon(
            name="deadlock-rpc",
            icon=image,
            title=f"{APP_NAME}\nStarting...",
            menu=self._build_menu(),
        )

        logger.info("System tray icon active.")
        self.icon.run()  # Blocks until icon.stop()

        # After tray exits
        self.engine.stop()
        if self._worker:
            self._worker.join(timeout=5)
        logger.info("Goodbye!")


# ═══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    # Prevent duplicate instances (simple file-lock approach)
    lock_path = LOG_DIR / ".lock"
    if platform.system() == "Windows":
        try:
            if lock_path.exists():
                lock_path.unlink()
            lock_file = open(lock_path, "w")
            import msvcrt
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        except (OSError, ImportError):
            # Already running or not on Windows — continue anyway
            pass
    else:
        try:
            import fcntl
            lock_file = open(lock_path, "w")
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, ImportError):
            pass

    app = TrayApp()
    app.run()


if __name__ == "__main__":
    main()
