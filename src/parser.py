import json
import re
import sys
from pathlib import Path

PRIMARY = {
    "ChangeGameState":    r"ChangeGameState:\s+\w+\s+\(\d+\)",
    "HLTV state":         r"Citadel HLTV Director, Entering game state",
    "Hideout lobby":      r"\[Hideout\] Hideout Lobby Connection State",
    "Client connected":   r"\[Client\] CL:\s+Connected to",
    "Client disconnect":  r"\[Client\] Disconnecting from server",
    "Server shutdown":    r"\[Server\] SV:\s+Server shutting down",
    "Map load":           r"\[HostStateManager\].*Loading \(",
    "Host activate":      r"\[HostStateManager\] Host activate",
    "Loaded hero":        r"\[Server\] Loaded hero \d+/",
    "Created bot":        r"Created bot \d+/hero_\w+",
    "Bot init":           r"Initializing bot for player slot",
    "Map info":           r"\[Client\] Map:",
    "Player info":        r"\[Client\] Players:",
    "Precaching":         r"Precaching \d+ heroes",
    "App shutdown":       r"Dispatching EventAppShutdown_t|Source2Shutdown",
    "LoopMode menu":      r"LoopMode:\s*menu",
}


def inspect(log_path: str):
    lines = Path(log_path).read_text(errors="replace").splitlines()
    print(f"Loaded {len(lines)} lines\n")

    for name, pattern in PRIMARY.items():
        matches = [(i, l.strip()) for i, l in enumerate(lines) if re.search(pattern, l, re.IGNORECASE)]
        if not matches:
            continue
        print(f"── {name} ({len(matches)} matches) ──")
        seen = set()
        for line_num, text in matches[:15]:
            key = re.sub(r'\d+', 'N', text)[:80]
            if key not in seen:
                seen.add(key)
                print(f"  L{line_num:>5}: {text[:200]}")
        if len(matches) > 15:
            print(f"  ... +{len(matches) - 15} more")
        print()

    print("Summary:")
    for name, pattern in PRIMARY.items():
        count = sum(1 for l in lines if re.search(pattern, l, re.IGNORECASE))
        if count:
            print(f"  {name:<25} {count:>5}")


def replay(log_path: str, config_path: str = "config.json"):
    from game_state import GameState, GamePhase
    from console_log import LogWatcher

    with open(config_path) as f:
        config = json.load(f)

    lines = Path(log_path).read_text(errors="replace").splitlines()
    print(f"Replaying {len(lines)} lines...\n")

    state = GameState()
    state.enter_main_menu()

    watcher = LogWatcher(
        log_path=log_path, state=state,
        patterns=config.get("log_patterns", {}),
        map_to_mode=config.get("map_to_mode", {}),
        hideout_maps=config.get("hideout_maps", ["dl_hideout"]),
        process_names=[],
    )

    transitions = [("START", state.phase.name, state.hero_display_name, state.map_name)]

    for i, line in enumerate(lines):
        line = line.strip()
        if line and watcher._process_line(line):
            transitions.append((f"L{i}", state.phase.name, state.hero_display_name, state.map_name))

    print(f"{'Line':<8} {'Phase':<18} {'Hero':<22} {'Map'}")
    print("─" * 60)
    for ref, phase, hero, map_name in transitions:
        print(f"{ref:<8} {phase:<18} {hero or '—':<22} {map_name or '—'}")
    print(f"\n{len(transitions)} state transitions")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python inspect_log.py <console.log> [--replay]")
        sys.exit(1)

    if "--replay" in sys.argv:
        replay(sys.argv[1])
    else:
        inspect(sys.argv[1])