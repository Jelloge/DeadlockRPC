import json
import os
import sys

DEFAULT_DISCORD_APP_ID = "1474302474474094634"
DEADLOCK_PROCESS_NAME = "project8.exe, deadlock.exe"
DEADLOCK_API_BASE = "https://api.deadlock-api.com/v1"
DEADLOCK_ASSETS_API = "https://assets.deadlock-api.com/v2"
HERO_IMAGE_BASE = "https://assets-bucket.deadlock-api.com/assets-api-res/images/heroes"
DEADLOCK_LOGO_URL = "https://assets-bucket.deadlock-api.com/assets-api-res/images/header.png"

PROCESS_CHECK_INTERVAL = 5
MATCH_POLL_INTERVAL = 30
PRESENCE_UPDATE_INTERVAL = 15

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "config.json")

def load_config():
    """Load user configuration from config.json."""
    defaults = {
        "discord_app_id": DEFAULT_DISCORD_APP_ID,
        "steam_id": "",
    }

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                user_config = json.load(f)
            defaults.update(user_config)
        except (json.JSONDecodeError, IOError):
            pass

    return defaults


def save_config(cfg):
    """Save configuration to config.json."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)
