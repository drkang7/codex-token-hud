"""Print a range report in a terminal, without a desktop or browser."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from history import HistoryCache, SessionCatalog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-home", type=Path, default=Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex"))
    parser.add_argument("--log", type=Path, action="append", default=[])
    parser.add_argument("--thread", default="")
    parser.add_argument("--list", action="store_true", help="List local conversation IDs")
    parser.add_argument("--messages", metavar="TEXT", help="Find user messages and print their stable IDs")
    parser.add_argument("--start", help="ISO start time, preferably with timezone")
    parser.add_argument("--end", help="ISO end time, preferably with timezone")
    parser.add_argument("--first", help="First user message ID from --messages")
    parser.add_argument("--last", help="Last user message ID; its responses are included")
    args = parser.parse_args()
    catalog = SessionCatalog(args.codex_home, args.log)
    catalog.refresh(force=True)
    if args.list:
        value = [{k: r.get(k) for k in ("id", "title", "model", "segment_count")} for r in catalog.rows.values()]
    else:
        thread = args.thread or (next(iter(catalog.rows)) if len(catalog.rows) == 1 else "")
        if thread not in catalog.rows:
            parser.error("Specify --thread from --list (or --log for one conversation).")
        history = HistoryCache().load(catalog, thread)
        if args.messages is not None:
            value = history.find_messages(args.messages)
        else:
            selection = {"mode": "messages", "first_id": args.first, "last_id": args.last} if args.first or args.last else {
                "mode": "time", "start": args.start, "end": args.end}
            try:
                value = history.calculate(selection)
            except ValueError as error:
                parser.error(str(error))
    print(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2))


if __name__ == "__main__":
    main()
