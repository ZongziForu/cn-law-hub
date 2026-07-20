"""HTTP mock data for mod_law_crawler tests."""

INDEX_HTML_FLFG = """<html><body>
<div class="list">
  <li><a href="/gfbw/fgwx/flfg/16448581.html">测试国防法实施条例</a></li>
  <li><a href="/gfbw/fgwx/flfg/16448582.html">测试民用运力国防动员条例</a></li>
  <li><a href="/gfbw/fgwx/flfg/16448583.shtml">测试无关格式</a></li>
  <li><a href="/">显示更多</a></li>
</div>
</body></html>"""

INDEX_HTML_BPS = """<html><body>
<div class="list">
  <li><a href="/gfbw/fgwx/bps/16449001.html">测试中国的国防白皮书</a></li>
</div>
</body></html>"""

INDEX_HTML_EMPTY = """<html><body><div class="list"></div></body></html>"""

INDEX_HTML_WITH_RELATIVE = """<html><body>
<div class="list">
  <li><a href="/gfbw/fgwx/flfg/16448584.html">测试军事设施保护条例</a></li>
</div>
</body></html>"""


DETAIL_HTML = """<html><body>
<h1 class="bt">测试国防法实施条例</h1>
<div class="content">
<p>第一条 为了加强国防建设...</p>
<p>第二条 本条例适用于国防活动。</p>
</div>
<div class="date">2024-01-15</div>
<div class="source">国防部网站</div>
</body></html>"""

DETAIL_HTML_NO_SOURCE = """<html><body>
<h1 class="article-title">测试标题</h1>
<div class="TRS_Editor"><p>正文内容</p></div>
</body></html>"""
