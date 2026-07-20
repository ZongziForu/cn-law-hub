#!/usr/bin/env python3
"""Unit tests for scripts/download.py."""

import sys
import unittest
import zipfile
from io import BytesIO, StringIO
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import download as dl
from common import chinese_to_int, extract_article_number, int_to_chinese


class TestArgumentParser(unittest.TestCase):
    def test_search_default(self):
        args = dl.build_parser().parse_args(["--search", "出租车"])
        self.assertEqual(args.search, "出租车")
        self.assertEqual(args.page, 1)
        self.assertEqual(args.size, 20)
        self.assertFalse(args.exact)
        self.assertFalse(args.urls_only)
        self.assertEqual(args.format, "docx")
        self.assertEqual(args.range, "title")

    def test_search_exact_and_pagination(self):
        args = dl.build_parser().parse_args(
            [
                "--search",
                "物业管理条例",
                "--exact",
                "--page",
                "3",
                "--size",
                "100",
                "--urls-only",
                "--format",
                "pdf",
                "--range",
                "content",
                "--status",
                "3",
            ]
        )
        self.assertEqual(args.search, "物业管理条例")
        self.assertTrue(args.exact)
        self.assertEqual(args.page, 3)
        self.assertEqual(args.size, 100)
        self.assertTrue(args.urls_only)
        self.assertEqual(args.format, "pdf")
        self.assertEqual(args.range, "content")
        self.assertEqual(args.status, "3")

    def test_info(self):
        args = dl.build_parser().parse_args(["--info", "abc123"])
        self.assertEqual(args.info, "abc123")

    def test_preview(self):
        args = dl.build_parser().parse_args(["--preview", "abc123"])
        self.assertEqual(args.preview, "abc123")

    def test_article(self):
        args = dl.build_parser().parse_args(["--article", "abc123", "第三十八条"])
        self.assertEqual(args.article, "abc123")
        self.assertEqual(args.output, "第三十八条")

    def test_download_with_output(self):
        args = dl.build_parser().parse_args(
            ["--download", "abc123", "--format", "pdf", "out.pdf"]
        )
        self.assertEqual(args.download, "abc123")
        self.assertEqual(args.format, "pdf")
        self.assertEqual(args.output, "out.pdf")


class TestSearchLawsPayload(unittest.TestCase):
    def setUp(self):
        # Disable cache so _request is always called during payload tests.
        dl._cache.enabled = False

    def tearDown(self):
        dl._cache.enabled = True

    @mock.patch("download._request")
    def test_fuzzy_payload(self, mock_request):
        mock_request.return_value.json.return_value = {
            "code": 200,
            "rows": [],
            "total": 0,
        }
        dl.search_laws("出租车", page=2, size=50)
        call = mock_request.call_args
        self.assertEqual(call.args[0], "POST")
        self.assertIn("law-search/search/list", call.args[1])
        payload = call.kwargs["json"]
        self.assertEqual(payload["searchContent"], "出租车")
        self.assertEqual(payload["pageNum"], 2)
        self.assertEqual(payload["pageSize"], 50)
        self.assertEqual(payload["searchType"], 2)
        self.assertEqual(payload["searchRange"], 1)

    @mock.patch("download._request")
    def test_exact_payload(self, mock_request):
        mock_request.return_value.json.return_value = {
            "code": 200,
            "rows": [],
            "total": 0,
        }
        dl.search_laws("物业管理条例", search_type=1)
        payload = mock_request.call_args.kwargs["json"]
        self.assertEqual(payload["searchType"], 1)

    @mock.patch("download._request")
    def test_status_filter(self, mock_request):
        mock_request.return_value.json.return_value = {
            "code": 200,
            "rows": [],
            "total": 0,
        }
        dl.search_laws("出租车", status_filter=[3])
        payload = mock_request.call_args.kwargs["json"]
        self.assertEqual(payload["sxx"], [3])


class TestParseDetail(unittest.TestCase):
    def test_valid_detail(self):
        data = {
            "code": 200,
            "data": {
                "bbbs": "id1",
                "title": "Test Law",
                "flxz": "地方法规",
                "zdjgName": "广州市人民代表大会常务委员会",
                "gbrq": "2020-01-01",
                "sxrq": "2020-02-01",
                "sxx": 3,
                "ossFile": {
                    "ossWordPath": "prod/20200101/uuid.docx",
                    "ossPdfPath": "prod/20200101/uuid.pdf",
                },
            },
        }
        info = dl.parse_detail(data)
        self.assertEqual(info["title"], "Test Law")
        self.assertEqual(info["authority"], "广州市人民代表大会常务委员会")
        self.assertEqual(info["status_code"], 3)
        self.assertEqual(info["status_str"], "现行有效")
        self.assertIn("prod/20200101/uuid.docx", info["word_url"])
        self.assertIn("prod/20200101/uuid.pdf", info["pdf_url"])

    def test_invalid_detail(self):
        self.assertEqual(dl.parse_detail({}), {})
        self.assertEqual(dl.parse_detail({"code": 500}), {})


