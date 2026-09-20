from pydantic import BaseSettings, Field
from nonebot import get_driver

from .tokenhub_engine import TokenHubEngine


class Config(BaseSettings):
    # Your Config Here
    trans_tencent_ai_enable: bool = Field(default=False)
    trans_tencent_ai_api_base: str = Field(
        default="https://tokenhub.tencentmaas.com/v1")
    trans_tencent_ai_ratelimit: int = Field(default=5)
    trans_tencent_ai_api_key: str = Field(default="")
    trans_tencent_ai_model: str = Field(default="hy-mt2-lite")

    class Config:
        extra = "ignore"


global_config = get_driver().config
config = Config(**global_config.dict())


class TencentAiEngine(TokenHubEngine):
    """
        智能腾讯引擎

        腾讯云混元翻译接口下线后，改用内网转发的 TokenHub(混元翻译模型)接口，
        语言表沿用原混元翻译的支持范围。
    """

    def __init__(self) -> None:

        alllangs = [
            'zh-cn', 'zh-tw', 'zh-yue', 'ja', "ko", "es", "fr", "th",
            "ar", "ru", "pt", "de", "it", "en"
        ]
        allowDict = {}
        for lang in alllangs:
            allowDict[lang] = alllangs
        allowDict["auto"] = alllangs

        super().__init__(
            name="智能腾讯",
            enable=config.trans_tencent_ai_enable,
            allow_dict=allowDict,
            alias=["aitc", "aitencent", "ai腾讯", "AI腾讯"],
            api_base=config.trans_tencent_ai_api_base,
            api_key=config.trans_tencent_ai_api_key,
            model=config.trans_tencent_ai_model,
            ratelimit=config.trans_tencent_ai_ratelimit)


"""
    智能腾讯引擎

    接入 TokenHub 的 OpenAI 兼容接口(hy-mt2-lite)，语言表沿用原混元翻译的支持范围，
    各语言之间互通：

    简体中文：zh-cn，繁体中文：zh-tc，粤语：zh-yue，英语：en，法语：fr，
    葡萄牙语：pt，西班牙语：es，日语：ja，俄语：ru，阿拉伯语：ar，韩语：ko，
    泰语：th，意大利语：it，德语：de

    新接口由模型自动识别源语言，请求中只需要给出目标语言。
"""
