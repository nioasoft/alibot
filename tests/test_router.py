from bot.config import DestinationConfig
from bot.router import DestinationRouter


def test_router_matches_multiple_destinations():
    router = DestinationRouter(
        {
            "tg_main": DestinationConfig("tg_main", True, "telegram", "@main", ["*"]),
            "tg_tech": DestinationConfig("tg_tech", True, "telegram", "@tech", ["tech"]),
            "wa_home": DestinationConfig("wa_home", True, "whatsapp", "120@g.us", ["home"]),
        }
    )

    matches = router.resolve("tech")

    assert [match.key for match in matches] == ["tg_main", "tg_tech"]
