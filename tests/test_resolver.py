import pytest
import httpx
import respx

from bot.resolver import LinkResolver


@pytest.fixture
def resolver():
    return LinkResolver()


@pytest.mark.asyncio
class TestLinkResolver:
    async def test_resolve_short_link_to_product_id(self, resolver: LinkResolver):
        short_url = "https://s.click.aliexpress.com/e/_oEhUSd4"
        final_url = "https://www.aliexpress.com/item/1005003091506814.html?algo_pvid=abc"

        with respx.mock:
            respx.get(short_url).mock(
                return_value=httpx.Response(
                    302,
                    headers={"Location": final_url},
                )
            )
            respx.get(final_url).mock(
                return_value=httpx.Response(200)
            )

            product_id = await resolver.resolve(short_url)

        assert product_id == "1005003091506814"

    async def test_direct_link_extracts_product_id(self, resolver: LinkResolver):
        url = "https://www.aliexpress.com/item/1005006789012345.html"
        product_id = await resolver.resolve(url)
        assert product_id == "1005006789012345"

    async def test_timeout_returns_none(self, resolver: LinkResolver):
        short_url = "https://s.click.aliexpress.com/e/_timeout"

        with respx.mock:
            respx.get(short_url).mock(side_effect=httpx.ReadTimeout("timeout"))

            product_id = await resolver.resolve(short_url)

        assert product_id is None

    async def test_cache_avoids_second_request(self, resolver: LinkResolver):
        short_url = "https://s.click.aliexpress.com/e/_cached"
        final_url = "https://www.aliexpress.com/item/9999999999.html"

        with respx.mock:
            route = respx.get(short_url).mock(
                return_value=httpx.Response(
                    302,
                    headers={"Location": final_url},
                )
            )
            respx.get(final_url).mock(return_value=httpx.Response(200))

            await resolver.resolve(short_url)
            await resolver.resolve(short_url)

        assert route.call_count == 1

    async def test_non_aliexpress_redirect_returns_none(self, resolver: LinkResolver):
        short_url = "https://s.click.aliexpress.com/e/_weird"
        final_url = "https://some-other-site.com/page"

        with respx.mock:
            respx.get(short_url).mock(
                return_value=httpx.Response(
                    302,
                    headers={"Location": final_url},
                )
            )
            respx.get(final_url).mock(return_value=httpx.Response(200))

            product_id = await resolver.resolve(short_url)

        assert product_id is None
