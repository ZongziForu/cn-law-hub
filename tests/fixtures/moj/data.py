"""HTTP mock data for moj_law_crawler tests."""

SEARCH_HTML = """<html><body>
<div class="searching-results-list">
  <input id="page-count" value="2"/>
  <div class="list-item">
    <a href="/detail?bbh=1001">测试行政处罚法实施条例</a>
    2024-03-01公布 2024-05-01施行 现行有效
  </div>
  <div class="list-item">
    <a href="/detail?bbh=1002">测试已修改法规</a>
    2020-01-01公布 已修改
  </div>
  <div class="list-item">
    <a href="/detail?bbh=1003">测试无状态法规</a>
    2023-06-15公布 2023-08-01施行
  </div>
</div>
</body></html>"""

SEARCH_HTML_EMPTY = """<html><body>
<div class="searching-results-list">
  <input id="page-count" value="0"/>
</div>
</body></html>"""

SEARCH_HTML_NO_RESULTS = """<html><body>
<div class="searching-results-list">
  <input id="page-count" value="1"/>
  <p>暂无数据</p>
</div>
</body></html>"""


DETAIL_HTML = """<html><body>
<h1 class="article-title">测试行政处罚法实施条例</h1>
<div class="article-content">
<p>第一条 为了规范行政处罚的设定和实施...</p>
<p>第二条 行政处罚遵循公正、公开的原则。</p>
</div>
<div class="date">2024-03-01</div>
</body></html>"""


DETAIL_HTML_MINIMAL = """<html><body>
<p>测试内容正文。</p>
</body></html>"""
