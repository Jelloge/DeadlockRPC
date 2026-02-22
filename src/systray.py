import logging
import os
import platform
import threading
import time
from pathlib import Path

logger = logging.getLogger("deadlock-rpc")

def create_tray_icon(app):
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

    icon_path = Path(__file__).parent / "favicon.ico"
    if icon_path.exists():
        logger.info("Tray icon: %s", icon_path)
        image = Image.open(icon_path)
    else:
        logger.warning("favicon.ico not found, using fallback icon")
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
        log_file = Path(__file__).parent / "logs" / "deadlock_rpc.log"
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

    # update tooltip
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