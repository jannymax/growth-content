import argparse
import difflib
import json
import os
import random
import re
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

try:
    from json_repair import repair_json
except Exception:
    repair_json = None


ROOT = Path(__file__).resolve().parents[1]

FEED_PATH = ROOT / "growth-feed.json"
POOL_PATH = ROOT / "content_pool.json"
PROMPTS_DIR = ROOT / "prompts"
IMAGES_DIR = ROOT / "images"

GITHUB_RAW_BASE = "https://raw.githubusercontent.com/jannymax/growth-content/main/images"
GITHUB_MODELS_URL = "https://models.github.ai/inference/chat/completions"
GITHUB_MODEL = os.getenv("GITHUB_MODEL", "openai/gpt-4o")

SEMANTIC_SCHOLAR_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
UNSPLASH_SEARCH_URL = "https://api.unsplash.com/search/photos"

CHINA_TZ = timezone(timedelta(hours=8))

TOPIC_QUERIES = [
    "early childhood development parenting longitudinal study",
    "parent child interaction language development children study",
    "emotion regulation preschool children parenting study",
    "executive function child development parenting intervention",
    "play based learning early childhood development research",
    "sleep routines child development parenting study",
    "shared reading language development children meta analysis",
    "secure attachment child development parenting study",
    "self regulation children family routines study",
    "positive parenting child socioemotional development study",
    "outdoor play child development early childhood study",
    "screen time child development systematic review preschool",
    "bilingual children cognitive language development study",
    "growth mindset children learning motivation study",
    "scaffolding learning children parent interaction study",
]

DISALLOWED_ABSOLUTE_WORDS = [
    "决定一生",
    "错过就来不及",
    "唯一",
    "必须",
    "最有效",
    "显著优于",
    "保证",
    "彻底改变",
]

DISALLOWED_SOUPY_WORDS = [
    "藏在",
    "土壤",
    "发光",
    "礼物",
    "被看见",
    "生长",
    "养出",
    "邀请",
]

DISALLOWED_SOURCE_MARKERS = [
    "wikipedia",
    "百科",
    "classic theories in child development",
]

DEFAULT_IMAGE_QUERY = "quiet lake morning mist minimal background"


def now_utc():
    return datetime.now(timezone.utc)


def iso_now():
    return now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")


def today_id():
    # 这个项目的发布时间对应中国早晨，所以日期按 Asia/Shanghai 计算，而不是 UTC。
    return datetime.now(CHINA_TZ).strftime("%Y-%m-%d")


def load_json(path, default):
    if not path.exists():
        return default

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp_name, str(path))
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def load_feed():
    return load_json(
        FEED_PATH,
        {
            "version": 1,
            "updated_at": "",
            "today_id": "",
            "quotes": [],
        },
    )


def load_pool():
    return load_json(POOL_PATH, {"items": []})


def already_published_today(feed, date_id):
    return any(item.get("id") == date_id for item in feed.get("quotes", []))


def canonical_text(value):
    value = (value or "").strip().lower()
    value = re.sub(r"https?://", "", value)
    value = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", value)
    return value


def paper_source_keys(paper):
    keys = set()

    for name in ("paperId", "url", "title"):
        value = paper.get(name)
        if value:
            keys.add(f"{name}:{canonical_text(value)}")

    external_ids = paper.get("externalIds") or {}
    doi = external_ids.get("DOI") or paper.get("doi")
    if doi:
        keys.add(f"doi:{canonical_text(doi)}")

    return {key for key in keys if key.split(":", 1)[1]}


def used_source_keys(feed, pool):
    keys = set()
    records = list(feed.get("quotes", [])) + list(pool.get("items", []))

    for record in records:
        source = record.get("source") or {}
        keys.update(paper_source_keys(source))

    return keys


def quote_similarity(left, right):
    return difflib.SequenceMatcher(
        None,
        canonical_text(left),
        canonical_text(right),
    ).ratio()


def get_recent_zh_quotes(feed, limit=60):
    quotes = []
    for item in feed.get("quotes", [])[-limit:]:
        text = (item.get("quote") or {}).get("zh-Hans", "")
        if text:
            quotes.append(text)
    return quotes


def score_paper(paper):
    year = paper.get("year") or 0
    citations = paper.get("citationCount") or 0
    abstract_len = len(paper.get("abstract") or "")

    recency_bonus = max(0, year - 2018) * 30
    citation_bonus = min(citations, 500) * 0.7
    abstract_bonus = min(abstract_len, 1600) * 0.05

    return recency_bonus + citation_bonus + abstract_bonus


