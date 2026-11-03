"""Engineering-only RAG preview: prints retrieved evidence, never sends messages."""

import argparse
import json

from app.knowledge.embeddings import LocalE5
from app.knowledge.retrieval import KnowledgeIndex

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question")
    parser.add_argument("--model-dir", default=".local/knowledge-models/e5-small")
    parser.add_argument("--db", default=".local/knowledge-rag/preview.sqlite3")
    parser.add_argument("--bundle", default="docs/knowledge/a1-reviewed-segments.json")
    parser.add_argument(
        "--document", required=True, help="Exact original SHA-256; internal preview only"
    )
    parser.add_argument("--build", action="store_true")
    args = parser.parse_args()
    index = KnowledgeIndex(args.db, args.bundle, LocalE5(args.model_dir))
    if args.build:
        index.build()
    print(
        json.dumps(
            {
                "scope": "engineering_preview_not_customer_response",
                "evidence": index.search_preview(args.question, document_sha256=args.document),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
