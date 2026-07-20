"""HTTP mock data for tax_law_crawler tests."""

CHANNEL_PAGE_HTML = """<html><body>
<script>var channelId = "test-channel-abc123";</script>
<div class="list-container"></div>
</body></html>"""

CHANNEL_PAGE_ALT_HTML = """<html><body>
<script>var channelId = "alt-channel-xyz789";</script>
</body></html>"""

CHANNEL_PAGE_MAIN_HTML = """<html><body>
<script>var channelId = "main-channel-001";</script>
</body></html>"""

CHANNEL_PAGE_NONE = "<html><body></body></html>"

API_RESPONSE = {
    "results": {
        "data": {
            "total": 3,
            "results": [
                {
                    "titleHtml": "测试增值税<em>暂行条例</em>实施细则",
                    "subTitleHtml": "（2024年修订版）",
                    "publishedTimeStr": "2024-05-01",
                    "url": "/zcfgk/c100009/c5250687/content.html",
                    "domainMetaList": [
                        {
                            "domainMetadataName": "发文信息",
                            "resultList": [
                                {"key": "fz", "value": "财政部令第50号"},
                                {"key": "issuerDepartment", "value": "财政部"},
                                {"key": "effectivedate", "value": "2024-07-01"},
                            ],
                        }
                    ],
                },
                {
                    "titleHtml": "测试企业所得税法实施条例",
                    "subTitleHtml": "",
                    "publishedTimeStr": "2023-12-01",
                    "url": "http://www.chinatax.gov.cn/zcfgk/c100010/c5250999/content.html",
                    "domainMetaList": [],
                },
            ],
        }
    }
}

API_RESPONSE_EMPTY = {"results": {"data": {"total": 0, "results": []}}}

API_RESPONSE_PAGE2 = {
    "results": {
        "data": {
            "total": 3,
            "results": [
                {
                    "titleHtml": "测试第三条规定",
                    "subTitleHtml": "",
                    "publishedTimeStr": "2024-08-01",
                    "url": "/zcfgk/c100009/c5250999/content.html",
                    "domainMetaList": [],
                }
            ],
        }
    }
}


DETAIL_HTML = """<html><body>
<h1 class="bt">测试增值税暂行条例实施细则</h1>
<div class="TRS_Editor"><p>第一条 在中华人民共和国境内销售货物或者提供加工...</p></div>
<div class="date">2024-05-01</div>
</body></html>"""

DETAIL_HTML_MINIMAL = """<html><body><div class="content"><p>仅有正文</p></div></body></html>"""
