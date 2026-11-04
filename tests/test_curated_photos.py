import unittest
from scripts import generate_daily_growth as growth

class CuratedPhotosTests(unittest.TestCase):
    def test_only_unused_approved_photos_are_selected(self):
        photos = growth.available_curated_photos({"quotes": []})
        self.assertGreaterEqual(len(photos), 2)
        feed = {"quotes": [{"image_source": {"provider": "Pexels", "id": photos[0]["id"]}}]}
        self.assertEqual([p["id"] for p in growth.available_curated_photos(feed)], [p["id"] for p in photos[1:]])

    def test_exhausted_queue_does_not_reuse_photos(self):
        photos = growth.available_curated_photos({"quotes": []})
        feed = {"quotes": [{"image_source": {"provider": "Pexels", "id": p["id"]}} for p in photos]}
        self.assertEqual(growth.available_curated_photos(feed), [])