def select_paper(papers, used_keys):
    candidates = []
    for paper in papers:
        if not paper.get("title") or not paper.get("abstract") or not paper.get("year"):
            continue
        if len(paper.get("abstract") or "") < 500:
            continue
        if paper_source_keys(paper) & used_keys:
            continue
        candidates.append(paper)

    if not candidates:
        return None

    candidates.sort(key=score_paper, reverse=True)
    return candidates[0]


def search_semantic_scholar(used_keys, topic_offset=0):
    headers = {"User-Agent": "growth-content-daily-feed/2.0"}
    fields = ",".join(
        [
            "paperId",
            "title",
            "abstract",
            "year",
            "citationCount",
            "url",
            "authors",
            "externalIds",
            "publicationDate",
            "venue",
            "publicationTypes",
        ]
    )

    queries = TOPIC_QUERIES[:]
    start = topic_offset % len(queries)
    queries = queries[start:] + queries[:start]

    last_error = None

    for query in queries:
        params = {
            "query": query,
            "limit": 50,
            "fields": fields,
        }

        for attempt in range(3):
            try:
                response = requests.get(
                    SEMANTIC_SCHOLAR_SEARCH_URL,
                    params=params,
                    headers=headers,
                    timeout=30,
                )

                if response.status_code == 429:
                    wait_seconds = 12 * (attempt + 1)
                    print(
                        "Semantic Scholar rate limited. "
                        f"Waiting {wait_seconds} seconds..."
                    )
                    time.sleep(wait_seconds)
                    continue

                response.raise_for_status()
                papers = response.json().get("data", [])
                selected = select_paper(papers, used_keys)
                if selected:
                    selected["_search_query"] = query
                    return selected
                break
            except Exception as error:
                last_error = error
                wait_seconds = 5 * (attempt + 1)
                print(
                    "Semantic Scholar search failed. "
                    f"Attempt {attempt + 1}/3. Waiting {wait_seconds} seconds..."
                )
                time.sleep(wait_seconds)

    raise RuntimeError(
        "No new suitable paper found from Semantic Scholar. "
        f"Last error: {last_error}"
    )


def github_models_generate(system_prompt, user_prompt):
    token = os.environ["GITHUB_TOKEN"]

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": "2026-03-10",
    }

    payload = {
        "model": GITHUB_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.35,
        "max_tokens": 2400,
    }

    response = requests.post(
        GITHUB_MODELS_URL,
        headers=headers,
        json=payload,
        timeout=120,
    )
    response.raise_for_status()

    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


def parse_model_json(raw):
    try:
        return json.loads(raw)
    except Exception:
        if repair_json is None:
            raise
        return json.loads(repair_json(raw))


def author_names(paper):
    authors = paper.get("authors") or []
    return [a.get("name") for a in authors if a.get("name")][:6]


def generate_insight(paper, recent_quotes):
    system_prompt = (PROMPTS_DIR / "content_system_prompt.md").read_text(encoding="utf-8")
    recent_block = "\n".join(f"- {quote}" for quote in recent_quotes[-25:])

    user_prompt = f"""
请只基于下面这一篇真实研究，生成 1 条每日成长内容。

论文标题：
{paper.get("title")}

年份：
{paper.get("year")}

期刊/会议：
{paper.get("venue") or "摘要未说明"}

引用数：
{paper.get("citationCount")}

论文链接：
{paper.get("url")}

摘要：
{paper.get("abstract")}

最近已经发布过的中文短句，注意不要重复观点和句式：
{recent_block or "暂无"}

要求：
- 只输出 1 条，不要输出多条
- 中文短句 55–90 个汉字，必须有具体洞察，不要口号
- 中文短句不要使用“可能”，要可信、具体、普通用户听得懂
- 不要用“藏在、土壤、发光、礼物、被看见、生长、养出、邀请”等鸡汤化或诗化表达
- 谨慎不等于反复弱化；用“与……相关、常常、更容易、为……提供、正在练习”等自然表达保留边界
- source_summary 120–260 个汉字，说明研究关注什么、发现了什么、能怎样谨慎理解
- source_summary 必须只依据上面的论文标题、年份、期刊/会议、链接和摘要，不要编造样本、方法或效果
- practical_takeaway 40–120 个汉字，给家长一个温和、可执行、不制造焦虑的做法
- source_summary 和 practical_takeaway 合计最多使用 1 次“可能”
- 如果摘要没有样本、方法、效果量等信息，就明确写“摘要未说明……”，不要编造
- 不要使用“决定一生、唯一、必须、最有效、保证”等绝对表达
- image_query 只能是英文摄影关键词，不能出现 people, child, baby, face, hand
- 输出严格 JSON，不要 markdown，不要解释

输出格式：
{{
  "insights": [
    {{
      "quote": {{
        "zh-Hans": "...",
        "en": "...",
        "ja": "..."
      }},
      "topic": "...",
      "source_summary": "...",
      "practical_takeaway": "...",
      "image_query": "quiet lake morning mist minimal background"
    }}
  ]
}}
"""

    raw = github_models_generate(system_prompt, user_prompt)
    generated = parse_model_json(raw)
    insights = generated.get("insights") or []
    if len(insights) != 1:
        raise RuntimeError("Model must return exactly one insight.")
    return insights[0]


