"""Fallback pool for AliExpress catalog operations across multiple accounts."""

from __future__ import annotations


class AliExpressClientPool:
    def __init__(self, clients: dict[str, object], preferred_key: str = "primary"):
        self._clients = clients
        self._preferred_key = preferred_key

    @property
    def is_enabled(self) -> bool:
        return any(getattr(client, "is_enabled", False) for client in self._clients.values())

    def _ordered_clients(self) -> list[object]:
        ordered: list[object] = []

        preferred = self._clients.get(self._preferred_key)
        if preferred is not None and getattr(preferred, "is_enabled", False):
            ordered.append(preferred)

        for key, client in self._clients.items():
            if key == self._preferred_key:
                continue
            if getattr(client, "is_enabled", False):
                ordered.append(client)

        return ordered

    def get_product_details(self, product_id: str):
        for client in self._ordered_clients():
            details = client.get_product_details(product_id)
            if details:
                return details
        return None

    def search_products(self, *args, **kwargs) -> list:
        for client in self._ordered_clients():
            products = client.search_products(*args, **kwargs)
            if products:
                return products
        return []

    def download_image(self, image_url: str):
        for client in self._ordered_clients():
            image = client.download_image(image_url)
            if image:
                return image
        return None
