from dataclasses import dataclass, field
from typing import List


@dataclass
class RssChannelData:
    """
        Rss标准channel数据
    """
    uuid: str = field(default="")  # 频道唯一标识
    source_url: str = field(
        default="")  # 数据来源url(例：http://rsshub.app/bilibili/partion/28)
    source_type: str = field(default="")  # 数据来源标识(例：rsshub)
    source_subtype: str = field(default="")  # 数据来源子标识(例如：bilibili)
    receive_timestamp: int = field(default=0)  # 收到数据的时间戳(ms)

    updated: int = field(default=0)  # rss标准里数据发布的时间
    generator: str = field(default="")  # rss标准里的数据生成器

    title_full: str = field(default="")  # rss标准里的频道标题
    author_full: str = field(default="")  # rss标准里的频道所有者
    des_source: str = field(default="")  # rss标准里的描述(未经过parse处理)
    des_full: str = field(default="")  # rss标准里的描述(纯文本)
    link: str = field(default="")  # rss标准需要展示的url
    entries: List["RssItemData"] = field(default_factory=list)  # rss标准的items


@dataclass
class RssItemData:
    """
        Rss标准Item数据

        由原始数据标准化得出
        用于输出可用信息的封装数据
    """
    uuid: str = field(default="")  # 数据包唯一标识

    guid: str = field(default="")  # rss标准里表达数据包唯一的guid
    link: str = field(default="")  # rss标准需要展示的url
    published: int = field(default=0)  # rss标准里数据发布的时间(ms)

    title_full: str = field(default="")  # rss标准里的标题
    author_full: str = field(default="")  # rss标准里的作者
    des_source: str = field(default="")  # rss标准里的描述(未经过parse处理)
    des_full: str = field(default="")  # rss标准里的描述(纯文本)