def validate_insight(insight, existing_quotes):
    quote = insight.get("quote") or {}
    zh = (quote.get("zh-Hans") or "").strip()
    en = (quote.get("en") or "").strip()
    ja = (quote.get("ja") or "").strip()
    summary = (insight.get("source_summary") or "").strip()
    takeaway = (insight.get("practical_takeaway") or "").strip()
    image_query = (insight.get("image_query") or "").strip()

    if not zh or not en or not ja:
        raise RuntimeError("Generated quote is missing one or more languages.")
    if len(zh) < 35 or len(zh) > 110:
        raise RuntimeError(f"Chinese quote length looks wrong: {len(zh)}")
    if len(summary) < 80:
        raise RuntimeError("source_summary is too short.")
    if len(takeaway) < 30:
        raise RuntimeError("practical_takeaway is too short.")
    if "可能" in zh:
        raise RuntimeError("Chinese quote should avoid weak wording: 可能")
    if summary.count("可能") + takeaway.count("可能") > 1:
        raise RuntimeError("Generated content uses 可能 too often.")

    for word in DISALLOWED_ABSOLUTE_WORDS:
        if word in zh or word in summary or word in takeaway:
            raise RuntimeError(f"Generated content uses absolutist wording: {word}")
    for word in DISALLOWED_SOUPY_WORDS:
        if word in zh:
            raise RuntimeError(f"Generated quote sounds too slogan-like: {word}")

    for old_quote in existing_quotes:
        if quote_similarity(zh, old_quote) >= 0.72:
            raise RuntimeError("Generated quote is too similar to an existing quote.")

    lowered_query = image_query.lower()
    blocked_image_words = ["people", "person", "child", "children", "baby", "face", "hand"]
    if any(word in lowered_query for word in blocked_image_words):
        raise RuntimeError("image_query contains people/child/body words.")
    if not re.search(r"[a-zA-Z]", image_query):
        raise RuntimeError("image_query must be English keywords.")


def make_pool_item(insight, paper, date_id):
    source = {
        "paperId": paper.get("paperId"),
        "title": paper.get("title"),
        "year": paper.get("year"),
        "url": paper.get("url"),
        "citationCount": paper.get("citationCount"),
        "authors": author_names(paper),
        "venue": paper.get("venue"),
        "publicationDate": paper.get("publicationDate"),
        "publicationTypes": paper.get("publicationTypes"),
        "externalIds": paper.get("externalIds"),
        "search_query": paper.get("_search_query"),
    }

    return {
        "id": f"pool_{date_id}",
        "status": "draft",
        "created_at": iso_now(),
        "published_at": None,
        "published_date": None,
        "topic": insight.get("topic", ""),
        "quote": insight["quote"],
        "image_query": insight.get("image_query", DEFAULT_IMAGE_QUERY),
        "source_summary": insight.get("source_summary", ""),
        "practical_takeaway": insight.get("practical_takeaway", ""),
        "source": source,
    }


def get_used_unsplash_ids(feed):
    used = set()
    for item in feed.get("quotes", []):
        source = item.get("image_source") or {}
        image_id = source.get("id")
        if image_id:
            used.add(image_id)
    return used


def import_pillow():
    try:
        from PIL import Image
    except Exception:
        return None
    return Image


def dhash_image_file(path):
    Image = import_pillow()
    if Image is None:
        return None

    try:
        with Image.open(path) as image:
            image = image.convert("L").resize((9, 8))
            pixels = list(image.getdata())
    except Exception:
        return None

    bits = []
    for row in range(8):
        offset = row * 9
        for col in range(8):
            bits.append(1 if pixels[offset + col] > pixels[offset + col + 1] else 0)

    value = 0
    for bit in bits:
        value = (value << 1) | bit
    return f"{value:016x}"


def hamming_distance(left, right):
    if not left or not right:
        return 64
    return bin(int(left, 16) ^ int(right, 16)).count("1")


