from html.parser import HTMLParser
from typing import Any, Callable, Dict, List, Optional
"""
    HTML解析器
    用于将html解析为适合显示的text文本
    并收集部分数据
"""


class GeneralHTMLParser(HTMLParser):
    """
        通用解析器

        用于将RSS中的描述html解析为消息
    """

    def __init__(self,
                 *,
                 handle_text: Optional[Callable[[str], Any]] = None,
                 handle_image: Optional[Callable[[str], Any]] = None,
                 handle_rstrip: Optional[Callable[[Any], Any]] = None,
                 convert_charrefs: bool = True) -> None:
        super().__init__(convert_charrefs=convert_charrefs)
        """
            - `handle_text` 文本处理，返回值不为空时将加到`self.message`尾部
            - `handle_image` 媒体处理，返回值不为空时将加到`self.message`尾部
            - `handle_rstrip` 文本处理-移除右边的空行，返回值将替换`self.message`
            - `convert_charrefs` 是否转换字符引用为原字符
        """
        self.message: Any = ""
        self.images: List[str] = []

        self.handle_text = handle_text or (lambda data: data)
        self.handle_image = handle_image or (lambda _: None)
        self.handle_rstrip = handle_rstrip or (lambda msg: str(msg).rstrip())
        self.allow_tags = ('???', "div", "img", "br", "hr", "p", "h1", "h2", "h3",
                           "h4", "h5", "li", "tr", "span", "strong", "em", "i",
                           "b", "u", "ins", "pre", "ol", "small")
        """标识哪些tag需要处理，不在此列表的tag会被忽略"""

    def handle_starttag(self, tag: str, attrs: Dict[str, str]):
        if tag not in self.allow_tags:
            return
        if tag in ["p", "h1", "h2", "h3", "h4", "h5", "li", "tr"]:
            self.message = self.handle_rstrip(self.message)
            self.message += self.handle_text("\n") or ""
        elif tag == "a":
            self.message += self.handle_text(" ") or ""
        elif tag == 'img':
            self.handle_img(dict(attrs))

    def handle_endtag(self, tag: str):
        if tag not in self.allow_tags:
            return

    def handle_data(self, data: str):
        if self.lasttag and self.lasttag not in self.allow_tags:
            return
        if not data.strip():
            # 移除无意义的空格
            return
        self.message += self.handle_text(data) or ""

    def handle_comment(self, data):
        pass

    def handle_startendtag(self, tag: str, attrs: Dict[str, str]):
        if self.lasttag not in self.allow_tags:
            return
        if tag == "br":
            self.message = self.handle_rstrip(self.message)
            self.message += self.handle_text("\n") or ""
        elif tag == "hr":
            self.message = self.handle_rstrip(self.message)
            self.message += self.handle_text("\n--------\n") or ""

        if tag == 'img':
            self.handle_img(dict(attrs))

    def handle_img(self, attrs: Dict[str, str]):
        # base64://
        # data:image/gif;base64,
        src = ""
        src = attrs.get('src', src)
        src = src or attrs.get('data-src', src)

        if src.startswith('data:image/'):
            src = 'base64://' + src[src.index('base64,') + len('base64,'):]
        elif not src.startswith('http'):
            # 安全起见，不以http或bs64起始的链接强制使用https://
            if src.startswith('//'):
                src = src[2:]
            elif src.startswith('/'):
                src = src[1:]
            src = f"https://{src}"
        if src:
            self.message += self.handle_image(src) or ""
            self.images.append(src)
