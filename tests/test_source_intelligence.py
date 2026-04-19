from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from bot.source_intelligence import SourceIntelligence


def test_refresh_builds_source_reputations_from_tracking_links():
    with patch("bot.source_intelligence.create_client") as mock_create_client:
        client = MagicMock()
        client.table().select().order().range().execute.side_effect = [
            SimpleNamespace(
                data=[
                    {"source_group": "@alpha", "click_count": 4},
                    {"source_group": "@alpha", "click_count": 0},
                    {"source_group": "@beta", "click_count": 0},
                    {"source_group": "@beta", "click_count": 0},
                ]
            ),
            SimpleNamespace(data=[]),
        ]
        mock_create_client.return_value = client

        intelligence = SourceIntelligence(
            url="https://test.supabase.co",
            key="service-key",
            max_rows=5000,
            min_links=2,
        )

        reputations = intelligence.refresh()

    assert set(reputations) == {"@alpha", "@beta"}
    assert reputations["@alpha"].clicks == 4
    assert reputations["@alpha"].links == 2
    assert reputations["@alpha"].score > reputations["@beta"].score


def test_refresh_skips_sources_below_minimum_link_threshold():
    with patch("bot.source_intelligence.create_client") as mock_create_client:
        client = MagicMock()
        client.table().select().order().range().execute.side_effect = [
            SimpleNamespace(data=[{"source_group": "@alpha", "click_count": 1}]),
            SimpleNamespace(data=[]),
        ]
        mock_create_client.return_value = client

        intelligence = SourceIntelligence(
            url="https://test.supabase.co",
            key="service-key",
            max_rows=5000,
            min_links=2,
        )

        reputations = intelligence.refresh()

    assert reputations == {}
