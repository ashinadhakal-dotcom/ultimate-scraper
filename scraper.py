from __future__ import annotations

import hashlib
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import MAX_ARTICLES, MAX_WORKERS, RAW_ROOT, REQUEST_TIMEOUT, SOURCE_NAME, SOURCE_URL, ensure_dirs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def _session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=MAX_WORKERS, pool_maxsize=MAX_WORKERS)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        }
    )
    return session


def _extract_urls(html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    urls: set[str] = set()
    for a_tag in soup.select("a[href]"):
        href = a_tag.get("href", "").strip()
        if not href:
            continue
        absolute = urljoin(SOURCE_URL, href)
        parsed = urlparse(absolute)
        if "setopati.com" not in parsed.netloc:
            continue
        if not parsed.path or parsed.path in {"/", "/news"}:
            continue
        if any(seg in parsed.path for seg in ("/video", "/photo", "/author", "/search", "/tag")):
            continue
        urls.add(absolute.split("#", 1)[0])
    return sorted(urls)


def _extract_date(soup: BeautifulSoup) -> datetime:
    candidates = [
        soup.select_one("meta[property='article:published_time']"),
        soup.select_one("meta[name='pubdate']"),
        soup.select_one("time[datetime]"),
    ]
    for tag in candidates:
        if not tag:
            continue
        raw = tag.get("content") or tag.get("datetime")
        if not raw:
            continue
        raw = raw.strip()
        raw = raw.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            pass
    return datetime.utcnow()


def _extract_title(soup: BeautifulSoup) -> str:
    for selector in ("h1", "meta[property='og:title']", "title"):
        tag = soup.select_one(selector)
        if not tag:
            continue
        title = (tag.get("content") if selector.startswith("meta") else tag.get_text(" ", strip=True)) or ""
        title = re.sub(r"\s+", " ", title).strip()
        if title:
            return title
    return ""


def _save_article(url: str, html: str, title: str, published_at: datetime) -> Path:
    out_dir = RAW_ROOT / f"{published_at:%Y}" / f"{published_at:%m}" / f"{published_at:%d}"
    out_dir.mkdir(parents=True, exist_ok=True)
    name_seed = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    out_path = out_dir / f"article_{name_seed}_raw.json"
    payload = {
        "source": SOURCE_NAME,
        "url": url,
        "title": title,
        "date": f"{published_at:%Y-%m-%d}",
        "scraped_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "raw_html": html,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return out_path


def _fetch_and_store(session: requests.Session, url: str) -> Path | None:
    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        html = response.text
        soup = BeautifulSoup(html, "lxml")
        title = _extract_title(soup)
        published_at = _extract_date(soup)
        return _save_article(url=url, html=html, title=title, published_at=published_at)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed article fetch %s: %s", url, exc)
        return None


def scrape() -> list[Path]:
    ensure_dirs()
    session = _session()
    try:
        response = session.get(SOURCE_URL, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to fetch source page %s: %s", SOURCE_URL, exc)
        return []

    urls = _extract_urls(response.text)[:MAX_ARTICLES]
    logger.info("Discovered %d candidate URLs", len(urls))
    saved_paths: list[Path] = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(_fetch_and_store, session, url) for url in urls]
        for future in as_completed(futures):
            path = future.result()
            if path:
                saved_paths.append(path)

    logger.info("Saved %d raw articles", len(saved_paths))
    return saved_paths


def main() -> None:
    scrape()


if __name__ == "__main__":
    main()
