"""Offline audit: python -m app.knowledge --input DIR --output .local/knowledge."""

import argparse
import json
from pathlib import Path

from app.knowledge.catalog import catalog_files
from app.knowledge.models import MetadataReview


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--metadata-reviews", type=Path)
    args = parser.parse_args()
    if not args.input.is_dir():
        parser.error("Input directory does not exist")
    if args.output.resolve() == args.input.resolve() or args.output.resolve().is_relative_to(
        args.input.resolve()
    ):
        parser.error("Output must be outside input directory")
    files = sorted(args.input.glob("*.pdf"))
    reviews = (
        [MetadataReview.model_validate(r) for r in json.loads(args.metadata_reviews.read_text())]
        if args.metadata_reviews
        else []
    )
    report = catalog_files(files, args.output, metadata_reviews=reviews)
    print(json.dumps({k: v for k, v in report.items() if k != "documents"}))
    return 0 if report["unique_documents"] == 6 and not report["errors"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
