#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["curl_cffi>=0.10", "beautifulsoup4>=4.12"]
# ///
"""Alza.cz from the terminal: product search and product detail.

Cloudflare in front of alza.cz rejects curl, WebFetch and crawler user agents on the
TLS fingerprint. curl_cffi with Chrome impersonation passes without any cookie.

Commands:
  search <query> [--page N] [--sort S] [--json]
  product <id|url> [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys

from bs4 import BeautifulSoup
from curl_cffi import requests

BASE = "https://www.alza.cz"
SORTS = {"relevance": 0, "price-asc": 1, "price-desc": 2, "rating": 6, "newest": 5}


def session() -> requests.Session:
    s = requests.Session(impersonate="chrome")
    s.headers.update({"accept-language": "cs-CZ", "referer": BASE + "/"})
    return s


def text(node) -> str:
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)) if node else ""


def price_number(s: str) -> float | None:
    s = s.replace("\xa0", " ").replace(",-", "").replace(" ", "").replace(",", ".")
    m = re.search(r"\d+(?:\.\d+)?", s)
    return float(m.group()) if m else None


def parse_box(box) -> dict:
    name_a = box.select_one("a.name")
    href = name_a["href"] if name_a and name_a.has_attr("href") else ""
    rating = box.select_one(".star-rating-block__value")
    count = box.select_one(".star-rating-block__count")
    coupon = box.select_one(".coupon-block")
    avl = box.select_one(".avl .avlVal")
    img = box.select_one("img.box-image")
    return {
        "id": int(box.get("data-id", 0) or 0),
        "code": box.get("data-code"),
        "name": text(name_a),
        "url": BASE + href.split("?")[0] if href.startswith("/") else href,
        "price": price_number(text(box.select_one(".js-price-box__primary-price__value"))),
        "coupon_price": price_number(text(coupon.select_one(".coupon-block__price"))) if coupon else None,
        "coupon_code": (coupon.get("data-coupon-code") or ("AlzaPlus" if "coupon-block--applus" in coupon.get("class", []) else None)) if coupon else None,
        "availability": text(avl),
        "rating": float(rating.get_text(strip=True).replace(",", ".")) if rating and rating.get_text(strip=True) else None,
        "reviews": int(re.sub(r"\D", "", count.get_text())) if count and re.search(r"\d", count.get_text()) else 0,
        "description": text(box.select_one(".Description")),
        "image": img["src"] if img and img.has_attr("src") else None,
        "can_buy": "canBuy" in box.get("class", []),
    }


FILTER_BODY = {
    "idPrefix": 0, "prefixType": 0, "idCategory": 0, "producers": "", "parameters": [], "idPrefixList": [],
    "page": 1, "pageTo": 1, "inStock": False, "newsOnly": False, "commodityStatusType": None,
    "upperDescriptionStatus": 0, "branchId": -2, "sort": 0, "categoryType": 1, "searchTerm": "",
    "sendProducers": False, "layout": 0, "append": False, "yearFrom": None, "yearTo": None, "artistId": None,
    "minPrice": -1, "maxPrice": -1, "shouldDisplayVirtooal": False, "callFromParametrizationView": False,
    "showOnlyActionCommodities": False, "activeSlot": 0, "searchInDescription": False,
    "showFullPriceDiscount": False, "showAtLeastOneSpecialPrice": False, "showOnlyHardDiscount": False,
    "sortMode": 0, "pageType": 0, "prefixCategory": 0,
}


def page_data(html: str) -> dict:
    """The `_pageData` JS object the listing page embeds; its `data` key drives the Filter service."""
    m = re.search(r"var _pageData\s*=\s*(\{.*?\});", html, re.S)
    if not m:
        die("listing page has no _pageData block; Alza changed its markup")
    return json.loads(m.group(1))


def search(s: requests.Session, query: str, page: int, sort: str) -> dict:
    r = s.get(BASE + "/search.htm", params={"exps": query})
    if r.status_code != 200:
        die(f"search failed: HTTP {r.status_code}", r.text)
    landing = BeautifulSoup(r.text, "html.parser")
    pd = page_data(r.text)["data"]
    count = landing.select_one("#lblNumberItem")
    total = int(re.sub(r"\D", "", text(count))) if count and re.search(r"\d", text(count)) else None
    if page == 1 and sort == "relevance":
        boxes_html = landing
    else:
        # Same call the page makes for paging and sorting. It needs the warm session from the GET above.
        body = {**FILTER_BODY, "idCategory": pd.get("categoryId", 0), "categoryType": pd.get("categoryTypeId", 1),
                "idPrefix": pd.get("idPrefix", 0), "prefixType": pd.get("prefixType", 0),
                "searchTerm": pd.get("searchTerm") or "", "page": page, "pageTo": page, "sort": SORTS[sort]}
        fr = s.post(BASE + "/Services/EShopService.svc/Filter", json=body,
                    headers={"accept": "application/json, text/plain, */*", "content-type": "application/json; charset=UTF-8",
                             "referer": r.url, "x-requested-with": "XMLHttpRequest"})
        if fr.status_code != 200 or "json" not in fr.headers.get("content-type", ""):
            die(f"Filter failed: HTTP {fr.status_code}", fr.text)
        d = fr.json()["d"]
        total = d.get("Count", total)
        boxes_html = BeautifulSoup(d.get("Boxes") or "", "html.parser")
    boxes = [parse_box(b) for b in boxes_html.select("div.box.browsingitem")]
    return {"query": query, "page": page, "sort": sort, "url": r.url, "title": text(landing.select_one("title")),
            "total": total, "results": boxes}


def product(s: requests.Session, ref: str) -> dict:
    if ref.startswith("http"):
        url = ref
    elif ref.isdigit():
        url = f"{BASE}/product-d{ref}.htm"
    else:
        die(f"product needs a numeric id or an alza.cz URL, got {ref!r}")
    r = s.get(url)
    if r.status_code != 200:
        die(f"product fetch failed: HTTP {r.status_code}", r.text)
    soup = BeautifulSoup(r.text, "html.parser")
    ld = {}
    for tag in soup.select('script[type="application/ld+json"]'):
        try:
            d = json.loads(tag.string or "")
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict) and d.get("@type") == "Product":
            ld = d
    offers = ld.get("offers") or {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    agg = ld.get("aggregateRating") or {}
    m = re.search(r"-d(\d+)\.htm", r.url)
    return {
        "id": int(m.group(1)) if m else None,
        "name": (ld.get("name") or text(soup.select_one("h1"))).strip(),
        "url": r.url.split("?")[0],
        "price": float(offers["price"]) if offers.get("price") else price_number(text(soup.select_one(".price-box__price"))),
        "currency": offers.get("priceCurrency"),
        "availability": offers.get("availability") or text(soup.select_one(".availability-label")),
        "sku": ld.get("sku"),
        "brand": (ld.get("brand") or {}).get("name") if isinstance(ld.get("brand"), dict) else ld.get("brand"),
        "rating": float(agg["ratingValue"]) if agg.get("ratingValue") else None,
        "reviews": int(agg["reviewCount"]) if agg.get("reviewCount") else None,
        "description": (ld.get("description") or text(soup.select_one(".description"))).strip(),
        "images": [i["url"] if isinstance(i, dict) else i for i in (ld.get("image") or [])][:5],
    }



def die(msg: str, body: str = "") -> None:
    print(f"error: {msg}", file=sys.stderr)
    if body and "challenge-platform" in body:
        print("error: Cloudflare challenge page returned; the Chrome impersonation profile may need updating", file=sys.stderr)
    sys.exit(1)


def fmt_price(p: float | None) -> str:
    return f"{p:,.0f} Kč".replace(",", " ") if p is not None else "-"


def print_search(d: dict) -> None:
    head = f"{d['title']}  (page {d['page']}"
    head += f", {d['total']} total)" if d.get("total") else ")"
    print(head)
    for i, p in enumerate(d["results"], 1):
        line = f"{i:2}. {p['name']}  {fmt_price(p['price'])}"
        if p["coupon_price"]:
            line += f"  ({fmt_price(p['coupon_price'])} with {p['coupon_code']})"
        if p["rating"] is not None:
            line += f"  ★{p['rating']} ({p['reviews']})"
        print(line)
        print(f"    {p['availability'] or 'n/a'} | code {p['code']} | id {p['id']}")
        print(f"    {p['url']}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("search")
    sp.add_argument("query")
    sp.add_argument("--page", type=int, default=1)
    sp.add_argument("--sort", choices=SORTS, default="relevance")
    sp.add_argument("--json", action="store_true")
    pp = sub.add_parser("product")
    pp.add_argument("ref")
    pp.add_argument("--json", action="store_true")
    a = ap.parse_args()

    s = session()
    if a.cmd == "search":
        d = search(s, a.query, a.page, a.sort)
        print(json.dumps(d, ensure_ascii=False, indent=1)) if a.json else print_search(d)
    elif a.cmd == "product":
        d = product(s, a.ref)
        print(json.dumps(d, ensure_ascii=False, indent=1)) if a.json else print("\n".join(f"{k}: {v}" for k, v in d.items()))


if __name__ == "__main__":
    main()
