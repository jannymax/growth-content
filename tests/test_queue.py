import copy
import sys
import unittest
from pathlib import Path
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import generate_daily_growth as g
from import_chapter import import_items


def item():
    return dict(id='textbook-1', concept_id='learning-context', status='ready', topic='学习',
        quote={'zh-Hans':'学习不仅是记住信息，还包括在不同情境中理解和运用知识；只在原来的练习里做对，不等于已经能够迁移。','en':'Learning in context.', 'ja':'学習と文脈。'},
        source_summary='测试来源说明',source=dict(title='Educational Psychology',year=2009,url='https://example.org/book',authors=['Seifert'],edition='2',chapter='2',pages='20'),
        review=dict(source_checked=True,standalone=True,semantic_dedup_checked=True,translations_checked=True))

class QueueTests(unittest.TestCase):
    def test_import_idempotent_and_conflict(self):
        a=item(); feed={'quotes':[]}; pool={'items':[]}
        pool=import_items(feed,pool,[a]); self.assertEqual(len(import_items(feed,pool,[a])['items']),1)
        b=copy.deepcopy(a);b['source_summary']='changed'
        with self.assertRaises(RuntimeError): import_items(feed,pool,[b])
    def test_unreviewed_and_duplicate_concept_rejected(self):
        a=item();a['review']['source_checked']=False
        with self.assertRaises(RuntimeError): import_items({'quotes':[]},{'items':[]},[a])
        a=item();b=copy.deepcopy(a);b['id']='different'
        with self.assertRaises(RuntimeError): import_items({'quotes':[]},{'items':[]},[a,b])
    def test_empty_and_missing_photo_do_not_consume(self):
        with self.assertRaises(RuntimeError): g.publish_queued_entry({'quotes':[]},{'items':[]},'2026-11-05')
        pool={'items':[item()]}
        with mock.patch.object(g,'available_curated_photos',return_value=[]):
            with self.assertRaises(RuntimeError): g.publish_queued_entry({'quotes':[]},pool,'2026-11-05')
        self.assertEqual(pool['items'][0]['status'],'ready')
    def test_fifo_and_same_day_retry(self):
        feed={'quotes':[]};pool={'items':[item()]}
        with mock.patch.object(g,'available_curated_photos',return_value=[{}]), mock.patch.object(g,'select_curated_image',return_value={}), mock.patch.object(g,'validate_feed'):
            entry=g.publish_queued_entry(feed,pool,'2026-11-05')
            self.assertEqual(entry['content_id'],'textbook-1')
            self.assertIsNone(g.publish_queued_entry(feed,pool,'2026-11-05'))
        self.assertEqual(len(feed['quotes']),1)

class PublicationIntegrationTests(unittest.TestCase):
    def test_real_photo_and_feed_in_temporary_directory(self):
        try:
            import PIL
        except ImportError:
            self.skipTest('Pillow is installed by the GitHub workflow')
        import tempfile
        feed, pool = g.load_feed(), g.load_pool()
        ready = [x for x in pool['items'] if x.get('status') == 'ready']
        if not ready or not g.available_curated_photos(feed):
            self.skipTest('Production inventory empty; queue behavior covered by fixtures')
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            for photo in g.IMAGES_DIR.iterdir():
                if photo.is_file():
                    (target / photo.name).symlink_to(photo.resolve())
            with mock.patch.object(g, 'IMAGES_DIR', target):
                entry = g.publish_queued_entry(feed, pool, '2099-01-01')
                self.assertEqual(entry['content_id'], ready[0]['id'])
                self.assertTrue((target / '2099-01-01.jpg').exists())
                g.validate_feed(feed)
                g.validate_pool(pool)
                self.assertIsNone(g.publish_queued_entry(feed, pool, '2099-01-01'))

class DedupRegressionTests(unittest.TestCase):
    def test_preface_changes_do_not_create_new_content(self):
        text = '孩子通过观察和比较逐渐理解事物之间的关系。'
        self.assertEqual(g.quote_similarity(text, '换个角度看：研究提醒我们：'+text), 1.0)

    def test_retired_history_blocks_reimport_with_new_id(self):
        old = item()
        new = copy.deepcopy(old)
        new.update(id='new-id', concept_id='different-label')
        new['quote']['zh-Hans'] = '不妨这样理解：' + old['quote']['zh-Hans']
        with mock.patch.object(g, 'load_json', return_value={'items':[old]}):
            with self.assertRaisesRegex(RuntimeError, 'similar'):
                import_items({'quotes':[]}, {'items':[]}, [new])

    def test_published_pool_blocks_bypassing_importer(self):
        old = item(); old['status'] = 'published'
        new = copy.deepcopy(old);new.update(id='new-id',status='ready')
        with self.assertRaisesRegex(RuntimeError, 'concept_id'):
            g.validate_ready_queue({'quotes':[]}, {'items':[old,new]})
