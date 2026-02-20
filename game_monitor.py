import logging
import time
from enum import Enum

import psutil

from config import DEADLOCK_PROCESS_NAME
from deadlock_api import DeadlockAPI

log = logging.getLogger(__name__)


class GameState(Enum):
    """Possible states of the Deadlock game."""
    CLOSED = "closed"
    MENU = "menu"
    IN_MATCH = "in_match"


class MatchInfo:
    """Container for current match information."""

    def __init__(self):
        self.match_id = None
        self.hero_id = None
        self.hero_name = ""
        self.team = None
        self.team_name = ""
        self.game_mode = ""
        self.match_mode = ""
        self.start_time = None
        self.party_size = 1
        self.party_max = 12
        self.net_worth_team_0 = 0
        self.net_worth_team_1 = 0
        self.spectators = 0

    def __eq__(self, other):
        if not isinstance(other, MatchInfo):
            return False
        return (self.match_id == other.match_id
                and self.hero_id == other.hero_id
                and self.net_worth_team_0 == other.net_worth_team_0
                and self.net_worth_team_1 == other.net_worth_team_1)


class GameMonitor:
    """Monitors Deadlock's running state and polls the API for match data."""

    def __init__(self, steam_id, api=None):
        self.steam_id = steam_id
        self.api = api or DeadlockAPI()
        self._state = GameState.CLOSED
        self._match_info = None
        self._last_api_poll = 0
        self._game_launch_time = None

    @property
    def state(self):
        return self._state

    @property
    def match_info(self):
        return self._match_info

    @property
    def game_launch_time(self):
        return self._game_launch_time

    def update(self, poll_interval=30):
        """Check game state and update match info.

        Args:
            poll_interval: Minimum seconds between API polls.

        Returns:
            tuple: (GameState, MatchInfo or None)
        """
        game_running = self._is_game_running()

        if not game_running:
            if self._state != GameState.CLOSED:
                log.info("Deadlock closed")
            self._state = GameState.CLOSED
            self._match_info = None
            self._game_launch_time = None
            return self._state, None

        if self._game_launch_time is None:
            self._game_launch_time = time.time()
            log.info("Deadlock detected")

        #poll API for active match data
        now = time.time()
        if self.steam_id and (now - self._last_api_poll >= poll_interval):
            self._last_api_poll = now
            self._poll_match_data()

        return self._state, self._match_info

    def _is_game_running(self):
        """Check if the Deadlock process is running."""
        for proc in psutil.process_iter(["name"]):
            try:
                if proc.info["name"] and proc.info["name"].lower() == DEADLOCK_PROCESS_NAME:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False

    def _poll_match_data(self):
        """Poll the Deadlock API for the player's active match."""
        result = self.api.find_player_active_match(self.steam_id)

        if result is None:
            if self._state == GameState.IN_MATCH:
                log.info("Match ended or player no longer in active match")
            self._state = GameState.MENU
            self._match_info = None
            return

        match_data = result["match"]
        player_data = result["player"]

        info = MatchInfo()
        info.match_id = match_data.get("match_id")
        info.hero_id = player_data.get("hero_id")
        info.hero_name = self.api.get_hero_name(info.hero_id) if info.hero_id else "Unknown"
        info.team = player_data.get("team")
        info.team_name = player_data.get("team_parsed", "")
        if info.team_name.startswith("KECitadelTeam"):
            info.team_name = info.team_name.replace("KECitadelTeam", "Team ")

        info.game_mode = self.api.parse_game_mode(match_data)
        info.start_time = match_data.get("start_time")
        info.net_worth_team_0 = match_data.get("net_worth_team_0", 0)
        info.net_worth_team_1 = match_data.get("net_worth_team_1", 0)
        info.spectators = match_data.get("spectators", 0)

        # count party members
        players = match_data.get("players", [])
        player_party = player_data.get("party")
        if player_party is not None and player_party > 0:
            info.party_size = sum(
                1 for p in players
                if p.get("party") == player_party
            )
        else:
            info.party_size = 1
        info.party_max = len(players) if players else 12

        if self._state != GameState.IN_MATCH:
            log.info("Entered match %s as %s", info.match_id, info.hero_name)

        self._state = GameState.IN_MATCH
        self._match_info = info
