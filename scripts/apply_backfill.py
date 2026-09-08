import argparse
import copy
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FEED_PATH = ROOT / "growth-feed.json"
POOL_PATH = ROOT / "content_pool.json"
DEFAULT_BACKFILL_PATH = ROOT / "backfill_2026_08.json"
IMAGES_DIR = ROOT / "images"
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/jannymax/growth-content/main/images"


def load(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save(path, value):
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("backfill", nargs="?", type=Path, default=DEFAULT_BACKFILL_PATH)
    args = parser.parse_args()

    feed = load(FEED_PATH)
    pool = load(POOL_PATH)
    backfill_path = args.backfill if args.backfill.is_absolute() else ROOT / args.backfill
    backfill = load(backfill_path)

    by_id = {item["id"]: item for item in feed["quotes"]}
    existing_ids = set(by_id)
    existing_pool_ids = {item["id"] for item in pool["items"]}

    for curated in backfill:
        date_id = curated["date"]
        if date_id in existing_ids:
            continue

        source_item = by_id[curated["source_ref"]]
        image_filename = f"{date_id}.jpg"
        image_path = IMAGES_DIR / image_filename
        if not image_path.exists():
            raise RuntimeError(f"Missing backfill image: {image_path}")
        entry = {
            "id": date_id,
            "date": date_id,
            "quote": curated["quote"],
            "author": copy.deepcopy(source_item["author"]),
            "image_url": f"{GITHUB_RAW_BASE}/{image_filename}",
            "image_filename": image_filename,
            "image_path": f"images/{image_filename}",
            "image_name": source_item.get("image_name", "quotation_card_bg"),
            "source": copy.deepcopy(source_item["source"]),
            "source_summary": source_item["source_summary"],
            "practical_takeaway": curated["practical_takeaway"],
            "topic": curated["topic"],
            "image_source": {
                "provider": "OpenAI image generation",
                "id": f"generated-{date_id}",
                "usage": "original project background",
                "text_free": True,
            },
        }
        feed["quotes"].append(entry)
        existing_ids.add(date_id)

        pool_id = f"pool_{date_id}"
        if pool_id not in existing_pool_ids:
            pool["items"].append(
                {
                    "id": pool_id,
                    "status": "published",
                    "created_at": f"{date_id}T00:00:00Z",
                    "published_at": f"{date_id}T00:00:00Z",
                    "published_date": date_id,
                    "topic": curated["topic"],
                    "quote": curated["quote"],
                    "image_query": "curated existing image",
                    "source_summary": source_item["source_summary"],
                    "practical_takeaway": curated["practical_takeaway"],
                    "source": copy.deepcopy(source_item["source"]),
                }
            )
            existing_pool_ids.add(pool_id)

    feed["quotes"].sort(key=lambda item: item["date"])
    pool["items"].sort(key=lambda item: item.get("published_date") or item.get("created_at") or "")
    latest_date = max(item["date"] for item in feed["quotes"])
    feed["today_id"] = latest_date
    feed["updated_at"] = f"{latest_date}T00:00:00Z"

    save(FEED_PATH, feed)
    save(POOL_PATH, pool)


if __name__ == "__main__":
    main()
