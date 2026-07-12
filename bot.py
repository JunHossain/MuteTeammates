"""Discord bot: server-mutes dead players on your team (you included)
on a mouse side-button toggle.

One asyncio process. A pynput listener thread pushes toggle events into the
bot's event loop. A background task polls the local Riot API and refreshes
the roster (agent -> IGN) whenever a new match starts.
"""

import asyncio
import logging

import discord
from pynput import mouse

log = logging.getLogger("bot")

BUTTONS = {
    "x1": mouse.Button.x1,
    "x2": mouse.Button.x2,
    "middle": mouse.Button.middle,
}

ROSTER_POLL_SECONDS = 15


class MuteBot(discord.Client):
    def __init__(self, cfg: dict, riot, vision):
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(intents=intents)
        self.cfg = cfg
        self.riot = riot
        self.vision = vision
        # IGN (lowercase, with or without #TAG) -> discord user id / username
        self.player_map = {str(k).lower(): v for k, v in cfg["players"].items()}
        self.roster = {}  # agent name -> {ign, game_name, ...}
        self.match_id = None
        self.guild = None
        self.muted: list[discord.Member] = []
        self._toggle_lock = asyncio.Lock()
        self._unmute_timer = None

    # ---------- lifecycle ----------

    async def setup_hook(self):
        self._loop = asyncio.get_running_loop()
        self._start_mouse_listener()
        self._roster_task = asyncio.create_task(self._roster_loop())

    async def on_ready(self):
        self.guild = self.get_guild(int(self.cfg["discord"]["guild_id"]))
        if self.guild is None:
            log.error("Bot is not in guild %s — check guild_id / invite.",
                      self.cfg["discord"]["guild_id"])
            await self.close()
            return
        await self.guild.chunk()
        log.info("Logged in as %s | guild: %s | press %s to toggle mute",
                 self.user, self.guild.name, self.cfg.get("mouse_button", "x2"))

    async def close(self):
        try:
            await self._unmute_all()
        finally:
            await super().close()

    # ---------- mouse trigger ----------

    def _start_mouse_listener(self):
        name = self.cfg.get("mouse_button", "x2")
        btn = BUTTONS.get(name)
        if btn is None:
            raise ValueError(f"Unknown mouse_button {name!r}; use one of {list(BUTTONS)}")

        def on_click(x, y, button, pressed):
            if pressed and button == btn:
                asyncio.run_coroutine_threadsafe(self.toggle(), self._loop)

        self._listener = mouse.Listener(on_click=on_click)
        self._listener.daemon = True
        self._listener.start()

    # ---------- roster refresh ----------

    async def _roster_loop(self):
        await self.wait_until_ready()
        connected = False
        while not self.is_closed():
            try:
                if not connected:
                    await asyncio.to_thread(self.riot.connect)
                    connected = True
                mid = await asyncio.to_thread(self.riot.current_match_id)
                if mid and mid != self.match_id:
                    mates = await asyncio.to_thread(self.riot.get_teammates)
                    self.roster = {p["agent"]: p for p in mates}
                    self.match_id = mid
                    log.info("New match — roster: %s",
                             {a: p["ign"] for a, p in self.roster.items()})
                elif not mid and self.match_id:
                    log.info("Match ended.")
                    self.match_id = None
                    self.roster = {}
            except Exception as e:
                log.debug("Riot poll failed (%s) — will retry.", e)
                connected = False  # Riot client may have restarted
            await asyncio.sleep(ROSTER_POLL_SECONDS)

    # ---------- mute logic ----------

    async def toggle(self):
        async with self._toggle_lock:
            if self.muted:
                await self._unmute_all()
                return
            if not self.roster:
                log.warning("No roster yet (not in a match?) — nothing to do.")
                return

            dead = await asyncio.to_thread(
                self.vision.dead_agents, list(self.roster))
            if not dead:
                log.info("Nobody's dead. Lucky them.")
                return

            for agent in dead:
                player = self.roster[agent]
                member = self._find_member(player)
                if member is None:
                    log.warning("%s (%s) not mapped/found in Discord — skipped.",
                                player["ign"], agent)
                    continue
                if member.voice is None:
                    log.warning("%s is not in a voice channel — skipped.",
                                member.display_name)
                    continue
                try:
                    await member.edit(mute=True, reason="MuteTeammates: dead")
                    self.muted.append(member)
                    log.info("Muted %s (%s / %s)",
                             member.display_name, player["ign"], agent)
                except discord.HTTPException as e:
                    log.error("Failed to mute %s: %s", member.display_name, e)

            secs = int(self.cfg.get("auto_unmute_seconds", 0))
            if self.muted and secs > 0:
                self._unmute_timer = asyncio.create_task(self._auto_unmute(secs))

    async def _auto_unmute(self, secs):
        await asyncio.sleep(secs)
        async with self._toggle_lock:
            await self._unmute_all()

    async def _unmute_all(self):
        if self._unmute_timer and not self._unmute_timer.done():
            self._unmute_timer.cancel()
        self._unmute_timer = None
        for member in self.muted:
            try:
                await member.edit(mute=False, reason="MuteTeammates: unmute")
                log.info("Unmuted %s", member.display_name)
            except discord.HTTPException as e:
                log.error("Failed to unmute %s: %s", member.display_name, e)
        self.muted.clear()

    # ---------- discord member resolution ----------

    def _find_member(self, player):
        key = (self.player_map.get(player["ign"].lower())
               or self.player_map.get(player["game_name"].lower()))
        if key is None:
            return None
        if isinstance(key, int) or str(key).isdigit():
            return self.guild.get_member(int(key))
        k = str(key).lower()
        for m in self.guild.members:
            names = {m.name.lower(), m.display_name.lower(),
                     (m.global_name or "").lower()}
            if k in names:
                return m
        return None
