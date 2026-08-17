#!/usr/bin/env python3
"""Submit sitemap URLs to IndexNow (Bing/Yandex) and optionally Bing SubmitUrlBatch."""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _http_get(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "SillGardenIndexingBot/1.0 (+https://sillgarden.com)"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def sitemap_urls() -> list[str]:
    try:
        xml = _http_get("https://sillgarden.com/sitemap-0.xml")
        root = ET.fromstring(xml)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        locs = [el.text.strip() for el in root.findall("sm:url/sm:loc", ns) if el.text]
        found = locs or re.findall(r"<loc>(https://[^<]+)</loc>", xml.decode("utf-8", errors="replace"))
        if found:
            return found
    except Exception as exc:  # noqa: BLE001
        print(f"Sitemap fetch failed ({exc}); using known URL list", file=sys.stderr)

    # Fallback matches current Astro sitemap (guides + core pages)
    return [
        "https://sillgarden.com/",
        "https://sillgarden.com/about/",
        "https://sillgarden.com/credits/",
        "https://sillgarden.com/disclosure/",
        "https://sillgarden.com/feed.xml",
        "https://sillgarden.com/guides/",
        "https://sillgarden.com/guides/aerogarden-vs-click-and-grow/",
        "https://sillgarden.com/guides/basil-countertop-first-harvest/",
        "https://sillgarden.com/guides/best-countertop-garden-apartments/",
        "https://sillgarden.com/guides/best-low-light-herbs-apartment/",
        "https://sillgarden.com/guides/cheapest-indoor-herb-garden-apartment/",
        "https://sillgarden.com/guides/countertop-garden-running-cost/",
        "https://sillgarden.com/guides/grow-light-schedules-herbs/",
        "https://sillgarden.com/guides/landlord-safe-indoor-garden-setup/",
        "https://sillgarden.com/guides/quiet-countertop-gardens-studios/",
        "https://sillgarden.com/guides/windowsill-herbs-without-kit/",
        "https://sillgarden.com/privacy/",
    ]


def ping_indexnow(urls: list[str], key: str) -> None:
    host = "sillgarden.com"
    payload = {
        "host": host,
        "key": key,
        "keyLocation": f"https://{host}/{key}.txt",
        "urlList": urls,
    }
    req = urllib.request.Request(
        "https://api.indexnow.org/indexnow",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        print(f"IndexNow OK ({resp.status}): {len(urls)} URLs")


def bing_submit(urls: list[str], api_key: str) -> None:
    payload = {"siteUrl": "https://sillgarden.com", "urlList": urls}
    endpoint = f"https://ssl.bing.com/webmaster/api.svc/json/SubmitUrlBatch?apikey={api_key}"
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        print(f"Bing SubmitUrlBatch OK ({resp.status}): {len(urls)} URLs")
        if body.strip():
            print(body[:300])


def main() -> int:
    load_dotenv()
    urls = sitemap_urls()
    if not urls:
        print("No URLs in sitemap", file=sys.stderr)
        return 1
    print(f"URLs: {len(urls)}")

    key = (os.environ.get("INDEXNOW_KEY") or "").strip()
    if not key:
        print("INDEXNOW_KEY missing — skip IndexNow", file=sys.stderr)
    else:
        # Ensure key file is live
        key_url = f"https://sillgarden.com/{key}.txt"
        try:
            live = _http_get(key_url).decode("utf-8", errors="replace").strip()
            if live != key:
                print(f"Key file mismatch at {key_url}", file=sys.stderr)
                return 1
        except Exception as exc:  # noqa: BLE001
            print(f"Key file not live yet ({key_url}): {exc}", file=sys.stderr)
            print("Deploy public/<key>.txt first, then re-run.", file=sys.stderr)
            return 1
        try:
            ping_indexnow(urls, key)
        except urllib.error.HTTPError as exc:
            print(f"IndexNow HTTP {exc.code}: {exc.read().decode()[:300]}", file=sys.stderr)
            return 1

    bing_key = (os.environ.get("BING_WEBMASTER_API_KEY") or "").strip()
    if bing_key:
        try:
            bing_submit(urls, bing_key)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            print(f"Bing SubmitUrlBatch HTTP {exc.code}: {detail[:400]}", file=sys.stderr)
            print("(Add/verify sillgarden.com in Bing Webmaster Tools if this failed.)", file=sys.stderr)
    else:
        print("No BING_WEBMASTER_API_KEY — skipped Bing batch")

    print("Google: sitemap already submitted in GSC. Manual 'Request indexing' in UI for priority URLs only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
