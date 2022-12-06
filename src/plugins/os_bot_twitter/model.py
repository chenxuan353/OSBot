from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from tortoise.models import Model
from tortoise import fields
from ..os_bot_base import DatabaseManage


class TweetTypeEnum(Enum):
    tweet = "发推"
    retweet = "转推"
    quote = "转评"
    replay = "回复"
    quote_replay = "带推回复"


class TwitterTweetModel(Model):

    class Meta:
        table = "os_twitter_tweet"
        table_description = "推特推文表"

    id = fields.CharField(pk=True, max_length=255, description="推文唯一标识")
    author_id: str = fields.CharField(index=True,
                                      max_length=255,
                                      description="发布推文的用户")
    author_name: str = fields.CharField(null=True,
                                        max_length=255,
                                        description="发布推文的用户昵称")
    """发布推文的用户昵称"""
    author_username: str = fields.CharField(null=True,
                                            max_length=255,
                                            description="发布推文的用户名")
    """发布推文的用户名"""
    text: str = fields.TextField(description="内容")
    display_text: str = fields.TextField(description="解析后的内容(用于展示)")
    trans_text: Optional[str] = fields.TextField(null=True,
                                                 description="推文的机器翻译")
    type: TweetTypeEnum = fields.CharEnumField(
        index=True,
        enum_type=TweetTypeEnum,
        max_length=255,
        default=TweetTypeEnum.tweet,
        description="推文类型 用于区分 发推、转推、转评、回复")
    minor_data: bool = fields.BooleanField(
        index=True, null=False, default=True,
        description="次生数据，次生数据可能不完整。")  # type: ignore
    """
        推文数据包含在响应的`includes`中时此字段应为true(转推涉及的tweet除外)

        为真表明此推文的数据很可能有所缺失
    """
    auto: bool = fields.BooleanField(description="是否来自自动更新")  # type: ignore
    """来自自动更新的数据？(自动更新的数据被认为时效性更佳)"""
    trans: bool = fields.BooleanField(default=False,
                                      description="是否包含人工翻译")  # type: ignore
    """被烤过的推文将置为True"""
    relate_trans: fields.ReverseRelation["TwitterTransModel"]
    possibly_sensitive: bool = fields.BooleanField(
        index=True, null=False, description="是否敏感")  # type: ignore
    """该字段表示内容可能被识别为敏感内容。"""
    retweet_count: int = fields.IntField(default=-1, description="转推数")
    reply_count: int = fields.IntField(default=-1, description="回复数")
    like_count: int = fields.IntField(default=-1, description="点赞数")
    quote_count: int = fields.IntField(default=-1, description="转评数")
    reply_settings: str = fields.CharField(
        null=True,
        max_length=255,
        description="回复设置 everyone, mentioned_users, followers")
    """
        回复设置

        everyone, mentioned_users, followers
        所有人，提及的用户，粉丝
    """
    conversation_id: Optional[str] = fields.CharField(
        index=True, null=True, max_length=255, description="原始推文ID（回复、回复的回复等）")
    """对话的原始推文的推文 ID（包括直接回复、回复的回复）"""
    referenced_tweet_id: Optional[str] = fields.CharField(
        index=True, null=True, max_length=255, description="引用的推文ID")
    referenced_tweet_author_id: Optional[str] = fields.CharField(
        index=True, null=True, max_length=255, description="引用的推文作者ID")
    """引用的推文作者ID(存在referenced_tweet_id也可能为空)"""
    referenced_tweet_author_name: str = fields.CharField(
        max_length=255, null=True, description="引用的推文作者昵称")
    """引用的推文作者昵称"""
    referenced_tweet_author_username: str = fields.CharField(
        max_length=255, null=True, description="引用的推文作者名")
    """引用的推文作者名"""

    lang: Optional[str] = fields.CharField(null=True,
                                           max_length=255,
                                           description="推文的语言（如果被Twitter检测到）")
    """推文的语言（如果被 Twitter 检测到）。作为 BCP47 语言标签返回。"""

    mentions: List[str] = fields.JSONField(default=list, description="提及的人")
    """
        提及的人

        包含提及的人ID
    """

    poll: Dict[str,
               Any] = fields.JSONField(default=dict,
                                       description="此字段以JSON形式存储，此推文包含的投票")
    """
        通过 attachments.poll_ids
        包含在响应的`includes`中，需要程序解析到此字段中
        ```
        {
            "id": "1199786642468413448",
            "voting_status": "closed",
            "duration_minutes": 1440,
            "options": [
                {
                    "position": 1,
                    "label": "“C Sharp”",
                    "votes": 795
                },
                {
                    "position": 2,
                    "label": "“C Hashtag”",
                    "votes": 156
                }
            ],
            "end_datetime": "2019-11-28T20:26:41.000Z"
        }
        ```
    """
    medias: List[Dict[str, Any]] = fields.JSONField(
        default=dict, description="此字段以JSON形式存储，此推文包含的媒体")
    """
        此推文包含的媒体对象
        包含在响应的`includes`中，需要程序解析到此字段中
        ```
        [
            {
                "duration_ms": 46947, // 类型为视频时可用。视频的持续时间（以毫秒为单位）。
                "type": "video", // 媒体类型 animated_gif, photo, video
                "height": 1080,
                "media_key": "13_1263145212760805376",
                "url": "...", // 推特媒体的跳转链接
                "public_metrics": { // 请求时媒体内容的公共参与度指标。(确定附加到推文的媒体的总观看次数。)
                    "view_count": 6909260
                },
                "preview_image_url": "https://pbs.twimg.com/media/EYeX7akWsAIP1_1.jpg", // 此内容的静态占位符预览的 URL。
                "width": 1920,
                "variants": [ // 每个媒体对象可能有多个显示或播放变体，具有不同的分辨率或格式
                    {
                    "bit_rate": 632000,
                    "content_type":"video/mp4",
                    "url": "https://video.twimg.com/ext_tw_video/1527322141724532740/pu/vid/320x568/lnBaR2hCqE-R_90a.mp4?tag=12"
                    }
                ]
            },
            ...
        ]
        ```
    """
    source: Optional[str] = fields.TextField(
        null=True, description="此字段以JSON形式存储，最后一次更新收到的推文数据原始Json")
    created_at: datetime = fields.DatetimeField(description="推文创建时间")
    update_time: datetime = fields.DatetimeField(auto_now=True,
                                                 description="推文数据更新时间")
    save_time: datetime = fields.DatetimeField(auto_now_add=True,
                                               description="推文入库时间")


