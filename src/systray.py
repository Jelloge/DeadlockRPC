import sys
import time
import threading
import ctypes
import platform
import logging
from pathlib import Path

import pystray
from PIL import Image, ImageDraw, ImageFont

from rpc_manager import DeadlockRPC

logger = logging.getLogger("deadlock-rpc")

APP_NAME = "Deadlock"
VERSION = "1.0.0"
LOG_DIR = Path.home() / ".deadlock-rpc"

def create_tray_icon_image() -> Image.Image:
    for icon_name in ["icon.ico", "icon.png"]:
        for search_dir in [Path(__file__).parent / "assets", Path(getattr(sys, "_MEIPASS", "")) / "assets", LOG_DIR / "assets"]:
            icon_path = search_dir / icon_name
            if icon_path.exists():
                try: return Image.open(icon_path).resize((64, 64))
                except Exception: pass
                
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([2, 2, size - 2, size - 2], fill=(30, 30, 35, 255))
    draw.ellipse([2, 2, size - 2, size - 2], outline=(218, 165, 32, 255), width=3)
    try: font = ImageFont.truetype("arial.ttf", 22)
    except OSError: font = ImageFont.load_default()

    text = "DL"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - tw) // 2, (size - th) // 2 - 2), text, fill=(218, 165, 32, 255), font=font)
    return img

class TrayApp:
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
            pystray.MenuItem(lambda item: f"Status: {self.engine.status}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(lambda item: "✓ Enabled" if self.engine.enabled else "  Paused", toggle_enabled),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(f"v{VERSION}", None, enabled=False),
            pystray.MenuItem("Quit", on_quit),
        )

    def _update_tooltip(self):
        while self.engine._running:
            if self.icon:
                try: self.icon.title = f"{APP_NAME}\n{self.engine.status}"
                except Exception: pass
            time.sleep(3)

    def run(self):
        logger.info("%s v%s starting...", APP_NAME, VERSION)
        if platform.system() == "Windows":
            try: ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
            except Exception: pass

        self._worker = threading.Thread(target=self.engine.run_loop, daemon=True)
        self._worker.start()
        threading.Thread(target=self._update_tooltip, daemon=True).start()

        self.icon = pystray.Icon(
            name="deadlock-rpc",
            icon=create_tray_icon_image(),
            title=f"{APP_NAME}\nStarting...",
            menu=self._build_menu(),
        )
        self.icon.run()
        self.engine.stop()
        if self._worker: self._worker.join(timeout=5)