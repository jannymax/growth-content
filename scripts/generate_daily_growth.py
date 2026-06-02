import json
import os
import random
from datetime import datetime, timezone
from pathlib import Path

import requests
from json_repair import repair_json


ROOT = Path(__file__).resolve().parents[1]

FEED_PATH = ROOT / "growth-feed.json"
POOL_PATH = ROOT / "content_pool.json"
PROMPTS_DIR = ROOT / "prompts"
IMAGES_DIR = ROOT / "images"

GITHUB_RAW_BASE = "https://raw.githubusercontent.com/jannymax/growth-content/main/images"

GITHUB_MODELS_URL = "https://models.github.ai/inference/chat/completions"
GITHUB_MODEL = os.getenv("GITHUB_MODEL", "openai/gpt-4o-mini")

UNSPLASH_SEARCH_URL = "https://api.unsplash.com/search/photos"

SEARCH_KEYWORDS = [
    "child development psychology",
    "early childhood education child development",
    "parent child interaction child development",
    "emotion regulation preschool children",
    "executive function child development",
    "pretend play child development",
    "language development children",
    "bilingual children cognitive development",
    "attachment theory child development",
    "scaffolding learning children",
    "play based learning early childhood",
    "social emotional learning preschool children",
]


def utc_now():
    return datetime.now(timezone.utc)


def today_id():
    return utc_now().strftime("%Y-%m-%d")


def load_json(path, default):
    if not path.exists():
        return default

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def load_feed():
    return load_json(FEED_PATH, {
        "version": 1,
        "updated_at": "",
        "today_id": "",
        "quotes": []
    })


def load_pool():
    return load_json(POOL_PATH, {
        "items": []
    })


def already_published_today(feed, date_id):
    return any(item.get("id") == date_id for item in feed.get("quotes", []))


def get_unpublished_items(pool):
    return [
        item for item in pool.get("items", [])
        if item.get("status") != "published"
    ]


def search_semantic_scholar():
    keyword = random.choice(SEARCH_KEYWORDS)

    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": keyword,
        "limit": 10,
        "fields": "title,abstract,year,citationCount,url,authors"
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()

    papers = response.json().get("data", [])

    papers = [
        p for p in papers
        if p.get("abstract")
        and p.get("title")
        and p.get("year")
    ]

    if not papers:
        raise RuntimeError("No suitable papers found.")

    papers.sort(
        key=lambda p: (
            p.get("citationCount") or 0,
            p.get("year") or 0
        ),
        reverse=True
    )

    return papers[0]


def github_models_generate(system_prompt, user_prompt):
    token = os.environ["GITHUB_TOKEN"]

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": "2026-03-10"
    }

    payload = {
        "model": GITHUB_MODEL,
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        "temperature": 0.4,
        "max_tokens": 1800
    }

    response = requests.post(
        GITHUB_MODELS_URL,
        headers=headers,
        json=payload,
        timeout=120
    )
    response.raise_for_status()

    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


def generate_insights(paper):
    system_prompt = (PROMPTS_DIR / "content_system_prompt.md").read_text(encoding="utf-8")

    user_prompt = f"""
请基于下面这篇研究，生成 1–8 条适合进入内容池的每日成长短句。

论文标题：
{paper.get("title")}

年份：
{paper.get("year")}

引用数：
{paper.get("citationCount")}

摘要：
{paper.get("abstract")}

要求：
- 每条中文 20–40 个汉字左右
- 每条只表达一个洞察
- 适合每天发布一条
- 中文、英文、日文三语
- 不夸大，不制造焦虑
- 输出严格 JSON，不要 markdown
"""

    raw = github_models_generate(system_prompt, user_prompt)

    try:
        return json.loads(raw)
    except Exception:
        repaired = repair_json(raw)
        return json.loads(repaired)


