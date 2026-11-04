"""Import reviewed original chapter summaries; never import textbook full text."""
import argparse
from pathlib import Path
import generate_daily_growth as g


def import_items(feed, pool, items):
    candidate = __import__('copy').deepcopy(pool)
    for item in items:
        existing = next((x for x in candidate['items'] if x['id'] == item['id']), None)
        if existing:
            keys = ('concept_id', 'quote', 'source', 'source_summary', 'review')
            if any(existing.get(k) != item.get(k) for k in keys):
                raise RuntimeError('Existing ID has different content; resolve before importing')
            continue
        if item.get('status') != 'ready':
            raise RuntimeError('Only reviewed ready items can be imported')
        g.validate_queue_item(item, g.dedup_history(feed, candidate) + [x for x in candidate['items'] if x.get('status') == 'ready'])
        candidate['items'].append(item)
    g.validate_pool(candidate)
    g.validate_ready_queue(feed, candidate)
    return candidate


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('chapter', type=Path)
    args = parser.parse_args()
    feed, pool = g.load_feed(), g.load_pool()
    batch = g.load_json(args.chapter, {})
    if not batch.get('items'):
        raise RuntimeError('Chapter requires nonempty reviewed items')
    result = import_items(feed, pool, batch['items'])
    g.save_json(g.POOL_PATH, result)
    print('Imported', len(result['items']) - len(pool['items']), 'new entries')
