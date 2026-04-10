"""Test AliExpress API — check hot products and campaigns."""

import sys
sys.path.insert(0, ".")

from dotenv import load_dotenv
load_dotenv()

from aliexpress_api import AliexpressApi, models as ali_models

from bot.config import load_config

config = load_config("config.yaml")

api = AliexpressApi(
    config.aliexpress.app_key,
    config.aliexpress.app_secret,
    ali_models.Language.EN,
    ali_models.Currency.USD,
    config.aliexpress.tracking_id,
)

print("=" * 60)
print("1. Hot Products (trending with high commission)")
print("=" * 60)

try:
    hot = api.get_hotproducts(
        category_ids="44",  # Consumer Electronics
        max_sale_price=2000,  # up to $20
        min_sale_price=100,   # at least $1
        page_size=5,
    )
    if hot and hot.products:
        for p in hot.products:
            title = getattr(p, "product_title", "?")
            price = getattr(p, "target_sale_price", "?")
            commission = getattr(p, "commission_rate", "?")
            orders = getattr(p, "lastest_volume", "?")
            link = getattr(p, "promotion_link", "?")
            print(f"\n  {title[:60]}")
            print(f"  Price: ${price} | Commission: {commission}% | Orders: {orders}")
            print(f"  Link: {str(link)[:80]}...")
    else:
        print("  No hot products returned")
except Exception as e:
    print(f"  ERROR: {e}")

print("\n" + "=" * 60)
print("2. Category list check")
print("=" * 60)

try:
    categories = api.get_categories()
    if categories:
        for cat in categories[:15]:
            cat_id = getattr(cat, "category_id", "?")
            name = getattr(cat, "category_name", "?")
            print(f"  {cat_id}: {name}")
    else:
        print("  No categories returned")
except Exception as e:
    print(f"  ERROR: {e}")

print("\n" + "=" * 60)
print("3. Affiliate link generation test")
print("=" * 60)

try:
    test_url = "https://www.aliexpress.com/item/1005007417628498.html"
    links = api.get_affiliate_links(test_url)
    if links:
        for link in links:
            print(f"  Original: {test_url}")
            print(f"  Affiliate: {link.promotion_link}")
    else:
        print("  No affiliate link returned (check API approval status)")
except Exception as e:
    print(f"  ERROR: {e}")

print("\n" + "=" * 60)
print("4. Product details test")
print("=" * 60)

try:
    products = api.get_products_details(["1005007417628498"])
    if products:
        p = products[0]
        print(f"  Title: {getattr(p, 'product_title', '?')}")
        print(f"  Price: ${getattr(p, 'target_original_price', '?')}")
        print(f"  Sale: ${getattr(p, 'target_sale_price', '?')}")
        print(f"  Rating: {getattr(p, 'evaluate_rate', '?')}")
        print(f"  Orders: {getattr(p, 'lastest_volume', '?')}")
        print(f"  Commission: {getattr(p, 'commission_rate', '?')}%")
        main_img = getattr(p, 'product_main_image_url', '?')
        print(f"  Main image: {str(main_img)[:80]}")
    else:
        print("  No product details returned")
except Exception as e:
    print(f"  ERROR: {e}")

print("\nDone!")
