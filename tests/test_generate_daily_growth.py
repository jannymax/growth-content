import unittest

from scripts import generate_daily_growth as growth


class GenerateDailyGrowthTests(unittest.TestCase):
    def test_source_keys_include_paper_id_doi_title_and_url(self):
        paper = {
            "paperId": "abc123",
            "title": "Parent Child Interaction and Language Development",
            "url": "https://example.org/paper",
            "externalIds": {"DOI": "10.1234/Example.DOI"},
        }

        keys = growth.paper_source_keys(paper)

        self.assertIn("paperId:abc123", keys)
        self.assertIn("doi:101234exampledoi", keys)
        self.assertIn("title:parentchildinteractionandlanguagedevelopment", keys)
        self.assertIn("url:exampleorgpaper", keys)

    def test_select_paper_skips_used_source(self):
        used = {"paperId:usedpaper"}
        papers = [
            {
                "paperId": "used-paper",
                "title": "Used Paper",
                "abstract": "a" * 600,
                "year": 2025,
                "citationCount": 500,
            },
            {
                "paperId": "fresh-paper",
                "title": "Fresh Paper",
                "abstract": "b" * 600,
                "year": 2024,
                "citationCount": 10,
            },
        ]

        selected = growth.select_paper(papers, used)

        self.assertEqual(selected["paperId"], "fresh-paper")

    def test_validate_insight_rejects_near_duplicate_quote(self):
        insight = {
            "quote": {
                "zh-Hans": "当孩子在稳定而温和的互动中被回应，他们往往更容易把注意力放回探索和学习，而不是反复确认自己是否安全。",
                "en": "A warm response can make exploration feel safer.",
                "ja": "温かな応答は探索を支えます。",
            },
            "source_summary": "这项研究关注亲子互动与儿童发展的关系，摘要显示稳定回应可能与儿童探索和学习有关。摘要未说明完整样本和具体测量细节，因此更适合作为温和理解，而不是直接当作因果结论。",
            "practical_takeaway": "可以在孩子寻求确认时先回应情绪，再慢慢把注意力带回正在做的事。",
            "image_query": "quiet forest morning mist minimal background",
        }

        with self.assertRaises(RuntimeError):
            growth.validate_insight(
                insight,
                [
                    "当孩子在稳定而温和的互动中被回应，他们往往更容易把注意力放回探索和学习，而不是反复确认自己是否安全。"
                ],
            )

    def test_validate_feed_rejects_duplicate_ids(self):
        feed = {
            "quotes": [
                {
                    "id": "2026-07-01",
                    "quote": {"zh-Hans": "第一条关于儿童成长的温和观察。"},
                    "source": {"title": "A", "url": "https://a.example"},
                },
                {
                    "id": "2026-07-01",
                    "quote": {"zh-Hans": "第二条关于儿童成长的温和观察。"},
                    "source": {"title": "B", "url": "https://b.example"},
                },
            ]
        }

        with self.assertRaises(RuntimeError):
            growth.validate_feed(feed)

    def test_hamming_distance(self):
        self.assertEqual(growth.hamming_distance("0000000000000000", "0000000000000000"), 0)
        self.assertEqual(growth.hamming_distance("0000000000000000", "ffffffffffffffff"), 64)


if __name__ == "__main__":
    unittest.main()