def existing_image_hashes(feed):
    hashes = []
    for item in feed.get("quotes", []):
        image_source = item.get("image_source") or {}
        value = image_source.get("perceptual_hash")
        if value:
            hashes.append(value)

    for path in IMAGES_DIR.glob("*"):
        if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            continue
        value = dhash_image_file(path)
        if value:
            hashes.append(value)

    return hashes


def build_unsplash_download_url(photo):
    raw = (photo.get("urls") or {}).get("raw")
    if not raw:
        return (photo.get("urls") or {}).get("regular")

    separator = "&" if "?" in raw else "?"
    return (
        f"{raw}{separator}"
        "w=1440&h=2160&fit=crop&crop=entropy&auto=format&q=90&fm=jpg"
    )


def notify_unsplash_download(photo, access_key):
    location = (photo.get("links") or {}).get("download_location")
    if not location:
        return

    try:
        requests.get(
            location,
            params={"client_id": access_key},
            timeout=15,
        )
    except Exception as error:
        print(f"Unsplash download notification failed: {error}")


def download_unsplash_image(date_id, image_query, feed):
    access_key = os.environ["UNSPLASH_ACCESS_KEY"]
    query = f"{image_query or DEFAULT_IMAGE_QUERY} calm minimal premium background negative space"
    used_ids = get_used_unsplash_ids(feed)
    known_hashes = existing_image_hashes(feed)

    search_queries = [
        query,
        "minimal quiet landscape vertical background negative space",
        "soft morning light nature vertical background",
    ]

    last_error = None

    for search_query in search_queries:
        params = {
            "query": search_query,
            "orientation": "portrait",
            "content_filter": "high",
            "per_page": 30,
            "client_id": access_key,
        }

        response = requests.get(UNSPLASH_SEARCH_URL, params=params, timeout=30)
        response.raise_for_status()
        results = response.json().get("results", [])
        random.shuffle(results)

        for selected in results:
            if selected.get("id") in used_ids:
                continue

            image_url = build_unsplash_download_url(selected)
            if not image_url:
                continue

            try:
                image_response = requests.get(image_url, timeout=60)
                image_response.raise_for_status()

                IMAGES_DIR.mkdir(exist_ok=True)
                image_path = IMAGES_DIR / f"{date_id}.jpg"
                image_path.write_bytes(image_response.content)

                image_hash = dhash_image_file(image_path)
                if image_hash and any(
                    hamming_distance(image_hash, old_hash) <= 8
                    for old_hash in known_hashes
                ):
                    if image_path.exists():
                        image_path.unlink()
                    continue

                notify_unsplash_download(selected, access_key)

                return {
                    "path": image_path,
                    "unsplash_id": selected.get("id"),
                    "unsplash_user": (selected.get("user") or {}).get("name"),
                    "unsplash_page": (selected.get("links") or {}).get("html"),
                    "perceptual_hash": image_hash,
                    "width": selected.get("width"),
                    "height": selected.get("height"),
                }
            except Exception as error:
                last_error = error
                continue

    raise RuntimeError(f"No suitable non-duplicate Unsplash image found: {last_error}")


def build_feed_entry(date_id, pool_item, image_meta):
    image_filename = f"{date_id}.jpg"

    return {
        "id": date_id,
        "date": date_id,
        "quote": pool_item["quote"],
        "author": {
            "zh-Hans": "育儿研究",
            "en": "Parenting Insights",
            "ja": "育児リサーチ",
        },
        "image_url": f"{GITHUB_RAW_BASE}/{image_filename}",
        "image_filename": image_filename,
        "image_path": f"images/{image_filename}",
        "image_name": "quotation_card_bg",
        "source": pool_item.get("source", {}),
        "source_summary": pool_item.get("source_summary", ""),
        "practical_takeaway": pool_item.get("practical_takeaway", ""),
        "topic": pool_item.get("topic", ""),
        "image_source": {
            "provider": "Unsplash",
            "id": image_meta.get("unsplash_id"),
            "photographer": image_meta.get("unsplash_user"),
            "url": image_meta.get("unsplash_page"),
            "perceptual_hash": image_meta.get("perceptual_hash"),
            "width": image_meta.get("width"),
            "height": image_meta.get("height"),
        },
    }


def image_filename_for_item(item):
    filename = item.get("image_filename")
    if filename:
        return filename

    image_path = item.get("image_path")
    if image_path:
        return Path(image_path).name

    image_url = item.get("image_url")
    if image_url:
        return Path(urlparse(image_url).path).name

    return ""


def has_real_source(source):
    title = str(source.get("title") or "").strip()
    url = str(source.get("url") or "").strip()
    year = source.get("year")
    if not title or not url or not year:
        return False

    haystack = f"{title} {url}".lower()
    return not any(marker in haystack for marker in DISALLOWED_SOURCE_MARKERS)


