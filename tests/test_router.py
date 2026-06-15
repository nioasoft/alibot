import datetime

from bot.config import DestinationConfig
from bot.models import PublishQueueItem
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


def _fb_router(session=None) -> DestinationRouter:
    return DestinationRouter(
        {
            "tg_main": DestinationConfig("tg_main", True, "telegram", "@main", ["*"]),
            "wa_tech": DestinationConfig("wa_tech", True, "whatsapp", "120@g.us", ["tech"]),
            "fb_a": DestinationConfig("fb_a", True, "facebook", "https://fb/g/a", ["*"]),
            "fb_b": DestinationConfig("fb_b", True, "facebook", "https://fb/g/b", ["*"]),
            "fb_c": DestinationConfig("fb_c", True, "facebook", "https://fb/g/c", ["*"]),
        },
        session=session,
    )


def _enqueue_fb(session, target_ref: str) -> None:
    # unique (deal_id, destination_key) per row to satisfy the table constraint
    next_deal_id = (
        session.query(PublishQueueItem).count() + 1
    )
    session.add(
        PublishQueueItem(
            deal_id=next_deal_id,
            target_group=target_ref,
            destination_key=f"{target_ref}#{next_deal_id}",
            platform="facebook",
            target_ref=target_ref,
            status="queued",
            priority=0,
            scheduled_after=datetime.datetime.now(datetime.UTC),
        )
    )
    session.commit()


def test_rotation_collapses_facebook_to_single_destination(db_session):
    router = _fb_router(db_session)

    result = router.resolve_with_rotation("tech")

    fb = [d for d in result if d.platform == "facebook"]
    non_fb = [d for d in result if d.platform != "facebook"]
    # non-facebook destinations are untouched...
    assert {d.key for d in non_fb} == {"tg_main", "wa_tech"}
    # ...but only ONE facebook group is selected per deal.
    assert len(fb) == 1


def test_rotation_prefers_least_recently_used_group(db_session):
    router = _fb_router(db_session)
    # fb_a and fb_b already have queue items; fb_c has none -> fb_c is most idle.
    _enqueue_fb(db_session, "https://fb/g/a")
    _enqueue_fb(db_session, "https://fb/g/b")

    result = router.resolve_with_rotation("tech")
    fb = [d for d in result if d.platform == "facebook"]

    assert [d.key for d in fb] == ["fb_c"]


def test_rotation_spreads_across_groups_over_consecutive_deals(db_session):
    router = _fb_router(db_session)
    picks = []
    for _ in range(3):
        result = router.resolve_with_rotation("tech")
        chosen = next(d for d in result if d.platform == "facebook")
        picks.append(chosen.key)
        _enqueue_fb(db_session, chosen.target)  # simulate the enqueue

    # three consecutive deals hit three distinct groups (full rotation, no repeats).
    assert sorted(picks) == ["fb_a", "fb_b", "fb_c"]


def test_rotation_without_session_keeps_all_facebook(db_session=None):
    router = _fb_router(session=None)
    result = router.resolve_with_rotation("tech")
    fb = [d for d in result if d.platform == "facebook"]
    assert len(fb) == 3  # no session -> backward-compatible (all groups)


def test_resolve_is_unchanged_and_pure(db_session):
    router = _fb_router(db_session)
    # plain resolve() still returns every matching destination (no collapsing).
    result = router.resolve("tech")
    assert len([d for d in result if d.platform == "facebook"]) == 3
