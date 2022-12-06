import asyncio
from datetime import datetime, timedelta, timezone
import time
from typing import Any, Dict, Optional, Type
import aiohttp
import feedparser
from feedparser import FeedParserDict
from requests.exceptions import ConnectTimeout
from aiohttp.client_exceptions import ClientConnectorError
from .data import RssChannelData, RssItemData
from .html_parser import GeneralHTMLParser
from .exception import RssRequestStatusError, RssRequestFailure, RssParserError


class RssParse:
    """
        Rss解析器

        最高兼容性适配

        需要修改时请继承此类进行修改

        需要报错请使用`RssParserError`
    """

    def __init__(
        self,
        GeneralHTMLParserCls: Optional[Type[GeneralHTMLParser]] = None,
        source_type: str = "",
        source_subtype: str = "",
    ) -> None:
        self.htmlparser = GeneralHTMLParserCls or GeneralHTMLParser
        """html解析器"""
        self.source_type = source_type
        self.source_subtype = source_subtype

    def deal_des(self, html_str: str) -> str:
        parser = self.htmlparser()
        parser.feed(html_str)
        return str(parser.message).strip()

    def validate(self, data: RssChannelData) -> bool:
        """
            验证rss数据是否有效

            主要验证 是否包含用于验证更新的必要数据
        """
        if data.updated <= 0:
            return False

        if data.entries:
            if data.entries[0].published <= 0:
                return False

        return True

    def conversion_item(self, data) -> RssItemData:
        """
            uuid: str  # 数据包唯一标识

            guid: str  # rss标准里表达数据包唯一的guid
            link: str  # rss标准需要展示的url
            published: int  # rss标准里数据发布的时间(ms)

            title_full: str  # rss标准里的标题
            author_full: str  # rss标准里的作者
            des_full: str  # rss标准里的描述
            content
        """
        item = RssItemData()
        item.link = getattr(data, "link", None) or ""
        if getattr(data, "published_parsed", None):
            dt = datetime(*data.published_parsed[:6],
                          tzinfo=timezone(timedelta(hours=0)))
            item.published = int(dt.timestamp() * 1000)
        else:
            item.published = 0
        item.guid = getattr(data, "id",
                            None) or F"{item.published}:{item.link}"
        item.title_full = getattr(data, "title", None) or ""
        item.author_full = getattr(data, "author", None) or ""
        item.des_source = getattr(data, "summary", None) or ""
        item.des_full = self.deal_des(item.des_source)
        item.uuid = item.guid
        return item

    def conversion(self,
                   data: FeedParserDict,
                   source_url: str = "") -> RssChannelData:
        """
            source_url: str  # 数据来源url(例：http://rsshub.app/bilibili/partion/28)
            source_type: str  # 数据来源标识(例：rsshub)
            source_subtype: str  # 数据来源子标识(例如：bilibili)
            receive_timestamp: int  # 收到数据的时间戳(ms)

            updated: int  # rss标准里数据发布的时间
            generator: str  # rss标准里的数据生成器

            title_full: str  # rss标准里的频道标题
            author_full: str  # rss标准里的频道所有人
            des_full: str  # rss标准里的描述
            link: str  # rss标准需要展示的url
            entries: List["RssItem"]  # rss标准的items
        """
        channel = RssChannelData()
        channel.source_type = self.source_type
        channel.source_subtype = self.source_subtype
        channel.source_url = source_url
        channel.receive_timestamp = int(time.time() * 1000)
        feed: Any = data.feed
        channel.title_full = getattr(feed, "title", None) or ""
        channel.author_full = getattr(feed, "publisher", None) or getattr(
            feed, "link", None) or ""
        channel.des_source = getattr(feed, "subtitle", None) or ""
        channel.des_full = self.deal_des(channel.des_source)
        channel.link = getattr(feed, "link", None) or ""

        if getattr(feed, "updated_parsed", None):
            dt = datetime(*feed.updated_parsed[:6],
                          tzinfo=timezone(timedelta(hours=0)))
            channel.updated = int(dt.timestamp() * 1000)
        else:
            channel.updated = 0

        channel.generator = getattr(feed, "generator", None) or getattr(
            feed, "link", None) or ""
        channel.entries = list()
        for item in getattr(data, "entries", []):
            channel.entries.append(self.conversion_item(item))
        # 返回前进行排序，保证时间顺序正确
        channel.entries.sort(key=lambda item: item.published, reverse=True)
        channel.uuid = channel.link
        return channel


class Rss:
    """
        Rss 基础解析
    """

    def __init__(self,
                 baseurl: str,
                 path: str,
                 RssParseCls: Optional[Type[RssParse]] = None,
                 headers: Optional[Dict[str, str]] = None,
                 proxy: Optional[str] = None,
                 timeout: Optional[int] = None,
                 source_type: str = "",
                 source_subtype: str = "") -> None:
        """
            - `baseurl` 基础url(可通过`set_baseurl`修改)
            - `path` 路径
            - `RssParseCls` 使用的rss解析器
            - `headers` 请求头 默认 {'User-Agent': 'RSSReadBot V1.0'}
            - `proxy` 代理
        """
        if baseurl.endswith('/'):
            baseurl = baseurl[:-1]
        if not path.startswith('/'):
            path = "/" + path

        self.baseurl = baseurl
        self.path = path
        self.url = f"{self.baseurl}{self.path}"
        self.proxy = proxy
        self.timeout = timeout or 5
        self.headers = headers or {'User-Agent': 'RSSReadBot V1.0'}
        RssParseCls = RssParseCls or RssParse
        self.rss_parse = RssParseCls(source_type=source_type,
                                     source_subtype=source_subtype)

    def set_baseurl(self, baseurl: str):
        """
            更换基础url（兼容多地址）
        """
        self.baseurl = baseurl
        self.url = f"{self.baseurl}{self.path}"

    async def async_http_request(self) -> str:
        async with aiohttp.request(
                "get",
                self.url,
                headers=self.headers,
                proxy=self.proxy,
                timeout=aiohttp.ClientTimeout(total=self.timeout)) as resp:
            code = resp.status
            result = await resp.read()
            if code != 200:
                raise RssRequestStatusError(F'url {self.url} 页面错误 {code}',
                                            cause=Exception(
                                                str(result, "utf-8")))
            return str(result, "utf-8")

    async def read(self) -> RssChannelData:
        # 读取页面数据
        try:
            request_content = await self.async_http_request()
            data: FeedParserDict = feedparser.parse(request_content)
            return self.rss_parse.conversion(data, source_url=self.url)
        except (ConnectTimeout, TimeoutError, asyncio.TimeoutError) as e:
            raise RssRequestFailure(F"url {self.url} => 读取超时！", cause=e)
        except ClientConnectorError as e:
            raise RssRequestFailure(F"url {self.url} => 连接异常！", cause=e)

    async def test(self, validate: bool = True) -> Optional[str]:
        """
            测试连接，如果一切正常则返回None，如果出现错误，则返回错误原因。
        """
        try:
            data = await self.read()
            if validate and not self.rss_parse.validate(data):
                return "此订阅无法通过验证，请联系管理员"
        except RssRequestStatusError:
            return "订阅源访问失败"
        except RssRequestFailure:
            return "连接失败，请检查网络。"
        except RssParserError:
            return "rss解析失败，请联系管理员"
        except Exception:
            return "页面解析出现异常，路径可能不支持rss解析。"
        return None
