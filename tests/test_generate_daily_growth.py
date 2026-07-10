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

    def test_topic_queries_include_science_literacy_at_controlled_interval(self):
        core_turn_queries = growth.topic_queries_for_offset(0)
        science_turn_queries = growth.topic_queries_for_offset(
            growth.SCIENCE_LITERACY_INTERVAL - 1
        )

        self.assertIn("parenting", core_turn_queries[0])
        self.assertIn(
            science_turn_queries[0],
            growth.SCIENCE_LITERACY_TOPIC_QUERIES,
        )
        self.assertLess(
            len(growth.SCIENCE_LITERACY_TOPIC_QUERIES),
            len(growth.TOPIC_QUERIES),
        )

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

    def test_validate_insight_rejects_weak_quote_wording(self):
        insight = {
            "quote": {
                "zh-Hans": "睡前少一点刺激，多一点熟悉的安静步骤，可能帮助孩子从白天的兴奋里慢慢放松下来。",
                "en": "Quiet bedtime steps help children settle.",
                "ja": "静かな寝る前の流れは、子どもが落ち着く助けになります。",
            },
            "source_summary": "这项研究关注睡前环境和儿童入睡过渡之间的关系，提示稳定、低刺激的流程与更平稳的休息准备有关。摘要未说明完整样本和效果量，因此需要保留边界理解。",
            "practical_takeaway": "睡前可以固定一个短流程，比如收玩具、洗漱、读一页书，再关灯休息。",
            "image_query": "quiet bedroom window light minimal background",
        }

        with self.assertRaises(RuntimeError):
            growth.validate_insight(insight, [])

    def test_validate_insight_rejects_slogan_like_quote(self):
        insight = {
            "quote": {
                "zh-Hans": "孩子的每一次尝试都藏在成长的土壤里，会慢慢生长成未来发光的礼物。",
                "en": "Every try becomes a gift for growth.",
                "ja": "一つ一つの挑戦が成長の贈り物になります。",
            },
            "source_summary": "这项研究关注儿童尝试任务时成人支持方式与自我调节之间的关系，摘要显示适度提示和等待能让儿童参与解决问题。摘要未说明完整效果量，因此需要保留边界理解。",
            "practical_takeaway": "孩子遇到小困难时，可以先等待几秒，再给一个很小的提示。",
            "image_query": "quiet forest morning minimal background",
        }

        with self.assertRaises(RuntimeError):
            growth.validate_insight(insight, [])

    def test_validate_insight_rejects_neuro_myth_wording(self):
        insight = {
            "quote": {
                "zh-Hans": "婴儿早期能分辨许多语言声音，母语经验会让常用语音连接更稳定，少用声音的神经元被裁剪。",
                "en": "Early language experience shapes speech perception.",
                "ja": "早期の言語経験は音の聞き分けに関わります。",
            },
            "source_summary": "这项研究关注婴儿语音知觉如何随语言经验变化，摘要显示早期经验与语音分辨模式调整有关。摘要未说明完整样本细节，因此不能把结果解释为简单的能力消失。",
            "practical_takeaway": "可以用自然互动让孩子多听、多回应不同语言声音，不需要制造窗口期焦虑。",
            "image_query": "quiet window light minimal background",
        }

        with self.assertRaises(RuntimeError):
            growth.validate_insight(insight, [])

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

    def test_validate_feed_rejects_duplicate_quotes(self):
        feed = {
            "quotes": [
                {
                    "id": "2026-06-01",
                    "quote": {"zh-Hans": "共同阅读能让孩子练习倾听、预测和表达。"},
                    "image_filename": "2026-06-02.jpg",
                    "source": {"title": "A", "url": "https://a.example"},
                },
                {
                    "id": "2026-06-02",
                    "quote": {"zh-Hans": "共同阅读，能让孩子练习倾听预测和表达"},
                    "image_filename": "2026-06-02.jpg",
                    "source": {"title": "B", "url": "https://b.example"},
                },
            ]
        }

        with self.assertRaises(RuntimeError):
            growth.validate_feed(feed)

    def test_validate_feed_rejects_placeholder_source_for_generated_content(self):
        feed = {
            "quotes": [
                {
                    "id": "2026-06-02",
                    "quote": {"zh-Hans": "稳定的生活流程能让孩子更清楚地预期接下来会发生什么。"},
                    "image_filename": "2026-06-02.jpg",
                    "source_summary": "这条内容缺少真实论文来源。",
                    "source": {
                        "title": "Classic theories in child development",
                        "year": 2024,
                        "url": "https://en.wikipedia.org/wiki/Child_development",
                    },
                },
            ]
        }

        with self.assertRaises(RuntimeError):
            growth.validate_feed(feed)

    def test_validate_feed_rejects_missing_image_file(self):
        feed = {
            "quotes": [
                {
                    "id": "2026-06-01",
                    "quote": {"zh-Hans": "户外观察能帮助孩子练习注意力和描述真实世界。"},
                    "image_filename": "missing-image.jpg",
                    "source": {"title": "A", "url": "https://a.example"},
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