class TwitterUserModel(Model):

    class Meta:
        table = "os_twitter_user"
        table_description = "推特用戶表"

    id: str = fields.CharField(pk=True, max_length=255, description="用户ID")
    name: str = fields.CharField(index=True, max_length=255, description="展示名")
    """昵称"""
    username: str = fields.CharField(index=True,
                                     max_length=255,
                                     description="用户名")
    """用户名"""
    profile_image_url: str = fields.CharField(max_length=255,
                                              description="用户的个人资料图片的 URL")
    description: Optional[str] = fields.TextField(null=True,
                                                  description="个人资料描述")
    protected: bool = fields.BooleanField(
        description="此用户是否选择保护他们的推文")  # type: ignore

    verified: bool = fields.BooleanField(
        description="用户是否经过验证")  # type: ignore
    followers_count: int = fields.IntField(default=-1, description="粉丝数")
    """粉丝数"""
    following_count: int = fields.IntField(default=-1, description="关注数")
    """关注数"""
    tweet_count: int = fields.IntField(default=-1, description="发布的推文（包括转推）数")
    listed_count: int = fields.IntField(default=-1, description="包含此用户的列表数")
    """包含此用户的列表数"""
    pinned_tweet_id: str = fields.CharField(index=True,
                                            max_length=255,
                                            description="用户置顶推文ID")
    source: Optional[str] = fields.TextField(
        null=True, description="此字段以JSON形式存储，最后一次更新收到的用户数据原始Json")
    created_at: datetime = fields.DatetimeField(description="用户更新时间")
    update_time: datetime = fields.DatetimeField(auto_now=True,
                                                 description="用户更新时间")
    save_time: datetime = fields.DatetimeField(auto_now_add=True,
                                               description="用户入库时间")


