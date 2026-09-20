from pydantic import BaseSettings, Field
from nonebot import get_driver

from .tokenhub_engine import TokenHubEngine


class Config(BaseSettings):
    # Your Config Here
    trans_tencent_enable: bool = Field(default=False)
    trans_tencent_api_base: str = Field(
        default="https://tokenhub.tencentmaas.com/v1")
    trans_tencent_ratelimit: int = Field(default=5)
    trans_tencent_api_key: str = Field(default="")
    trans_tencent_model: str = Field(default="hy-mt2-lite")

    class Config:
        extra = "ignore"


global_config = get_driver().config
config = Config(**global_config.dict())


class TencentEngine(TokenHubEngine):
    """
        腾讯引擎

        腾讯云 TMT 接口下线后，改用内网转发的 TokenHub(混元翻译模型)接口，
        语言表沿用原 TMT 的支持范围。
    """

    def __init__(self) -> None:
        super().__init__(
            name="腾讯",
            enable=config.trans_tencent_enable,
            allow_dict={
                "auto": ["zh-cn", "en", "ja", "ko"],
                "zh-cn": [
                    "zh-tw", "en", "ja", "ko", "fr", "es", "it", "de", "tr",
                    "ru", "pt", "vi", "id", "th", "ms"
                ],
                "zh-tw": [
                    "zh-cn", "en", "ja", "ko", "fr", "es", "it", "de", "tr",
                    "ru", "pt", "vi", "id", "th", "ms"
                ],
                "en": [
                    "zh-cn", "ja", "ko", "fr", "es", "it", "de", "tr", "ru",
                    "pt", "vi", "id", "th", "ms", "ar", "hi"
                ],
                "ja": ["zh-cn", "en", "ko"],
                "ko": ["zh-cn", "en", "ja"],
                "fr": ["zh-cn", "en", "es", "it", "de", "tr", "ru", "pt"],
                "es": ["zh-cn", "en", "fr", "it", "de", "tr", "ru", "pt"],
                "it": ["zh-cn", "en", "fr", "es", "de", "tr", "ru", "pt"],
                "de": ["zh-cn", "en", "fr", "es", "it", "tr", "ru", "pt"],
                "tr": ["zh-cn", "en", "fr", "es", "it", "de", "ru", "pt"],
                "ru": ["zh-cn", "en", "fr", "es", "it", "de", "tr", "pt"],
                "pt": ["zh-cn", "en", "fr", "es", "it", "de", "tr", "ru"],
                "vi": ["zh-cn", "en"],
                "id": ["zh-cn", "en"],
                "th": ["zh-cn", "en"],
                "ms": ["zh-cn", "en"],
                "ar": ["en"],
                "hi": ["en"]
            },
            alias=["tc", "tencent"],
            api_base=config.trans_tencent_api_base,
            api_key=config.trans_tencent_api_key,
            model=config.trans_tencent_model,
            ratelimit=config.trans_tencent_ratelimit)


"""
    腾讯引擎

    接入 TokenHub 的 OpenAI 兼容接口(hy-mt2-lite)，语言表沿用原腾讯云 TMT 的
    支持范围：

        源语言，支持：
    auto：自动识别（识别为一种语言）
    zh：简体中文
    zh-TW：繁体中文
    en：英语
    ja：日语
    ko：韩语
    fr：法语
    es：西班牙语
    it：意大利语
    de：德语
    tr：土耳其语
    ru：俄语
    pt：葡萄牙语
    vi：越南语
    id：印尼语
    th：泰语
    ms：马来西亚语
    ar：阿拉伯语
    hi：印地语

    目标语言的支持范围与语言表`allow_dict`一致，详见该表。
    新接口由模型自动识别源语言，请求中只需要给出目标语言。
"""
