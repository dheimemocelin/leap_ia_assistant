"""Extract review candidates from official model-page components, never approve them."""

import hashlib
import json
import re
from html import unescape
from html.parser import HTMLParser

from app.catalog.media_library import norm
from app.policy.commercial import CommercialPolicyEngine

ALLOWED_PAGES = {
    "https://www.leapmotor.com.br/b10.html",
    "https://www.leapmotor.com.br/c10.html",
}


def plain_text(value):
    return " ".join(unescape(re.sub(r"<[^>]*>", " ", value)).split())


def extract_candidates(html: str, *, url: str, retrieved_at: str):
    if url not in ALLOWED_PAGES:
        raise ValueError("Only configured official Brazilian model pages are permitted")
    records = []

    def visit(item, title):
        if isinstance(item, list):
            for child in item:
                visit(child, title)
        elif isinstance(item, dict):
            text = plain_text(item.get("text", ""))
            if text and CommercialPolicyEngine().validate_output(text):
                records.append(
                    {
                        "section": title,
                        "title": plain_text(item.get("title", "")),
                        "text": text,
                        "sha256": hashlib.sha256(text.encode()).hexdigest(),
                        "approval_status": "pending_review",
                    }
                )
            for key, value in item.items():
                if key not in {"text", "title", "buttons"} and isinstance(value, (dict, list)):
                    visit(value, title)

    # Walk all sections rather than depending on a private nested layout.
    class Extractor(HTMLParser):
        def handle_starttag(self, tag, attrs):
            if tag != "prox-master-all-features":
                return
            value = dict(attrs).get("items")
            if value:
                for section in json.loads(value):
                    title = plain_text(section.get("title", ""))
                    if not re.search("garantia|servico", norm(title)):
                        visit(section, title)

    Extractor().feed(html)
    if not records:
        raise ValueError("No technical component records found; page layout may have changed")
    return {
        "url": url,
        "retrieved_at": retrieved_at,
        "page_sha256": hashlib.sha256(html.encode()).hexdigest(),
        "approval_status": "pending_review",
        "records": records,
    }
