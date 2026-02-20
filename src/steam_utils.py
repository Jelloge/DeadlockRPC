import platform
import logging
from pathlib import Path
import psutil

logger = logging.getLogger("deadlock-rpc")

DEADLOCK_PROCESS_NAMES = {
    "project8.exe", "deadlock.exe", "citadel.exe",
    "project8", "deadlock", "citadel",
}

GSI_CFG_CONTENT = '''"Deadlock RPC"
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

def find_steam_path() -> Path | None:
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
        for p in [Path(r"C:\Program Files (x86)\Steam"), Path(r"C:\Program Files\Steam"), Path(r"D:\Steam"), Path(r"D:\SteamLibrary")]:
            if p.exists(): return p
    elif system == "Linux":
        for p in [Path.home() / ".steam" / "steam", Path.home() / ".local" / "share" / "Steam"]:
            if p.exists(): return p
    elif system == "Darwin":
        p = Path.home() / "Library" / "Application Support" / "Steam"
        if p.exists(): return p
    return None

def find_steam_library_folders(steam_path: Path) -> list[Path]:
    folders = [steam_path]
    vdf_path = steam_path / "steamapps" / "libraryfolders.vdf"
    if not vdf_path.exists():
        vdf_path = steam_path / "config" / "libraryfolders.vdf"
    if vdf_path.exists():
        try:
            text = vdf_path.read_text(encoding="utf-8", errors="ignore")
            import re
            for match in re.finditer(r'"path"\s+"([^"]+)"', text):
                p = Path(match.group(1))
                if p.exists() and p not in folders:
                    folders.append(p)
        except Exception:
            pass
    return folders

def find_deadlock_install() -> Path | None:
    steam_path = find_steam_path()
    if not steam_path: return None
    libraries = find_steam_library_folders(steam_path)
    for lib in libraries:
        for name in ["Deadlock", "deadlock"]:
            game_dir = lib / "steamapps" / "common" / name
            if game_dir.exists(): return game_dir
    return None

def install_gsi_config() -> bool:
    game_dir = find_deadlock_install()
    if not game_dir:
        logger.warning("Could not find Deadlock installation — GSI auto-install skipped.")
        return False
    gsi_dir = game_dir / "game" / "citadel" / "cfg" / "gamestate_integration"
    try:
        gsi_dir.mkdir(parents=True, exist_ok=True)
        cfg_path = gsi_dir / "gamestate_integration_discord_rpc.cfg"
        if cfg_path.exists():
            existing = cfg_path.read_text(encoding="utf-8", errors="ignore")
            if existing.strip() == GSI_CFG_CONTENT.strip():
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

def is_deadlock_running() -> bool:
    for proc in psutil.process_iter(["name"]):
        try:
            name = proc.info.get("name", "")
            if name and name.lower() in DEADLOCK_PROCESS_NAMES:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False