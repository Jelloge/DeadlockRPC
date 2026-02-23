<img width="1700" height="1268" alt="image" src="https://github.com/user-attachments/assets/6d562252-a7e6-44ab-bfeb-8a753469b117" />

[![pypresence](https://img.shields.io/badge/using-pypresence-00bb88.svg?style=for-the-badge&logo=discord&logoWidth=20)](https://github.com/qwertyquerty/pypresence) ![Platform: Windows](https://img.shields.io/badge/platform-Windows-lightgrey?cacheSeconds=100000) [![SuperCumRat69 on Steam](https://img.shields.io/badge/Steam-SuperCumRat69-blue?logo=Steam)](https://steamcommunity.com/id/supercumrat69/)


Discord Rich Presence for Valve's [Deadlock](https://store.steampowered.com/app/1422450/Deadlock/). Python application that shows your current in-game status on your Discord profile (hero, game mode, match type, party size, match timer, etc).

<img width="250" height="127" alt="deadlock1" src="https://github.com/user-attachments/assets/04db86fa-7a8d-41eb-8311-44d65bd2ca0b" />  <img width="257" height="144" alt="deadlock3" src="https://github.com/user-attachments/assets/5e2fb80c-08b5-4d82-abfb-83d25a6d2c0e" /> <img width="273" height="137" alt="deadlock2" src="https://github.com/user-attachments/assets/02f94a24-3aa7-48a8-a028-7ae4b304f3f4" />

## Requirements

- Discord 
- Steam + Deadlock installed

## Installation and Setup


Download **DeadlockRPC.exe** from the [latest release](https://github.com/Jelloge/DeadlockRPC/releases/latest) and run it! 

It will show up in your taskbar. Make sure you launch the game USING this app, as it will automatically launch your game with '-condebug' via Steam so console logging is always enabled.

If you need help, message me on Discord: boba

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

Please share any issues!

- 'Looking for Match...' not being displayed for players in a party.

