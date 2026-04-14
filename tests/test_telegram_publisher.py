from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.config import InviteLinkConfig
from bot.telegram_publisher import TelegramPublisher


@pytest.mark.asyncio
async def test_send_deal_uses_rotating_invite_footer():
    client = MagicMock()
    client.send_message = AsyncMock(return_value=MagicMock(id=123))

    publisher = TelegramPublisher(
        client=client,
        site_url="https://www.dilim.net/",
        invite_links=[
            InviteLinkConfig(
                url="https://chat.whatsapp.com/test",
                label="קבוצת טסט",
                platform="whatsapp",
                footer_label="💬 להצטרפות לקבוצת הוואטסאפ",
            )
        ],
    )

    message_id = await publisher.send_deal(
        target_ref="@target",
        text="דיל לדוגמה",
        link="https://s.click.aliexpress.com/e/_test",
        deal_id=5,
    )

    assert message_id == 123
    sent_text = client.send_message.await_args.args[1]
    assert "🛒 לרכישה: https://s.click.aliexpress.com/e/_test" in sent_text
    assert "💬 להצטרפות לקבוצת הוואטסאפ: https://chat.whatsapp.com/test" in sent_text
    assert sent_text.endswith("🌐 להצטרפות לכל הקבוצות: https://www.dilim.net/")
