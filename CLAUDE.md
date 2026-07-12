# CLAUDE.md — project notes

This file is Claude's persistent project memory. It is loaded automatically at
the start of every session. **Keep the "Current status" section up to date
whenever meaningful work happens** — the user has frequent power outages and
loses sessions, so this file is how a fresh session catches up.

## What this project is

**MuteTeammates** — a Windows tool that server-mutes dead Valorant teammates
in Discord at the press of a mouse side button. Portfolio project of the user.

Pipeline:
1. `riot.py` — connects to the *local* Riot client API (via `valclient`
   lockfile auth) to learn the current match roster: which agent each
   player on our team plays (self included) and their IGN. Also downloads agent portrait icons from
   valorant-api.com into `templates/` (auto-cached, gitignored).
2. `vision.py` — screenshots the top HUD strip (`mss`) and template-matches
   each roster agent's portrait against it (OpenCV `TM_CCOEFF_NORMED`).
   Portrait present = alive, absent = dead. Key tricks: templates are
   composited onto the *median color* of the captured strip (HUD band color
   varies per map), and scales stay tight around 40px (1080p portrait size).
3. `bot.py` — `discord.py` client. A `pynput` mouse listener (side button,
   default `x2`) toggles: mute all dead teammates / unmute everyone.
   Background task polls the Riot API every 15s for new matches.
4. `main.py` — entry point + CLI helpers: `--capture` (tune screen region),
   `--test-riot` (print roster), `--test-vision` (print match scores).

## Configuration & secrets

- `config.json` — the REAL config with the Discord bot token, guild id, and
  the IGN→Discord-id map of the user's friends. **Gitignored, never commit.**
- `config.example.json` — committed placeholder version. Keep the two in
  sync structurally when config keys change.

## Conventions / decisions

- Working state on the user's machine: 1920x1080, region `ap`,
  mouse button `x2`, threshold 0.75 — all confirmed working (2026-07-12).
- Server-mute only works when targets are in a voice channel of the guild.
- The local Riot API is unofficial; treat it as read-only.
- The roster includes the user themself — they get muted on death too
  (their IGN must be in the `players` map like everyone else's).
- Commit messages: short, single line, no Claude attribution / trailers.

## Current status

- **2026-07-12**: Tool confirmed fully working by the user. Secrets were
  abstracted out of git (config.example.json + .gitignore), repo published
  at https://github.com/JunHossain/MuteTeammates (public, portfolio).
- **2026-07-12**: Roster now includes the user (riot.py no longer excludes
  self), so they get muted on death too. Untested in a live match so far.
