import copy
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FEED_PATH = ROOT / "growth-feed.json"
POOL_PATH = ROOT / "content_pool.json"
BACKFILL_PATH = ROOT / "backfill_2026_08.json"


def load(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save(path, value):
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main():
    feed = load(FEED_PATH)
    pool = load(POOL_PATH)
    backfill = load(BACKFILL_PATH)

    by_id = {item["id"]: item for item in feed["quotes"]}
    existing_ids = set(by_id)
    existing_pool_ids = {item["id"] for item in pool["items"]}

    for curated in backfill:
        date_id = curated["date"]
        if date_id in existing_ids:
            continue

        source_item = by_id[curated["source_ref"]]
        entry = {
            "id": date_id,
            "date": date_id,
            "quote": curated["quote"],
            "author": copy.deepcopy(source_item["author"]),
            "image_url": source_item.get("image_url"),
            "image_filename": source_item.get("image_filename"),
            "image_path": source_item.get("image_path"),
            "image_name": source_item.get("image_name", "quotation_card_bg"),
            "source": copy.deepcopy(source_item["source"]),
            "source_summary": source_item["source_summary"],
            "practical_takeaway": curated["practical_takeaway"],
            "topic": curated["topic"],
            "image_source": copy.deepcopy(source_item.get("image_source", {})),
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
    feed["today_id"] = "2026-08-18"
    feed["updated_at"] = "2026-08-18T00:00:00Z"

    save(FEED_PATH, feed)
    save(POOL_PATH, pool)


if __name__ == "__main__":
    main()
