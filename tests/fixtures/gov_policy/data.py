"""HTTP mock data for gov_policy_library tests."""

# Simulated API search response (parsed JSON)
SEARCH_RESPONSE = {
    "code": 200,
    "searchVO": {
        "totalCount": 5,
        "catMap": {
            "国务院文件": {
                "listVO": [
                    {
                        "title": "测试<em>法规</em>一关于加强<em>营商</em>环境建设的意见",
                        "piclinksurl": "https://www.gov.cn/gongbao/content/2024/content_12345.htm",
                        "code": "gf001",
                        "pcode": "国发〔2024〕1号",
                        "pubtime": "2024-03-15",
                        "summary": "这是一份测试政策文件的摘要。",
                        "content": "测试正文内容...",
                        "source": "国务院",
                    },
                    {
                        "title": "测试政策二进一步推进放管服改革",
                        "piclinksurl": "https://www.gov.cn/gongbao/content/2024/content_67890.htm",
                        "code": "gf002",
                        "pcode": "国办发〔2024〕5号",
                        "pubtime": "2024-06-01",
                        "summary": "",
                        "content": "",
                        "source": "国务院办公厅",
                    },
                ]
            },
            "国务院部门文件": {
                "listVO": [
                    {
                        "title": "测试部门文件一关于优化营商环境的通知",
                        "piclinksurl": "",
                        "code": "bm001",
                        "pcode": "",
                        "pubtime": "2024-02-20",
                        "summary": "",
                        "content": "",
                        "source": "国家发展改革委",
                    }
                ]
            },
        },
        "extendresult": {
            "groupMap": {},
            "facetMap": {"pubtimeyear": {"2024": 3}},
        },
    },
}

EMPTY_RESPONSE = {"code": 200, "searchVO": {"totalCount": 0, "catMap": {}, "extendresult": {}}}

SEARCH_ERROR_RESPONSE = {"code": 500, "searchVO": {"totalCount": 0, "catMap": {}}}


def make_search_html(title, content_text="", pub_date="", source_name=""):
    return f"""<html><body>
<h1>{title}</h1>
<div class="article-content">{content_text}</div>
<div class="date">{pub_date}</div>
<div class="source">{source_name}</div>
</body></html>"""


DETAIL_HTML_FULL = make_search_html(
    "测试法规一：关于加强营商环境建设的意见",
    "第一条 为优化营商环境，制定本意见。\n第二条 各地区应当落实本意见。",
    "2024-03-15",
    "国务院",
)

DETAIL_HTML_NO_CONTENT = """<html><body>
<h1>测试标题</h1>
<div class="date">2024-01-01</div>
</body></html>"""

DETAIL_HTML_RELATIVE_LINKS = make_search_html(
    "测试页面",
    '参阅<a href="/zhengce/content/2024/content_999.htm">相关文件</a>。',
    "2024-05-01",
    "国务院办公厅",
)
