"""Show local pilot counts without printing names, contacts, or conversation content."""

import argparse
import json
import sqlite3
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path(".local/pilot.sqlite3"))
    args = parser.parse_args()
    if not args.db.is_file():
        parser.error("Pilot database does not exist")
    with sqlite3.connect(f"{args.db.resolve().as_uri()}?mode=ro", uri=True) as db:
        counts = {
            name: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for name, table in [
                ("people", "pilot_people"),
                ("conversations", "pilot_threads"),
                ("opportunities", "pilot_opportunities"),
            ]
        }
    print(json.dumps(counts))


if __name__ == "__main__":
    main()
