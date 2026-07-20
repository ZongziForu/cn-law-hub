"""HTTP mock data for party_law_crawler tests."""

LIST_HTML_TIAOLI = """<html><body>
<ul class="list">
  <li><a href="/2024/03/15/ARTI1234567890.shtml">测试纪律处分条例实施细则</a></li>
  <li><a href="/2023/06/01/ARTI0987654321.shtml">测试党内监督条例实施办法</a></li>
  <li><a href="/2022/01/01/ARTI1111111111.shtml">测试党支部工作条例</a></li>
</ul>
</body></html>"""

LIST_HTML_DANGZHANG = """<html><body>
<ul class="list">
  <li><a href="/2022/10/22/ARTI2222222222.shtml">测试中国共产党章程修正案</a></li>
</ul>
</body></html>"""

LIST_HTML_EMPTY = """<html><body><ul class="list"></ul></body></html>"""

LIST_HTML_WITH_NAV = """<html><body>
<ul class="list">
  <li><a href="/2024/01/01/ARTI3333333333.shtml">测试有效条目</a></li>
  <li><a href="/">返回首页</a></li>
  <li><a href="javascript:;">显示更多</a></li>
</ul>
</body></html>"""


DETAIL_HTML = """<html><body>
<h1>测试纪律处分条例实施细则</h1>
<div class="article-content">
<p>第一条 为了严肃党的纪律...</p>
<p>第二条 本条例适用于全体党员。</p>
</div>
<div class="date">2024-03-15</div>
<div class="source">共产党员网</div>
</body></html>"""

DETAIL_HTML_MINIMAL = """<html><body>
<h1 class="bt">测试标题</h1>
</body></html>"""