class TestCollectSearchUrls(unittest.TestCase):
    @mock.patch("download.get_download_url")
    def test_collect_success_and_failure(self, mock_get_url):
        def side_effect(bbbs, fmt):
            if bbbs == "id1":
                return "https://example.com/1.doc"
            raise RuntimeError("no url")

        mock_get_url.side_effect = side_effect

        data = {
            "code": 200,
            "rows": [
                {
                    "bbbs": "id1",
                    "title": "Law 1",
                    "flxz": "A",
                    "zdjgName": "X",
                    "gbrq": "2020",
                    "sxrq": "2020",
                    "sxx": 3,
                },
                {
                    "bbbs": "id2",
                    "title": "Law 2",
                    "flxz": "B",
                    "zdjgName": "Y",
                    "gbrq": "2020",
                    "sxrq": "2020",
                    "sxx": 3,
                },
            ],
        }
        results = dl.collect_search_urls(data)
        self.assertEqual(results[0]["url"], "https://example.com/1.doc")
        self.assertIsNone(results[0]["error"])
        self.assertIsNone(results[1]["url"])
        self.assertIn("no url", results[1]["error"])


class TestPrintSearchResults(unittest.TestCase):
    def test_output(self):
        data = {
            "code": 200,
            "total": 1,
            "rows": [
                {
                    "bbbs": "id1",
                    "title": "Test <em>Law</em>",
                    "flxz": "地方法规",
                    "zdjgName": "广州市人大",
                    "gbrq": "2020",
                    "sxrq": "2020",
                    "sxx": 3,
                }
            ],
        }
        out = StringIO()
        with mock.patch("sys.stdout", new=out):
            dl.print_search_results(data)
        text = out.getvalue()
        self.assertIn("Total: 1 | Returned: 1", text)
        self.assertIn("id1", text)
        self.assertIn("现行有效", text)
        self.assertNotIn("<em>", text)


class TestChineseNumerals(unittest.TestCase):
    def test_chinese_to_int(self):
        cases = [
            ("一", 1),
            ("十", 10),
            ("十四", 14),
            ("三十八", 38),
            ("一百零一", 101),
            ("二百一十七", 217),
            ("一千零一", 1001),
        ]
        for cn, expected in cases:
            self.assertEqual(chinese_to_int(cn), expected, f"failed for {cn}")

    def test_int_to_chinese(self):
        cases = [
            (1, "一"),
            (10, "十"),
            (14, "十四"),
            (38, "三十八"),
            (101, "一百零一"),
            (217, "二百一十七"),
            (1001, "一千零一"),
        ]
        for n, expected in cases:
            self.assertEqual(int_to_chinese(n), expected, f"failed for {n}")

    def test_round_trip(self):
        for n in range(1, 200):
            self.assertEqual(chinese_to_int(int_to_chinese(n)), n)


class TestArticleHelpers(unittest.TestCase):
    def test_is_article_line(self):
        self.assertTrue(dl._is_article_line("第一条"))
        self.assertTrue(dl._is_article_line("第38条"))
        self.assertTrue(dl._is_article_line("  第二百一十七条  "))
        self.assertFalse(dl._is_article_line("第一章 总则"))
        self.assertFalse(dl._is_article_line("为了规范"))

    def test_extract_article_number(self):
        self.assertEqual(extract_article_number("第一条 为了规范"), "第一条")
        self.assertEqual(extract_article_number("第38条 内容"), "第38条")

    def test_split_into_articles(self):
        paragraphs = [
            "题注",
            "第一条 内容一",
            "第二款 内容",
            "第二条 内容二",
            "第三条 内容三",
        ]
        articles = dl._split_into_articles(paragraphs)
        nums = [a[0] for a in articles]
        self.assertEqual(nums, ["题注/前言", "第一条", "第二条", "第三条"])

    def test_match_article_query(self):
        self.assertTrue(dl._match_article_query("38", "第三十八条"))
        self.assertTrue(dl._match_article_query("第38条", "第三十八条"))
        self.assertTrue(dl._match_article_query("三十八", "第三十八条"))
        self.assertTrue(dl._match_article_query("第三十八条", "第三十八条"))
        self.assertFalse(dl._match_article_query("39", "第三十八条"))


class TestExtractParagraphsFromDocx(unittest.TestCase):
    def _make_docx(self, paragraphs):
        xml_parts = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
        xml_parts.append(
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        )
        xml_parts.append("<w:body>")
        for text in paragraphs:
            xml_parts.append("<w:p><w:r><w:t>{}</w:t></w:r></w:p>".format(text))
        xml_parts.append("</w:body>")
        xml_parts.append("</w:document>")
        document_xml = "".join(xml_parts).encode("utf-8")

        buf = BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("word/document.xml", document_xml)
        return buf.getvalue()

    def test_extract_paragraphs(self):
        paragraphs = ["第一条", "本法所称...", "第二条"]
        docx_bytes = self._make_docx(paragraphs)
        result = dl._extract_paragraphs_from_docx(docx_bytes)
        self.assertEqual(result, paragraphs)


if __name__ == "__main__":
    unittest.main()
