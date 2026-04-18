from __future__ import annotations

import datetime
from pathlib import Path

import pytest
import respx
from httpx import Response

from bot.facebook_publisher import FacebookPublisher
from bot.models import Deal


def _make_deal() -> Deal:
    return Deal(
        id=1,
        raw_message_id=1,
        product_id="1005001",
        product_name="Sample Deal",
        original_text="orig",
        rewritten_text="rewritten",
        price=49.9,
        original_price=None,
        currency="ILS",
        shipping=None,
        category="tech",
        ali_category_raw=None,
        category_source=None,
        affiliate_account_key=None,
        affiliate_link="https://s.click.aliexpress.com/e/_sample",
        product_link="https://www.aliexpress.com/item/1005001.html",
        image_hash=None,
        image_path="/tmp/sample.jpg",
        text_hash="hash",
        source_group="@source",
        created_at=datetime.datetime.now(datetime.UTC),
    )


@pytest.mark.asyncio
async def test_send_deal_includes_image_path_and_updated_site_text() -> None:
    publisher = FacebookPublisher(
        service_url="http://facebook.test",
        site_url="https://www.dilim.net/",
    )

    with respx.mock(assert_all_called=True) as router:
        route = router.post("http://facebook.test/publish").mock(
            return_value=Response(200, json={"ok": True})
        )

        ok = await publisher.send_deal(
            deal=_make_deal(),
            group_url="https://www.facebook.com/groups/test",
        )

    assert ok is True
    payload = route.calls[0].request.content.decode()
    assert f'"image_path":"{Path("/tmp/sample.jpg").resolve()}"' in payload
    assert '"text":"rewritten"' in payload
    assert '"append_text":"\\n\\n🌐 להצטרפות לקבוצות לפי תחומי עניין: https://www.dilim.net\\n🛒 לרכישה: https://s.click.aliexpress.com/e/_sample"' in payload
    assert "הצטרפות לקבוצות לפי תחומי עניין" in payload
