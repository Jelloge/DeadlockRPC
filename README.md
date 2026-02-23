<img width="1700" height="1268" alt="image" src="https://github.com/user-attachments/assets/6d562252-a7e6-44ab-bfeb-8a753469b117" />


Rich Presence for Valve's [Deadlock](https://store.steampowered.com/app/1422450/Deadlock/) .

Python application that shows your current in-game status on your Discord profile (hero, game mode, match type, party size, match timer, etc).
The application will automatically launch your game with '-condebug' via Steam so console logging is always enabled.

## Requirements

- Discord 
- Steam + Deadlock installed

## Installation

Download **DeadlockRPC.exe** from the [latest release](https://github.com/Jelloge/DeadlockRPC/releases/latest) and run it! It will show up in your taskbar.

Config.json has my game's install path hardcoded, and it will work for most people. If you have Deadlock on a different drive, it will (should) fall back to the auto-detection feature which will search common paths and parses libraryfolders.vdf so it should be fine. 

<details>
<summary>Building from source</summary>

1. **Clone the repo**
2. **Install dependencies** (Python 3.10+)
3. **Configure** (optional)

Edit `src/config.json` if needed:
- `deadlock_install_path` set this if Deadlock isn't in a standard Steam library location
- `update_interval_seconds` how often Discord presence refreshes default: 15s

4. **Run**
5. **Build the exe** (optional)

pip install pyinstaller
python build.py

Output: `dist/DeadlockRPC.exe`

</details>

## Linux/Mac Support

The app was built and tested on a Windows platform, so currently Mac and Linux are unsupported. Linux users MIGHT be able to run python src/main.py from source. Let me know if you try this! 

## How It Works

DeadlockRP monitors Deadlock's `console.log` file (written when the game runs with `-condebug`). It parses log events using regex patterns to detect game state changes that I painstakingly mapped out, and pushes updates to Disc.

The game's runtime and memory are never touched. So it's VAC-safe and won't affect performance.

## TO-DO

- Dynamic portrait changes, for critical and gloating portraits. Recently implemented switches that will display Silver's wolf and human form, so I know that it's do-able
- Localization
- Clean up code
- Cross-platform stuff

## Known Bugs

Please report any bugs in the Issues tab.

- 'Looking for Match...' not being displayed for players in a party.

