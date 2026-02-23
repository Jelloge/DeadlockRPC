from __future__ import annotations
import logging
from pypresence import Presence, exceptions as rpc_exceptions
from game_state import GamePhase, GameState, MatchMode
logger = logging.getLogger(__name__)

PARTY_MAX = 6

class DiscordRPC:

    def __init__(self, application_id: str, assets_config: dict):
        self.application_id = application_id
        self.assets = assets_config
        self.rpc: Presence | None = None
        self._connected = False
        self._last_update_hash = None

    def connect(self) -> bool:
        try:
            self.rpc = Presence(self.application_id)
            self.rpc.connect()
            self._connected = True
            logger.info("Connected to Discord RPC")
            return True
        except Exception as e:
            logger.error("Failed to connect to Discord: %s", e)
            self._connected = False
            return False

    def disconnect(self) -> None:
        if self.rpc and self._connected:
            try:
                self.rpc.clear()
                self.rpc.close()
            except Exception:
                pass
        self._connected = False

    def ensure_connected(self) -> bool:
        if self._connected:
            return True
        return self.connect()

    def update(self, state: GameState) -> None:
        if not self.ensure_connected():
            return

        presence = self._build_presence(state)
        update_hash = str(presence)
        if update_hash == self._last_update_hash:
            return
        self._last_update_hash = update_hash

        try:
            if state.phase == GamePhase.NOT_RUNNING:
                self.rpc.clear()
            else:
                self.rpc.update(**presence)
                logger.debug("Presence: %s", presence)
        except rpc_exceptions.InvalidID:
            logger.error("Invalid Discord Application ID")
            self._connected = False
        except (ConnectionError, BrokenPipeError):
            logger.warning("Discord connection lost")
            self._connected = False
        except Exception as e:
            logger.error("RPC error: %s", e)

    def _build_presence(self, state: GameState) -> dict:
        if state.phase == GamePhase.NOT_RUNNING:
            return {}

        logo = self.assets.get("logo", "deadlock_logo")
        logo_text = self.assets.get("logo_text", "Deadlock")

        p: dict = {
            "large_image": state.hero_asset_name or logo,
            "large_text": state.hero_display_name or logo_text,
        }
        if state.in_party:
            p["party_size"] = [state.party_size, PARTY_MAX]

        match state.phase:
            case GamePhase.MAIN_MENU:
                p["details"] = "Main Menu"
                p["large_image"] = logo
                p["large_text"] = logo_text

            case GamePhase.HIDEOUT:
                p["details"] = "In the Hideout"
                p["state"] = f"Playing Solo (1 of 6)"

            case GamePhase.PARTY_HIDEOUT:
                p["details"] = "In Party Hideout"
                p["state"] = f"Party of {state.party_size}"

            case GamePhase.IN_QUEUE:
                p["details"] = "Looking for Match..."
                if state.in_party:
                    p["state"] = f"In Queue {state.party_size}"
                # if state.hero_key:
                #     p["small_text"] = "Searching"

            case GamePhase.MATCH_INTRO:
                mode_str = state.mode_display()
                hero = state.hero_display_name
                if state.in_party:
                    p["details"] = f" {mode_str} · {hero}" if hero else f" {mode_str}"
                    p["state"] = f"Party of {state.party_size}"
                elif hero:
                    p["details"] = f" {mode_str}"
                    p["state"] = f"Playing as {hero}"
                else:
                    p["details"] = f" {mode_str}"
                if state.hero_key:
                    p["small_image"] = logo
                    p["small_text"] = logo_text

            case GamePhase.IN_MATCH:
                mode_str = state.mode_display()
                hero = state.hero_display_name
                if state.in_party:
                    p["details"] = f" {mode_str} · {hero}" if hero else f" {mode_str}"
                    p["state"] = f"Party of {state.party_size}"
                elif hero:
                    p["details"] = f" {mode_str}"
                    p["state"] = f"Playing as {hero}"
                else:
                    p["details"] = f" {mode_str}"
                if state.hero_key:
                    p["small_image"] = logo
                    p["small_text"] = "The Archmother"
                if state.match_start_time and state.match_mode not in (MatchMode.SANDBOX, MatchMode.TUTORIAL):
                    p["start"] = int(state.match_start_time)

            case GamePhase.POST_MATCH:
                p["details"] = "Post-Match"

            case GamePhase.SPECTATING:
                p["details"] = "Spectating a Match"
                p["large_image"] = logo
                p["large_text"] = logo_text
                p.pop("small_image", None)
                p.pop("small_text", None)

        # Stable session timestamp
        if "start" not in p and state.session_start_time:
            p["start"] = int(state.session_start_time)

        return {k: v for k, v in p.items() if v is not None}