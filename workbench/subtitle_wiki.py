"""Read-only four-language MD reference viewer. Never executes document content."""
import html
from pathlib import Path
from urllib.parse import unquote
LINKS=[('README.md','知识库入口'),('en.md','英文'),('zh.md','中文'),('ja.md','日文'),('ko.md','韩文'),('implementation.md','程序执行与缺口'),('sources/en.md','英文原文'),('sources/zh-CN.md','简体原文'),('sources/zh-Hant.md','繁体原文'),('sources/ja.md','日文原文'),('sources/ko.md','韩文原文'),('sources/en-sdh-cc.md','SDH / CC原文')]
def page(root,route):
    root=Path(root).resolve();name='README.md' if route=='/prime-style-guides' else unquote(route.removeprefix('/subtitle-wiki/'))
    rel=Path(name)
    if rel.is_absolute() or '..' in rel.parts or rel.suffix!='.md':raise ValueError('Unsupported wiki reference')
    path=(root/rel).resolve()
    try:path.relative_to(root)
    except ValueError:raise ValueError('Wiki reference outside root')
    text=path.read_text(encoding='utf-8')
    nav=' · '.join('<a href="/subtitle-wiki/'+html.escape(n,quote=True)+'">'+html.escape(t)+'</a>' for n,t in LINKS if (root/n).is_file())
    title=text.splitlines()[0].lstrip('# ').strip()
    return ('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>'+html.escape(title)+'</title><style>body{max-width:1100px;margin:30px auto;padding:0 20px;font:16px/1.65 system-ui;background:#111923;color:#e8edf4}a{color:#71d8c7}nav{position:sticky;top:0;background:#111923;padding:12px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}</style><nav>'+nav+'</nav><p>只读规范知识库 · 可用浏览器查找关键词 · 归档文字资料不等于已全部程序化</p><pre>'+html.escape(text)+'</pre></html>').encode('utf-8')
