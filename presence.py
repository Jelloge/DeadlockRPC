import logging
import time

from pypresence import Presence, DiscordNotFound, PipeClosed

from config import DEADLOCK_LOGO_URL
from deadlock_api import DeadlockAPI
from game_monitor import GameState, MatchInfo

log = logging.getLogger(__name__)


class PresenceManager:
    def __init__(self, client_id, api=None):
        self.client_id = client_id
        self.api = api or DeadlockAPI()
        self._rpc = None
        self._connected = False
        self._last_update = 0
        self._last_state_hash = None

    @property
    def connected(self):
        return self._connected

    def connect(self):
        if self._connected:
            return True

        try:
            self._rpc = Presence(self.client_id)
            self._rpc.connect()
            self._connected = True
            log.info("Connected to Discord")
            return True
        except DiscordNotFound:
            log.debug("Discord not running")
            return False
        except Exception as e:
            log.debug("Failed to connect to Discord: %s", e)
            return False

    def disconnect(self):
        if self._rpc and self._connected:
            try:
                self._rpc.clear()
                self._rpc.close()
            except Exception:
                pass
        self._connected = False
        self._rpc = None
        self._last_state_hash = None

    def update(self, game_state, match_info=None, game_launch_time=None, min_interval=15):
        """
       Args:
            game_state: Current GameState enum value.
            match_info: MatchInfo object if in a match.
            game_launch_time: Epoch timestamp when the game was launched.
            min_interval: Minimum seconds between Discord updates.
        """
        if not self._connected:
            return

        # Rate limit updates
        now = time.time()
        if now - self._last_update < min_interval:
            return

        try:
            if game_state == GameState.CLOSED:
                self._clear_presence()
            elif game_state == GameState.IN_MATCH and match_info:
                self._update_in_match(match_info)
            elif game_state == GameState.MENU:
                self._update_in_menu(game_launch_time)
        except (PipeClosed, BrokenPipeError, OSError):
            log.warning("Discord connection lost")
            self._connected = False
            self._rpc = None
        except Exception as e:
            log.warning("Failed to update presence: %s", e)

    def _clear_presence(self):
        """Clear the Discord presence."""
        state_hash = "cleared"
        if self._last_state_hash == state_hash:
            return
        try:
            self._rpc.clear()
            self._last_state_hash = state_hash
            self._last_update = time.time()
            log.debug("Presence cleared")
        except Exception:
            pass

    def _update_in_menu(self, game_launch_time=None):
        """Show that the player is in the Deadlock menu."""
        state_hash = "menu"
        if self._last_state_hash == state_hash:
            return

        kwargs = {
            "details": "In Menu",
            "state": "Browsing",
            "large_image": DEADLOCK_LOGO_URL,
            "large_text": "Deadlock",
        }

        if game_launch_time:
            kwargs["start"] = int(game_launch_time)

        self._rpc.update(**kwargs)
        self._last_state_hash = state_hash
        self._last_update = time.time()
        log.debug("Presence updated: In Menu")

    def _update_in_match(self, info: MatchInfo):
        """Show detailed match information."""
        state_hash = (
            f"match:{info.match_id}:{info.hero_id}"
            f":{info.net_worth_team_0}:{info.net_worth_team_1}"
        )
        if self._last_state_hash == state_hash:
            return

        #hero name + game mode
        details = f"Playing {info.hero_name}"
        if info.game_mode:
            details += f" | {info.game_mode}"

        #team + net worth comparison
        state_parts = []
        if info.team_name:
            state_parts.append(info.team_name)

        if info.net_worth_team_0 or info.net_worth_team_1:
            souls_0 = self._format_souls(info.net_worth_team_0)
            souls_1 = self._format_souls(info.net_worth_team_1)
            state_parts.append(f"Souls: {souls_0} vs {souls_1}")

        state = " | ".join(state_parts) if state_parts else "In Match"

        #hero image
        hero_image = ""
        hero_text = info.hero_name
        if info.hero_id:
            hero_image = self.api.get_hero_image(info.hero_id)

        kwargs = {
            "details": details[:128],
            "state": state[:128],
            "large_image": hero_image or DEADLOCK_LOGO_URL,
            "large_text": hero_text,
            "small_image": DEADLOCK_LOGO_URL,
            "small_text": "Deadlock",
        }

        #match start timestamp for elapsed time
        if info.start_time:
            kwargs["start"] = int(info.start_time)

        #party info
        if info.party_size > 1:
            kwargs["party_id"] = f"match_{info.match_id}"
            kwargs["party_size"] = [info.party_size, info.party_max]

        self._rpc.update(**kwargs)
        self._last_state_hash = state_hash
        self._last_update = time.time()
        log.debug("Presence updated: %s (%s)", info.hero_name, info.match_id)

    @staticmethod
    def _format_souls(value):
        if not value:
            return "0"
        if value >= 1000:
            return f"{value / 1000:.1f}k"
        return str(value)
