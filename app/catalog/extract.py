"""Draft-only extraction of image inventory from an authorized product page snapshot."""

from html.parser import HTMLParser
from urllib.parse import urljoin

from app.catalog.models import ApprovalStatus, MediaCategory, VehicleMedia


class _ImageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.images: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "img":
            return
        values = dict(attrs)
        src = values.get("src") or values.get("data-src")
        alt = values.get("alt") or ""
        if src:
            self.images.append((src, alt))


def _category(alt: str) -> MediaCategory:
    text = alt.casefold()
    if any(token in text for token in ("porta-malas", "porta malas", "bagageiro")):
        return MediaCategory.TRUNK
    if any(token in text for token in ("painel", "cockpit", "volante", "central multimídia")):
        return MediaCategory.DASHBOARD
    if any(token in text for token in ("interior", "bancos", "banco", "teto panorâmico")):
        return MediaCategory.INTERIOR
    if any(token in text for token in ("detalhe", "farol", "lanterna", "roda")):
        return MediaCategory.DETAIL
    return MediaCategory.EXTERIOR


def extract_media_drafts(
    html: str,
    *,
    page_url: str,
    vehicle_id: str,
    retrieved_at: str,
    rights_basis: str,
) -> list[VehicleMedia]:
    """Create review-required media records; never fetches or stores image bytes."""
    parser = _ImageParser()
    parser.feed(html)
    result = []
    seen: set[str] = set()
    for index, (src, alt) in enumerate(parser.images):
        image_url = urljoin(page_url, src)
        if image_url in seen:
            continue
        seen.add(image_url)
        result.append(
            VehicleMedia(
                id=f"{vehicle_id}-media-{index + 1}",
                vehicle_id=vehicle_id,
                category=_category(alt),
                source_url=image_url,
                rights_basis=rights_basis,
                provenance=f"Extracted from {page_url}; alt={alt[:300]}",
                retrieved_at=retrieved_at,
                approval_status=ApprovalStatus.PENDING_REVIEW,
            )
        )
    return result