def validate_feed(feed):
    if not isinstance(feed.get("quotes"), list):
        raise RuntimeError("growth-feed.json must contain a quotes list.")

    seen_ids = set()
    seen_quotes = {}
    for item in feed.get("quotes", []):
        item_id = item.get("id")
        if not item_id:
            raise RuntimeError("A feed item is missing id.")
        if item_id in seen_ids:
            raise RuntimeError(f"Duplicate feed id: {item_id}")
        seen_ids.add(item_id)

        quote = item.get("quote") or {}
        zh = quote.get("zh-Hans")
        if not zh:
            raise RuntimeError(f"Feed item {item_id} is missing zh-Hans quote.")
        normalized_quote = canonical_text(zh)
        previous_id = seen_quotes.get(normalized_quote)
        if previous_id:
            raise RuntimeError(
                f"Duplicate zh-Hans quote in {previous_id} and {item_id}: {zh}"
            )
        seen_quotes[normalized_quote] = item_id

        image_filename = image_filename_for_item(item)
        if not image_filename:
            raise RuntimeError(f"Feed item {item_id} is missing image filename.")
        image_path = IMAGES_DIR / image_filename
        if not image_path.exists():
            raise RuntimeError(
                f"Feed item {item_id} points to missing image: {image_path}"
            )

        source = item.get("source") or {}
        if item_id >= "2026-06-02" and not has_real_source(source):
            raise RuntimeError(
                f"Feed item {item_id} must cite a specific real publication."
            )
        if item_id >= "2026-06-02" and not item.get("source_summary"):
            raise RuntimeError(f"Feed item {item_id} is missing source_summary.")
        if source and not source.get("title"):
            raise RuntimeError(f"Feed item {item_id} is missing source title.")


def validate_pool(pool):
    if not isinstance(pool.get("items"), list):
        raise RuntimeError("content_pool.json must contain an items list.")

    seen_ids = set()
    for item in pool.get("items", []):
        item_id = item.get("id")
        if not item_id:
            raise RuntimeError("A pool item is missing id.")
        if item_id in seen_ids:
            raise RuntimeError(f"Duplicate pool id: {item_id}")
        seen_ids.add(item_id)

        published_date = item.get("published_date")
        if published_date and published_date >= "2026-06-02":
            if not has_real_source(item.get("source") or {}):
                raise RuntimeError(
                    f"Published pool item {item_id} must cite a specific real publication."
                )
            if not item.get("source_summary"):
                raise RuntimeError(f"Published pool item {item_id} is missing source_summary.")


def publish_daily_entry(feed, pool, date_id):
    used_keys = used_source_keys(feed, pool)
    paper = search_semantic_scholar(used_keys, topic_offset=len(feed.get("quotes", [])))
    recent_quotes = get_recent_zh_quotes(feed)

    last_error = None
    for attempt in range(2):
        try:
            insight = generate_insight(paper, recent_quotes)
            validate_insight(insight, recent_quotes)
            break
        except Exception as error:
            last_error = error
            print(f"Generated insight failed validation. Attempt {attempt + 1}/2: {error}")
    else:
        raise RuntimeError(f"Could not generate a valid insight: {last_error}")

    pool_item = make_pool_item(insight, paper, date_id)
    image_meta = download_unsplash_image(
        date_id=date_id,
        image_query=pool_item.get("image_query", DEFAULT_IMAGE_QUERY),
        feed=feed,
    )
    entry = build_feed_entry(date_id, pool_item, image_meta)

    feed["quotes"].append(entry)
    feed["quotes"].sort(key=lambda item: item.get("date") or item.get("id") or "")
    feed["today_id"] = date_id
    feed["updated_at"] = iso_now()

    pool_item["status"] = "published"
    pool_item["published_at"] = iso_now()
    pool_item["published_date"] = date_id
    pool["items"].append(pool_item)

    validate_feed(feed)
    validate_pool(pool)

    return entry


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    feed = load_feed()
    pool = load_pool()

    validate_feed(feed)
    validate_pool(pool)

    if args.validate_only:
        print("growth-feed.json and content_pool.json are valid.")
        return

    date_id = today_id()
    if already_published_today(feed, date_id):
        print(f"{date_id} already exists in growth-feed.json. Nothing to do.")
        return

    entry = publish_daily_entry(feed, pool, date_id)

    save_json(FEED_PATH, feed)
    save_json(POOL_PATH, pool)

    print(f"Published daily growth quote for {date_id}.")
    print((entry.get("quote") or {}).get("zh-Hans", ""))


if __name__ == "__main__":
    main()
