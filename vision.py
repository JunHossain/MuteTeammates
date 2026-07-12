"""Screen vision: is each teammate's agent portrait present in the HUD strip?

The top-center-left HUD strip shows one portrait per *living* ally,
your own included. Dead allies' portraits are removed (survivors may
reflow), so we don't
track slots at all — we just template-match each roster agent against the
whole strip. Present = alive, absent = dead.

Two details matter a lot for reliable scores (measured on real captures):

* Background: the agent icons have transparent backgrounds, but in the HUD
  they're drawn over a translucent band whose color depends on the map and
  lighting. Compositing each template onto the *median color of the
  captured strip* (instead of a fixed color) makes present agents score
  ~0.95 while absent ones stay below ~0.55, on bright and dark maps alike.
* Scale: at 1920x1080 the portraits render at exactly 40px. A few px off
  drops the score fast, so scales stay close around template_size.
"""

import logging
from pathlib import Path

import cv2
import mss
import numpy as np

log = logging.getLogger("vision")


class Vision:
    def __init__(self, cfg: dict, template_dir):
        self.region = cfg["region"]  # {left, top, width, height} in pixels
        self.size = int(cfg.get("template_size", 40))
        self.scales = cfg.get("scales", [0.95, 1.0, 1.05])
        self.threshold = float(cfg.get("threshold", 0.75))
        self.template_dir = Path(template_dir)
        self._icons = {}  # agent -> (bgr float32, alpha float32 in 0..1)

    def capture_color(self):
        with mss.mss() as sct:
            img = np.array(sct.grab(self.region))
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    def _icon(self, agent: str):
        if agent not in self._icons:
            # "KAY/O" must not become a subdirectory
            path = self.template_dir / f"{agent.replace('/', '_')}.png"
            img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
            if img is None:
                raise FileNotFoundError(f"Missing template: {path}")
            if img.ndim == 3 and img.shape[2] == 4:
                bgr = img[:, :, :3].astype(np.float32)
                alpha = img[:, :, 3:].astype(np.float32) / 255.0
            else:
                bgr = img[:, :, :3].astype(np.float32)
                alpha = np.ones(bgr.shape[:2] + (1,), np.float32)
            self._icons[agent] = (bgr, alpha)
        return self._icons[agent]

    def scores(self, agents, strip=None):
        """Best match score per agent across configured scales."""
        if strip is None:
            strip = self.capture_color()
        h, w = strip.shape[:2]
        # HUD band color right now (adapts to map/lighting per capture)
        bg = np.median(strip.reshape(-1, 3), axis=0).astype(np.float32)
        out = {}
        for agent in agents:
            bgr, alpha = self._icon(agent)
            comp = (bgr * alpha + bg * (1.0 - alpha)).astype(np.uint8)
            best = 0.0
            for s in self.scales:
                px = max(8, int(round(self.size * s)))
                if px >= h or px >= w:
                    continue
                tmpl = cv2.resize(comp, (px, px),
                                  interpolation=cv2.INTER_AREA)
                res = cv2.matchTemplate(strip, tmpl, cv2.TM_CCOEFF_NORMED)
                best = max(best, float(res.max()))
            out[agent] = best
        return out

    def dead_agents(self, agents):
        """Agents from the roster whose portrait is NOT on screen right now."""
        sc = self.scores(agents)
        dead = [a for a, v in sc.items() if v < self.threshold]
        log.info("Scores: %s -> dead: %s",
                 {a: round(v, 2) for a, v in sc.items()}, dead or "none")
        return dead
