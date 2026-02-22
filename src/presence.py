from __future__ import annotations
import logging
from typing import Optional
from pypresence import Presence, exceptions as rpc_exceptions
from game_state import GamePhase, GameState, MatchMode
logger = logging.getLogger(__name__)

PARTY_MAX = 6

class DiscordRPC:

    def __init__(self, application_id: str, assets_config: dict, hero_prefix: str = "hero_"):
        self.application_id = application_id
        self.assets = assets_config
        self.hero_prefix = hero_prefix
        self.rpc: Optional[Presence] = None
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
        logo = self.assets.get("logo", "deadlock_logo")
        logo_text = self.assets.get("logo_text", "Deadlock")
        p: dict = {}

        match state.phase:
            case GamePhase.NOT_RUNNING:
                return {}

            case GamePhase.MAIN_MENU:
                p["details"] = "Main Menu"
                p["large_image"] = logo
                p["large_text"] = logo_text

            case GamePhase.HIDEOUT:
                p["details"] = "In the Hideout"
                p["large_image"] = self._hero_or_logo(state, logo)
                p["large_text"] = state.hero_display_name or logo_text
                self._small_logo_if_hero(p, state, logo, logo_text)

            case GamePhase.PARTY_HIDEOUT:
                p["details"] = "In Party Hideout"
                p["state"] = f"Party of {state.party_size}"
                p["large_image"] = self._hero_or_logo(state, logo)
                p["large_text"] = state.hero_display_name or logo_text
                p["party_size"] = [state.party_size, PARTY_MAX]
                self._small_logo_if_hero(p, state, logo, logo_text)

            case GamePhase.IN_QUEUE:
                p["details"] = "Finding Match"
                p["state"] = "Searching..."
                p["large_image"] = self._hero_or_logo(state, logo)
                p["large_text"] = state.hero_display_name or logo_text
                p["small_image"] = self.assets.get("queue_icon", logo)
                p["small_text"] = "Searching"
                if state.in_party:
                    p["party_size"] = [state.party_size, PARTY_MAX]

            case GamePhase.MATCH_INTRO:
                mode_str = state.mode_display()
                p["details"] = f"Playing {mode_str}"
                p["state"] = "Match starting."
                p["large_image"] = self._hero_or_logo(state, logo)
                p["large_text"] = state.hero_display_name or logo_text
                self._small_logo_if_hero(p, state, logo, mode_str)
                if state.in_party:
                    p["party_size"] = [state.party_size, PARTY_MAX]

            case GamePhase.IN_MATCH:
                mode_str = state.mode_display()
                p["details"] = f"Playing {mode_str}"

                parts = []
                if state.hero_display_name:
                    parts.append(state.hero_display_name)
                if state.in_party:
                    parts.append(f"Party of {state.party_size}")
                p["state"] = " · ".join(parts) if parts else "In Match"

                p["large_image"] = self._hero_or_logo(state, logo)
                p["large_text"] = state.hero_display_name or logo_text
                if state.hero_key:
                    p["small_image"] = logo
                    p["small_text"] = mode_str

                if state.match_start_time:
                    p["start"] = int(state.match_start_time)
                if state.in_party:
                    p["party_size"] = [state.party_size, PARTY_MAX]

            case GamePhase.POST_MATCH:
                p["details"] = "Post-Match"
                p["large_image"] = self._hero_or_logo(state, logo)
                p["large_text"] = state.hero_display_name or logo_text
                self._small_logo_if_hero(p, state, logo, logo_text)

            case GamePhase.SPECTATING:
                p["details"] = "Spectating a Match"
                p["large_image"] = logo
                p["large_text"] = logo_text

        return {k: v for k, v in p.items() if v is not None}

    def _hero_or_logo(self, state: GameState, logo: str) -> str:
        return state.hero_asset_name if state.hero_key else logo

    def _small_logo_if_hero(self, p: dict, state: GameState, logo: str, text: str) -> None:
        if state.hero_key:
            p["small_image"] = logo
            p["small_text"] = text