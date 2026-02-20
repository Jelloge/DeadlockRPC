# Deadlock — Discord Rich Presence

A lightweight system-tray app that shows your live **Deadlock** match details on your Discord profile — hero, KDA, score, match time, and more. Users just download and run. Zero setup.

---

## What It Shows

| Detail | Example |
|---|---|
| **Hero** | "Playing Haze" with hero portrait |
| **KDA** | 8/2/5 KDA |
| **Team Score** | Score: 24 - 18 |
| **Match Timer** | 14:32 elapsed |
| **Game Mode** | Standard Match / Street Brawl |
| **Level** | Lvl 14 |
| **Souls** | 12,400 Souls |

Without Game State Integration data, a basic "Playing Deadlock" presence with elapsed time is still shown.

---

## For End Users

1. **Download** `DeadlockRPC.exe`
2. **Run it** — a small icon appears in your system tray
3. **Play Deadlock** — your Discord profile updates automatically
4. That's it. No accounts, no API keys, no config files.

**Right-click the tray icon** to pause/resume or quit.

> **First run:** The app automatically installs a small config file into your Deadlock folder so the game can send live match data. You may need to restart Deadlock once after installation.

> **Tip:** Make sure Discord's Activity Status is turned on: *User Settings → Activity Privacy → Display current activity as a status message*.

---

## For the Developer (You)

### One-Time Setup

#### 1. Create a Discord Application

1. Go to the **[Discord Developer Portal](https://discord.com/developers/applications)**
2. Click **New Application** → name it `Deadlock`
3. Copy the **Application ID**

#### 2. Upload Rich Presence Art Assets

In the Developer Portal: **Your App → Rich Presence → Art Assets**

Upload images with these **exact** names:

| Asset Key | What to Upload |
|---|---|
| `deadlock_logo` | Deadlock game logo (required — default fallback) |
| `hero_abrams` | Abrams portrait |
| `hero_haze` | Haze portrait |
| `hero_seven` | Seven portrait |
| ... | See `heroes.py` for the full list of 38+ heroes |

Hero portraits can be found on the [Deadlock Wiki](https://deadlock.wiki/Heroes) or community sites. They should be square, at least 512×512.

#### 3. Set Your Application ID

Open `deadlock_rpc.py` and replace the placeholder:

```python
DISCORD_APP_ID = "YOUR_DISCORD_APP_ID_HERE"  # ← paste your ID here
```

#### 4. Build the Executable

**Windows:**
```
build.bat
```

**Or manually:**
```bash
pip install -r requirements.txt
pyinstaller deadlock_rpc.spec --noconfirm --clean
```

Output: `dist/DeadlockRPC.exe` — this is the single file you distribute.

**Optional:** Drop a custom `icon.ico` in the `assets/` folder before building and uncomment the `icon=` line in `deadlock_rpc.spec` for a proper Deadlock icon on the .exe.

#### 5. Distribute

Upload `DeadlockRPC.exe` wherever you like — GitHub Releases, your website, etc. Users just download and run it.

---

## How It Works

```
┌─────────────┐     HTTP POST       ┌──────────────┐
│  Deadlock    │ ──────────────────→ │  GSI Server  │
│  (Source 2)  │   localhost:3000    │  (Flask)     │
└─────────────┘                      └──────┬───────┘
                                            │
       ┌────────────┐                       │ live game state
       │  Process    │  game running?       │
       │  Detection  │ ───────────┐         │
       │  (psutil)   │            ▼         ▼
       └────────────┘       ┌────────────────────┐
                            │   DeadlockRPC      │
                            │   Engine           │
                            └────────┬───────────┘
                                     │
                                     │ RPC update every 15s
                                     ▼
                            ┌────────────────────┐
                            │  Discord Client    │
                            │  (pypresence IPC)  │
                            └────────────────────┘
                                     │
                                     ▼
                            ┌────────────────────┐
                            │  System Tray Icon  │
                            │  (pystray)         │
                            └────────────────────┘
```

**Data priority:**
1. **Game State Integration** — Real-time hero, KDA, score, level, souls (richest data)
2. **Process detection** — Detects game running/stopped for basic presence

**On first run, the app automatically:**
- Locates the Steam/Deadlock installation via the Windows registry
- Creates the `gamestate_integration` folder if needed
- Writes the GSI config file so Deadlock starts sending game state data
- Starts a local HTTP listener on port 3000
- Connects to Discord's IPC pipe

---

## Project Structure

```
deadlock-discord-rpc/
├── deadlock_rpc.py       ← Main app (tray icon + RPC engine)
├── gsi_server.py         ← Game State Integration HTTP receiver
├── heroes.py             ← Hero roster & asset key mappings
├── deadlock_rpc.spec     ← PyInstaller build config
├── build.bat             ← One-click Windows build script
├── requirements.txt      ← Python dependencies
├── assets/               ← Place icon.ico / icon.png here (optional)
│   └── (your icon)
├── LICENSE
└── README.md
```

---

## Adding New Heroes

When Valve adds heroes:

1. Open `heroes.py`
2. Add to the `HEROES` dict:
   ```python
   "new_hero": {"name": "New Hero", "image": "hero_new_hero"},
   ```
3. Upload the portrait to your Discord Application's Art Assets
4. Rebuild the .exe

---

## Troubleshooting

| Problem | Solution |
|---|---|
| Discord doesn't show activity | Enable Activity Status in Discord settings. Must use desktop app (not browser). |
| No hero/KDA/score data | Restart Deadlock after first run. Add `-gamestateintegration` to Deadlock's Steam launch options. |
| "Waiting for Discord..." | Start the Discord desktop app first. |
| Tray icon not visible | Check the system tray overflow area (the `^` arrow on Windows). |
| Antivirus flags the .exe | PyInstaller executables are sometimes falsely flagged. Add an exception. |

Logs are saved to: `%USERPROFILE%\.deadlock-rpc\deadlock_rpc.log`

---

## License

MIT — see [LICENSE](LICENSE).

*Deadlock is a trademark of Valve Corporation. Not affiliated with or endorsed by Valve or Discord.*
