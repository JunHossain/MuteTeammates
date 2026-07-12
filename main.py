"""MuteTeammates — mute your dead Valorant teammates in Discord.

Usage:
  python main.py                 run the tool
  python main.py --capture       save the HUD strip screenshot (tune vision.region)
  python main.py --test-riot     print current match roster (must be in a match)
  python main.py --test-vision   print per-agent match scores (must be in a match)
"""

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_config():
    with open(ROOT / "config.json", encoding="utf-8") as f:
        return json.load(f)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)-7s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--capture", nargs="?", const="strip.png", metavar="FILE",
                    help="save a screenshot of the configured HUD region and exit")
    ap.add_argument("--test-riot", action="store_true",
                    help="connect to the local Riot client and print the roster")
    ap.add_argument("--test-vision", action="store_true",
                    help="print template-match scores for the current roster")
    ap.add_argument("--delay", type=int, default=5, metavar="SECS",
                    help="countdown before capturing, so you can Alt+Tab back "
                         "into Valorant (default: 5)")
    args = ap.parse_args()

    cfg = load_config()

    from vision import Vision
    from riot import RiotLocal

    vision = Vision(cfg["vision"], ROOT / "templates")
    riot = RiotLocal(cfg["riot"]["region"], ROOT / "templates")

    def countdown():
        if args.delay > 0:
            import time
            print(f"Alt+Tab back into Valorant - capturing in {args.delay}s...")
            for i in range(args.delay, 0, -1):
                print(f"  {i}...")
                time.sleep(1)

    if args.capture:
        import cv2
        countdown()
        img = vision.capture_color()
        cv2.imwrite(args.capture, img)
        print(f"Saved {args.capture} ({img.shape[1]}x{img.shape[0]}px).")
        print("Open it and check all 5 teammate portraits are fully inside; "
              "adjust vision.region in config.json if not.")
        return

    if args.test_riot or args.test_vision:
        riot.connect()
        roster = riot.get_teammates()
        if not roster:
            sys.exit("No teammates found — are you in a live match?")
        print("Teammates this match:")
        for p in roster:
            print(f"  {p['agent']:<12} {p['ign']}")
        if args.test_vision:
            print()
            countdown()
            sc = vision.scores([p["agent"] for p in roster])
            for agent, score in sc.items():
                state = "ALIVE" if score >= vision.threshold else "DEAD"
                print(f"  {agent:<12} score={score:.2f}  -> {state}")
            print(f"\n(threshold = {vision.threshold}; tune in config.json)")
        return

    token = cfg["discord"]["bot_token"]
    if not token or token.startswith("PASTE"):
        sys.exit("Set discord.bot_token in config.json first (see README.md).")
    if not int(cfg["discord"]["guild_id"]):
        sys.exit("Set discord.guild_id in config.json first (see README.md).")

    from bot import MuteBot
    bot = MuteBot(cfg, riot, vision)
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()
