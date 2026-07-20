"""HTTP mock data for court_law_crawler tests."""

LIST_HTML_PAGE1_INTERP = """<html><body>
<div class="list">
  <li><a href="/fabu/xiangqing/504221.html">测试关于审理建设工程施工合同纠纷案件适用法律问题的解释</a></li>
  <li><a href="/fabu/xiangqing/504222.html">测试关于适用民法典担保制度的解释</a></li>
</div>
<a href="/fabu/gengduo/16_5.html">尾页</a>
<a href="/fabu/gengduo/16_2.html">2</a>
<a href="/fabu/gengduo/16_3.html">3</a>
</body></html>"""

LIST_HTML_PAGE1_FILE = """<html><body>
<div class="list">
  <li><a href="/fabu/xiangqing/504230.html">测试关于进一步规范司法裁量权的意见</a></li>
</div>
</body></html>"""

LIST_HTML_EMPTY = "<html><body></body></html>"

LIST_HTML_PAGE2 = """<html><body>
<div class="list">
  <li><a href="/fabu/xiangqing/504225.html">测试关于网络消费纠纷的司法解释</a></li>
</div>
</body></html>"""


DETAIL_HTML = """<html><body>
<div class="detail">
<h1>测试关于审理建设工程施工合同纠纷案件适用法律问题的解释</h1>
<p>为正确审理建设工程施工合同纠纷案件...</p>
</div>
发布时间：2024-02-01 10:00
来源：最高人民法院
</body></html>"""

DETAIL_HTML_NO_SOURCE = """<html><body>
<div class="detail">
<h1>测试标题</h1>
<p>正文内容</p>
</div>
发布时间：2023-06-15 08:00
</body></html>"""
