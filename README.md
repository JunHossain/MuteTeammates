# MuteTeammates

Mute your dead Valorant teammates in Discord with one mouse button.

**How it works:** at match start, the local Riot client API tells us which
agent everyone on your team is playing and their IGN. When you press your
mouse side button, one screenshot of the top HUD strip is taken; anyone
whose agent portrait is missing from the strip is dead — the Discord bot
server-mutes them. That includes you, if you're in the players map and
annoying from the grave. Press again to unmute everyone.

## Setup

### 1. Install dependencies

```
pip install -r requirements.txt
```

### 2. Create your config

```
copy config.example.json config.json
```

`config.json` is gitignored — your bot token and friends' IDs stay local.

### 3. Create the Discord bot (one time)

1. Go to https://discord.com/developers/applications → **New Application**.
2. **Bot** tab → **Reset Token** → copy it into `config.json` → `discord.bot_token`.
   Never share this token or the config file.
3. Same page, under **Privileged Gateway Intents**: enable **Server Members Intent**.
4. **OAuth2 → URL Generator**: scope `bot`, permission **Mute Members**.
   Open the generated URL and invite the bot to your server.
   (It only needs Mute Members — don't give it admin.)
5. In Discord, enable **Settings → Advanced → Developer Mode**. Then:
   - Right-click your server → **Copy Server ID** → `discord.guild_id`.
   - Right-click each friend → **Copy User ID** → use in the `players` map.

### 4. Fill in `config.json`

```jsonc
"players": {
  "SPIDERMANN": 111111111111111111,      // Valorant name -> Discord user ID
  "papaplayer#TAG": 222222222222222222,  // with or without #TAG both work
  "SomeFriend": "their_discord_username" // username works too, ID is safer
}
```

Put **everyone who ever plays with you** in there — yourself included, if
you want to be muted when you die too. Each match, only the 5 actually in
the game matter. `riot.region` is your Valorant region
(`ap`, `na`, `eu`, `kr`, `br`, `latam`).

### 5. Tune the screen region (one time)

While in a match (1920x1080), run:

```
python main.py --capture
```

Open `strip.png` — it should contain all 5 teammate portraits at the top-left
of center, and nothing from the enemy side. Adjust `vision.region` in
`config.json` until it does.

### 6. Test, then run

```
python main.py --test-riot      # in a match: should print agents + IGNs
python main.py --test-vision    # should show high scores for living teammates
python main.py                  # run for real
```

Everyone must be in a voice channel of your server (server-mute only works
in voice). Press the side button (`x2` = forward by default, `x1` = back)
to mute the dead; press again to unmute. Set `auto_unmute_seconds` > 0 for
a safety timer that unmutes automatically.

## Troubleshooting

- **`--capture` is a black image** → set Valorant to *Windowed Fullscreen*
  (also fixes side-button not registering in exclusive fullscreen).
- **Riot connect fails** → Valorant must be running; the lockfile lives at
  `%LOCALAPPDATA%\Riot Games\Riot Client\Config\lockfile`.
- **Alive players detected as dead** → lower `vision.threshold` (check
  `--test-vision` scores), or the region is off — re-run `--capture`.
- **Dead players detected as alive** → raise `vision.threshold`: run
  `--test-vision` while a teammate is dead and pick a value between their
  score and the living players' scores.
- **"not in a voice channel — skipped"** → the bot can only mute people
  connected to voice in *your* server.
- **Not 1080p?** → scale `vision.region` and `template_size` proportionally.

## Notes

- The local Riot client API is unofficial (read-only, widely used by
  community tools, doesn't touch game memory — but not Riot-sanctioned).
- Get your friends' consent. It's funnier when everyone's in on it.
