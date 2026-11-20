from datetime import date, datetime
from importlib.util import find_spec

from app.core.tenant_context import tenant_scope
from app.models import Creative
from app.services.creative_intelligence_service import CreativeIntelligenceService
from app.services.visual_creative_analysis_service import VisualCreativeAnalysisService


def register(client, email):
    return client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "correct-horse-battery-staple",
            "business_name": email.split("@")[0],
        },
    )


def headers(auth):
    return {
        "Authorization": f"Bearer {auth.json()['access_token']}",
        "X-Business-ID": str(auth.json()["business"]["id"]),
    }


def test_creative_listing_and_comparison_disclose_recorded_metrics_and_date_filter(api_client):
    auth = register(api_client, "creative-metrics@example.com")
    business_id = auth.json()["business"]["id"]
    with tenant_scope(business_id), api_client.session_factory() as db:
        db.add_all([
            Creative(creative_name="Recorded winner", platform="meta", spend=100,
                     revenue=300, roas=3, ctr=2.5, cpc=1.2,
                     created_at=datetime(2026, 7, 1)),
            Creative(creative_name="Zero defaults", platform="meta", spend=0,
                     revenue=0, roas=0, ctr=0, cpc=0,
                     created_at=datetime(2026, 8, 1)),
        ])
        db.commit()
        page = CreativeIntelligenceService.list_creatives(
            db, business_id, date(2026, 7, 1), date(2026, 7, 31)
        )
        comparison = CreativeIntelligenceService.compare(db, business_id, [1, 2, 999])

    assert page.total == 1
    assert page.creatives[0].source == "legacy creatives table"
    assert page.creatives[0].recorded_roas.amount == 3
    assert page.creatives[0].impressions is None
    assert page.best_recorded_roas_creative_id == page.creatives[0].creative_id
    zero = comparison.creatives[1]
    assert zero.recorded_roas.amount == 0
    assert zero.recorded_roas.available is False
    assert comparison.missing_creative_ids == [999]


def test_creative_api_requires_scope_and_hides_other_business_rows(api_client):
    owner = register(api_client, "creative-owner@example.com")
    other = register(api_client, "creative-other@example.com")
    business_id = owner.json()["business"]["id"]
    with tenant_scope(business_id), api_client.session_factory() as db:
        row = Creative(creative_name="Private creative", spend=10, revenue=25,
                       roas=2.5, ctr=1.4, cpc=0.8)
        db.add(row)
        db.commit()
        creative_id = row.id

    own = api_client.get("/intelligence/creatives", headers=headers(owner))
    cross_business = api_client.get(
        f"/intelligence/creatives/{creative_id}", headers=headers(other)
    )
    comparison = api_client.get(
        f"/intelligence/creatives/comparison?creative_ids={creative_id}",
        headers=headers(owner),
    )
    unauthenticated = api_client.get("/intelligence/creatives")

    assert own.status_code == 200
    assert own.json()["total"] == 1
    assert cross_business.status_code == 404
    assert comparison.status_code == 200
    assert unauthenticated.status_code == 401


def test_visual_service_handles_missing_unsupported_invalid_image_and_video():
    missing = VisualCreativeAnalysisService.analyze_image(None, None)
    unsupported_type = VisualCreativeAnalysisService.analyze_image(b"not-media", "text/plain")
    invalid_image = VisualCreativeAnalysisService.analyze_image(b"invalid", "image/png")
    video = VisualCreativeAnalysisService.analyze_video(b"video bytes")

    assert missing.status == "unavailable"
    assert unsupported_type.status == "unsupported"
    assert invalid_image.status in {"failed", "unavailable"}
    assert video.status == "unsupported"


def test_visual_service_analyzes_local_image_or_reports_optional_dependency_absence():
    # A tiny transparent PNG; no image file or private URL is persisted.
    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de"
        "0000000c49444154789c6310d1b0010000cc0079bd15c3af0000000049454e44ae426082"
    )
    result = VisualCreativeAnalysisService.analyze_image(png, "image/png")
    if find_spec("PIL"):
        assert result.status == "analyzed"
        assert result.width == 1 and result.height == 1
        assert result.aspect_ratio == 1
        assert result.dominant_colors
    else:
        assert result.status == "unavailable"
