"""Local Riot client integration.

Talks to the Valorant client's local API (via valclient) to figure out
which match we're in and who our teammates are (agent -> IGN), and
downloads agent portrait icons from valorant-api.com for template matching.
"""

import logging
from pathlib import Path

import requests
from valclient.client import Client

log = logging.getLogger("riot")

AGENTS_URL = "https://valorant-api.com/v1/agents?isPlayableCharacter=true"


class RiotLocal:
    def __init__(self, region: str, template_dir):
        self.region = region
        self.template_dir = Path(template_dir)
        self.client = None
        self._agents = None  # agent uuid -> (displayName, displayIcon url)

    def connect(self):
        """Attach to the running Riot/Valorant client via its lockfile."""
        c = Client(region=self.region)
        c.activate()
        self.client = c
        log.info("Connected to local Riot client (puuid %s...)", c.puuid[:8])

    def _agent_meta(self):
        if self._agents is None:
            data = requests.get(AGENTS_URL, timeout=15).json()["data"]
            self._agents = {
                a["uuid"].lower(): (a["displayName"], a["displayIcon"])
                for a in data
            }
        return self._agents

    def _ensure_template(self, agent_name: str, icon_url: str) -> Path:
        """Download the agent's portrait icon once, cache it on disk."""
        self.template_dir.mkdir(parents=True, exist_ok=True)
        # "KAY/O" must not become a subdirectory
        path = self.template_dir / f"{agent_name.replace('/', '_')}.png"
        if not path.exists():
            r = requests.get(icon_url, timeout=15)
            r.raise_for_status()
            path.write_bytes(r.content)
            log.info("Downloaded template for %s", agent_name)
        return path

    def current_match_id(self):
        """Match ID if we're currently in a live game, else None."""
        try:
            return self.client.coregame_fetch_player()["MatchID"]
        except Exception:
            return None

    def get_teammates(self):
        """Roster of our whole team (including self) for the current match.

        Returns a list of {puuid, agent, ign, game_name} dicts.
        """
        meta = self._agent_meta()
        me = self.client.puuid
        match = self.client.coregame_fetch_match()
        players = match["Players"]

        my_team = next(p["TeamID"] for p in players if p["Subject"] == me)
        mates = [p for p in players if p["TeamID"] == my_team]

        names = self._resolve_names([p["Subject"] for p in mates])

        roster = []
        for p in mates:
            agent_name, icon_url = meta.get(p["CharacterID"].lower(), (None, None))
            if agent_name is None:
                log.warning("Unknown agent uuid %s", p["CharacterID"])
                continue
            self._ensure_template(agent_name, icon_url)
            n = names.get(p["Subject"], {})
            game_name = n.get("GameName", "")
            tag = n.get("TagLine", "")
            ign = f"{game_name}#{tag}" if game_name else p["Subject"][:8]
            roster.append({
                "puuid": p["Subject"],
                "agent": agent_name,
                "ign": ign,
                "game_name": game_name,
            })
        return roster

    def _resolve_names(self, puuids):
        """puuid -> {GameName, TagLine} via the name service endpoint."""
        try:
            res = self.client.put(
                endpoint="/name-service/v2/players",
                endpoint_type="pd",
                json_data=puuids,
            )
            return {e["Subject"]: e for e in res}
        except Exception as e:
            log.warning("Name service lookup failed: %s", e)
            return {}
