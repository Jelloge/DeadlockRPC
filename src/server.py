import json
import logging
import threading
import time
from flask import Flask, request

logger = logging.getLogger("deadlock-rpc.gsi")


class GSIState:
    """threadsafe container for the latest game state"""

    def __init__(self):
        self._lock = threading.Lock()
        self._state: dict = {}
        self._last_update: float = 0.0

    def update(self, data: dict):
        with self._lock:
            self._state = data
            self._last_update = time.time()

    def get(self) -> dict:
        with self._lock:
            return dict(self._state)

    @property
    def last_update(self) -> float:
        with self._lock:
            return self._last_update

    @property
    def is_stale(self) -> bool:
        with self._lock:
            return self._last_update == 0 or (time.time() - self._last_update) > 60.0

    def get_hero_name(self) -> str | None:
        s = self.get()
        return (
            s.get("hero", {}).get("name")
            or s.get("player", {}).get("hero")
            or s.get("hero", {}).get("id")
        )

    def get_kda(self) -> tuple[int, int, int] | None:
        p = self.get().get("player", {})
        if "kills" in p:
            return (p.get("kills", 0), p.get("deaths", 0), p.get("assists", 0))
        return None

    def get_team_score(self) -> tuple[int, int] | None:
        m = self.get().get("map", {})
        t1 = m.get("team1_score") or m.get("radiant_score")
        t2 = m.get("team2_score") or m.get("dire_score")
        if t1 is not None and t2 is not None:
            return (int(t1), int(t2))
        return None

    def get_game_time(self) -> int | None:
        m = self.get().get("map", {})
        gt = m.get("clock_time") or m.get("game_time")
        return int(gt) if gt is not None else None

    def get_game_state(self) -> str | None:
        m = self.get().get("map", {})
        return m.get("game_state") or m.get("phase")

    def get_game_mode(self) -> str | None:
        m = self.get().get("map", {})
        return m.get("mode") or m.get("game_mode")

    def get_player_level(self) -> int | None:
        s = self.get()
        lvl = s.get("hero", {}).get("level") or s.get("player", {}).get("level")
        return int(lvl) if lvl is not None else None

    def get_souls(self) -> int | None:
        p = self.get().get("player", {})
        val = p.get("souls") or p.get("gold") or p.get("net_worth")
        return int(val) if val is not None else None


class GSIServer:

    AUTH_TOKEN = "deadlock_discord_rpc_token"

    def __init__(self, port: int = 3000):
        self.port = port
        self.state = GSIState()

        self.app = Flask("deadlock-gsi")
        self.app.logger.setLevel(logging.WARNING)
        logging.getLogger("werkzeug").setLevel(logging.WARNING)

        @self.app.route("/", methods=["POST"])
        def _receive():
            try:
                data = request.get_json(force=True, silent=True)
                if not data:
                    return "Bad payload", 400
                auth = data.get("auth", {})
                if auth.get("token") != self.AUTH_TOKEN:
                    return "Unauthorized", 401
                self.state.update(data)
            except Exception as e:
                logger.error("GSI error: %s", e)
            return "OK", 200

        @self.app.route("/", methods=["GET"])
        def _health():
            return "GSI OK", 200

    def start(self):
        t = threading.Thread(
            target=lambda: self.app.run(host="127.0.0.1", port=self.port, threaded=True),
            daemon=True, name="gsi-server",
        )
        t.start()
        logger.info("GSI server on http://127.0.0.1:%d", self.port)
