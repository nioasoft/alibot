from types import SimpleNamespace

from bot.quality import QualityGate
from bot.source_intelligence import SourceReputation


def test_source_reputation_boost_can_push_deal_over_threshold():
    gate = QualityGate(
        min_score_external=70,
        source_reputation_enabled=True,
        source_reputation_boost_max=12,
        source_reputation_penalty_max=18,
    )
    gate.set_source_reputations(
        {
            "@strong": SourceReputation(
                source_group="@strong",
                score=90,
                links=10,
                clicks=18,
                clicked_links=7,
                avg_clicks_per_link=1.8,
                click_coverage_rate=0.7,
            )
        }
    )

    decision = gate.evaluate_pipeline(
        source_group="@strong",
        ali_details=SimpleNamespace(
            orders_count=50,
            rating=4.6,
            price=100.0,
            sale_price=85.0,
            app_sale_price=None,
            images=["img"],
        ),
        category_source="api",
        affiliate_link_ready=True,
        has_image=True,
    )

    assert decision.accepted is True
    assert decision.score > 70
    assert decision.reason == "quality_pass_source_boost"


def test_source_reputation_penalty_can_reject_borderline_deal():
    gate = QualityGate(
        min_score_external=70,
        source_reputation_enabled=True,
        source_reputation_boost_max=12,
        source_reputation_penalty_max=18,
    )
    gate.set_source_reputations(
        {
            "@weak": SourceReputation(
                source_group="@weak",
                score=10,
                links=9,
                clicks=0,
                clicked_links=0,
                avg_clicks_per_link=0.0,
                click_coverage_rate=0.0,
            )
        }
    )

    decision = gate.evaluate_pipeline(
        source_group="@weak",
        ali_details=SimpleNamespace(
            orders_count=50,
            rating=4.4,
            price=100.0,
            sale_price=80.0,
            app_sale_price=None,
            images=["img"],
        ),
        category_source="api",
        affiliate_link_ready=True,
        has_image=True,
    )

    assert decision.accepted is False
    assert decision.score < 70
    assert decision.reason == "quality_below_threshold_source_penalty"
