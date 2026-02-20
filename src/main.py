import platform
import logging
from pathlib import Path
import sys

from tray_app import TrayApp

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

def main():
    lock_path = LOG_DIR / ".lock"
    
    if platform.system() == "Windows":
        try:
            if lock_path.exists():
                lock_path.unlink()
            lock_file = open(lock_path, "w")
            import msvcrt
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        except (OSError, ImportError):
            logger.error("App is already running.")
            sys.exit(0)
    else:
        try:
            import fcntl
            lock_file = open(lock_path, "w")
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, ImportError):
            logger.error("App is already running.")
            sys.exit(0)

    app = TrayApp()
    app.run()

if __name__ == "__main__":
    main()