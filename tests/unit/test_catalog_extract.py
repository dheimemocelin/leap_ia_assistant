from app.catalog.extract import extract_media_drafts


def test_extracts_image_inventory_without_fetching_or_approving_assets() -> None:
    html = '''<img src="/assets/c10.jpg" alt="C10 exterior frontal">
              <img data-src="https://cdn.example/interior.jpg" alt="Interior painel e volante">
              <img src="/assets/c10.jpg" alt="duplicate">'''
    rows = extract_media_drafts(
        html,
        page_url="https://www.leapmotor.com.br/c10.html",
        vehicle_id="c10-bev",
        retrieved_at="2026-10-29T00:00:00Z",
        rights_basis="pending rights review",
    )
    assert len(rows) == 2
    assert str(rows[0].source_url) == "https://www.leapmotor.com.br/assets/c10.jpg"
    assert rows[0].approval_status == "pending_review"
    assert rows[1].category == "dashboard"
    assert all(row.storage_uri is None for row in rows)
