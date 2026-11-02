"""Download only configured official pages into pending local review candidates.

Usage: python3 -m scripts.extract_official_catalog --output .local/knowledge-candidates
No LLM, approval, database writes or runtime catalog replacement.
"""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from app.catalog.official_import import ALLOWED_PAGES, extract_candidates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".local/knowledge-candidates"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=25, follow_redirects=False, trust_env=False) as client:
        for url in sorted(ALLOWED_PAGES):
            with client.stream("GET", url) as response:
                response.raise_for_status()
                chunks = bytearray()
                for chunk in response.iter_bytes():
                    chunks.extend(chunk)
                    if len(chunks) > 2_000_000:
                        raise ValueError("Official page exceeds extraction size limit")
            data = extract_candidates(
                chunks.decode("utf-8"), url=url, retrieved_at=datetime.now(UTC).isoformat()
            )
            destination = args.output / (url.rsplit("/", 1)[1].replace(".html", "") + ".json")
            destination.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
            print(f"{destination.name}: {len(data['records'])} pending technical records")


if __name__ == "__main__":
    main()
