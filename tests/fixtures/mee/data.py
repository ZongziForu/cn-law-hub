"""HTTP mock data for mee_law_crawler tests."""

LIST_HTML_FL = """<html><body>
<li><a href="/ywgz/fgbz/fl/202603/t20260313_1146496.shtml">测试环境保护法</a></li>
<li><a href="/ywgz/fgbz/fl/202503/t20250310_1147000.shtml">测试大气污染防治法实施细则</a></li>
</body></html>"""

LIST_HTML_XZFG = """<html><body>
<li><a href="/ywgz/fgbz/xzfg/202502/t20250220_1148001.shtml">测试排污许可管理条例</a></li>
</body></html>"""

LIST_HTML_EMPTY = "<html><body></body></html>"

LIST_HTML_GZ = """<html><body>
<li><a href="/gzk/gz/202601/t20260105_1149002.shtml">测试碳排放权交易管理办法</a></li>
</body></html>"""


DETAIL_HTML = """<html><body>
<h1>测试环境保护法</h1>
<div class="article-content">
<p>第一条 为保护和改善环境...</p>
<p>第二条 本法适用于中华人民共和国领域。</p>
</div>
<div class="date">2026-03-13</div>
<div class="source">生态环境部</div>
</body></html>"""

DETAIL_HTML_MINIMAL = "<html><body><h1>测试标题</h1></body></html>"