def add_insights_to_pool(pool, generated, paper):
    insights = generated.get("insights", [])

    if not insights:
        raise RuntimeError("No insights generated.")

    now_text = utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")

    authors = paper.get("authors") or []
    author_names = [a.get("name") for a in authors if a.get("name")]

    existing_keys = set()
    for item in pool.get("items", []):
        zh = item.get("quote", {}).get("zh-Hans", "")
        existing_keys.add(zh)

    added_count = 0

    for index, insight in enumerate(insights, start=1):
        quote = insight.get("quote", {})
        zh = quote.get("zh-Hans", "").strip()

        if not zh:
            continue

        if zh in existing_keys:
            continue

        pool_item = {
            "id": f"pool_{utc_now().strftime('%Y%m%d%H%M%S')}_{index}",
            "status": "draft",
            "created_at": now_text,
            "published_at": None,
            "published_date": None,
            "topic": insight.get("topic", ""),
            "quote": quote,
            "image_query": insight.get("image_query", "quiet lake morning mist minimal background"),
            "source_summary": insight.get("source_summary", ""),
            "source": {
                "title": paper.get("title"),
                "year": paper.get("year"),
                "url": paper.get("url"),
                "citationCount": paper.get("citationCount"),
                "authors": author_names[:5]
            }
        }

        pool["items"].append(pool_item)
        existing_keys.add(zh)
        added_count += 1

    if added_count == 0:
        raise RuntimeError("No new insights added to pool.")

    return added_count


def download_unsplash_image(date_id, image_query):
    access_key = os.environ["UNSPLASH_ACCESS_KEY"]

    # 强化你的图片审美：干净、安静、适合背景
    query = f"{image_query} minimal calm nature background negative space"

    params = {
        "query": query,
        "orientation": "landscape",
        "per_page": 10,
        "client_id": access_key
    }

    response = requests.get(
        UNSPLASH_SEARCH_URL,
        params=params,
        timeout=30
    )
    response.raise_for_status()

    results = response.json().get("results", [])

    if not results:
        # 兜底关键词
        params["query"] = "minimal calm landscape negative space"
        response = requests.get(
            UNSPLASH_SEARCH_URL,
            params=params,
            timeout=30
        )
        response.raise_for_status()
        results = response.json().get("results", [])

    if not results:
        raise RuntimeError("No Unsplash image found.")

    # 取前几张里随机一张，避免每天过于类似
    selected = random.choice(results[:5])
    image_url = selected["urls"]["regular"]

    image_response = requests.get(image_url, timeout=60)
    image_response.raise_for_status()

    IMAGES_DIR.mkdir(exist_ok=True)

    image_path = IMAGES_DIR / f"{date_id}.jpg"
    image_path.write_bytes(image_response.content)

    return {
        "path": image_path,
        "unsplash_id": selected.get("id"),
        "unsplash_user": selected.get("user", {}).get("name"),
        "unsplash_page": selected.get("links", {}).get("html")
    }


def build_feed_entry(date_id, pool_item, image_meta):
    return {
        "id": date_id,
        "date": date_id,
        "quote": pool_item["quote"],
        "author": {
            "zh-Hans": "育儿研究",
            "en": "Parenting Insights",
            "ja": "育児リサーチ"
        },
        "image_url": f"{GITHUB_RAW_BASE}/{date_id}.jpg",
        "image_name": "quotation_card_bg",
        "source": pool_item.get("source", {}),
        "topic": pool_item.get("topic", ""),
        "image_source": {
            "provider": "Unsplash",
            "id": image_meta.get("unsplash_id"),
            "photographer": image_meta.get("unsplash_user"),
            "url": image_meta.get("unsplash_page")
        }
    }


def publish_one_item(feed, pool, date_id):
    unpublished = get_unpublished_items(pool)

    if not unpublished:
        raise RuntimeError("No unpublished items in pool.")

    selected = unpublished[0]

    image_meta = download_unsplash_image(
        date_id=date_id,
        image_query=selected.get("image_query", "quiet lake morning mist minimal background")
    )

    entry = build_feed_entry(date_id, selected, image_meta)

    feed["quotes"].append(entry)
    feed["today_id"] = date_id
    feed["updated_at"] = utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")

    selected["status"] = "published"
    selected["published_at"] = utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")
    selected["published_date"] = date_id

    return selected


def main():
    date_id = today_id()

    feed = load_feed()
    pool = load_pool()

    if already_published_today(feed, date_id):
        print(f"{date_id} already exists in growth-feed.json. Nothing to do.")
        return

    unpublished = get_unpublished_items(pool)

    if not unpublished:
        print("Content pool is empty. Searching for a new paper...")
        paper = search_semantic_scholar()
        generated = generate_insights(paper)
        added_count = add_insights_to_pool(pool, generated, paper)
        print(f"Added {added_count} insights to content_pool.json.")

    selected = publish_one_item(feed, pool, date_id)

    save_json(FEED_PATH, feed)
    save_json(POOL_PATH, pool)

    print(f"Published daily growth quote for {date_id}.")
    print(selected.get("quote", {}).get("zh-Hans", ""))


if __name__ == "__main__":
    main()