class TwitterSubscribeModel(Model):

    class Meta:
        table = "os_twitter_subscribe"
        table_description = "推特订阅表"

    id = fields.IntField(pk=True)
    group_mark: str = fields.CharField(index=True,
                                       max_length=255,
                                       description="组掩码标识")
    subscribe: str = fields.CharField(index=True,
                                      max_length=255,
                                      description="订阅的用户ID")
    drive_mark: str = fields.CharField(max_length=255, description="驱动标识")
    bot_type: str = fields.CharField(max_length=255, description="关联的Bot标识")
    bot_id: str = fields.CharField(max_length=255, description="关联的BotID")
    send_param: Dict[str, Any] = fields.JSONField(
        description="此字段以JSON形式存储，发送消息时的参数")

    tweet_trans: bool = fields.BooleanField(
        default=False, description="推送时翻译(机翻)")  # type: ignore
    update_mention: bool = fields.BooleanField(
        default=False, description="相关推送")  # type: ignore
    update_retweet: bool = fields.BooleanField(
        default=False, description="转推推送")  # type: ignore
    update_quote: bool = fields.BooleanField(
        default=False, description="转评推送")  # type: ignore
    update_replay: bool = fields.BooleanField(
        default=False, description="回复推送")  # type: ignore
    update_name: bool = fields.BooleanField(
        default=False, description="昵称更新推送")  # type: ignore
    update_description: bool = fields.BooleanField(
        default=False, description="描述更新推送")  # type: ignore
    update_profile: bool = fields.BooleanField(
        default=False, description="头像更新推送")  # type: ignore
    update_followers: bool = fields.BooleanField(
        default=False, description="粉丝数更新推送")  # type: ignore
    change_time: datetime = fields.DatetimeField(auto_now=True,
                                                 description="修改时间")
    create_time: datetime = fields.DatetimeField(auto_now_add=True,
                                                 description="创建时间")


class TwitterTransModel(Model):

    class Meta:
        table = "os_twitter_trans"
        table_description = "推特烤推表"

    id = fields.IntField(pk=True)
    group_mark: str = fields.CharField(index=True,
                                       max_length=255,
                                       description="组掩码标识")
    subscribe: Optional[str] = fields.CharField(index=True,
                                                null=True,
                                                max_length=255,
                                                description="关联的订阅用户")
    username: str = fields.CharField(index=True,
                                     null=True,
                                     max_length=255,
                                     description="关联用户名")
    tweet_id: str
    tweet: fields.ForeignKeyRelation[
        TwitterTweetModel] = fields.ForeignKeyField(
            f"models.TwitterTweetModel",
            null=True,
            related_name="relate_trans",
            db_constraint=False,
            index=True,
            description="关联的推文ID")
    drive_mark: str = fields.CharField(index=True,
                                       max_length=255,
                                       description="驱动标识")
    bot_type: str = fields.CharField(index=True,
                                     max_length=255,
                                     description="关联的Bot标识")
    bot_id: str = fields.CharField(index=True,
                                   max_length=255,
                                   description="关联的BotID")
    user_id: str = fields.CharField(index=True,
                                    max_length=255,
                                    description="产生此操作的用户ID")
    trans_text: str = fields.TextField(description="推文的翻译")
    file_name: str = fields.CharField(max_length=255,
                                      description="关联文件名,可能因自动清理失效。")
    create_time: datetime = fields.DatetimeField(auto_now_add=True,
                                                 description="创建时间")


DatabaseManage.get_instance().add_model(TwitterTweetModel)
DatabaseManage.get_instance().add_model(TwitterUserModel)
DatabaseManage.get_instance().add_model(TwitterSubscribeModel)
