"""Launch Deadlock with -condebug via Steam.
"""

import os
import subprocess
import sys
import webbrowser

DEADLOCK_APP_ID = "1422450"
STEAM_URL = f"steam://run/{DEADLOCK_APP_ID}//-condebug/"


def launch():
    """Open Steam and launch Deadlock with -condebug."""
    if sys.platform == "win32":
        os.startfile(STEAM_URL)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", STEAM_URL])
    else:
        # xdg-open is more reliable than webbrowser for steam:// URIs on Linux
        try:
            subprocess.Popen(["xdg-open", STEAM_URL])
        except FileNotFoundError:
            webbrowser.open(STEAM_URL)


if __name__ == "__main__":
    launch()
