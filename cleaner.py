from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from bs4 import BeautifulSoup

from config import ADS_KEYWORDS, MIN_CONTENT_CHARS, PROCESSED_ROOT, RAW_ROOT, ensure_dirs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

NEPALI_PATTERN = re.compile(r"[\u0900-\u097F]")
SPACE_PATTERN = re.compile(r"\s+")


def _is_noise(node) -> bool:
    attrs = " ".join(node.get("class", []) + [node.get("id", "")]).lower()
    return any(keyword in attrs for keyword in ADS_KEYWORDS)


def _normalize_text(text: str) -> str:
    text = SPACE_PATTERN.sub(" ", text.replace("\xa0", " ")).strip()
    return text


def _clean_html(raw_html: str) -> str:
    soup = BeautifulSoup(raw_html, "lxml")

    for node in soup(["script", "style", "noscript", "header", "footer", "nav", "aside", "form", "svg", "iframe"]):
        node.decompose()

    for node in soup.find_all(True):
        if _is_noise(node):
            node.decompose()

    container = soup.find("article") or soup.find("main") or soup.body or soup
    parts = []
    for node in container.find_all(["h1", "h2", "p", "li"]):
        text = _normalize_text(node.get_text(" ", strip=True))
        if len(text) < 12:
            continue
        if not NEPALI_PATTERN.search(text):
            continue
        parts.append(text)

    if not parts:
        text = _normalize_text(container.get_text(" ", strip=True))
        return text if NEPALI_PATTERN.search(text) else ""

    return "\n".join(dict.fromkeys(parts))


def _processed_path(raw_path: Path) -> Path:
    relative = raw_path.relative_to(RAW_ROOT)
    year, month, day = relative.parts[0], relative.parts[1], relative.parts[2]
    out_dir = PROCESSED_ROOT / year / month / day
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = raw_path.name.replace("_raw.json", "_processed.json")
    return out_dir / filename


def process_file(raw_path: Path) -> Path | None:
    try:
        payload = json.loads(raw_path.read_text(encoding="utf-8"))
        cleaned_content = _clean_html(payload.get("raw_html", ""))
        if len(cleaned_content) < MIN_CONTENT_CHARS:
            logger.info("Skipping short content: %s", raw_path)
            return None

        output = {
            "source": payload.get("source", "setopati"),
            "url": payload.get("url", ""),
            "title": payload.get("title", "").strip(),
            "date": payload.get("date", ""),
            "cleaned_content": cleaned_content,
            "raw_file_path": str(raw_path),
        }
        out_path = _processed_path(raw_path)
        out_path.write_text(json.dumps(output, ensure_ascii=False), encoding="utf-8")
        return out_path
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to process %s: %s", raw_path, exc)
        return None


def clean_all() -> list[Path]:
    ensure_dirs()
    raw_files = sorted(RAW_ROOT.glob("*/*/*/article_*_raw.json"))
    logger.info("Found %d raw files", len(raw_files))

    outputs = []
    for raw_file in raw_files:
        out_path = process_file(raw_file)
        if out_path:
            outputs.append(out_path)

    logger.info("Created %d processed files", len(outputs))
    return outputs


def main() -> None:
    clean_all()


if __name__ == "__main__":
    main()
