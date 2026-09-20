"""
    TokenHub(混元 Hy-MT2)翻译引擎共享实现

    腾讯云 TMT(tmt.tencentcloudapi.com)与混元翻译(hunyuan.tencentcloudapi.com)
    接口即将下线，两个腾讯引擎统一改用内网转发的 TokenHub OpenAI 兼容接口
    (POST {api_base}/chat/completions)。

    该模型是专用翻译模型，没有默认系统提示词，必须带上翻译指令，
    直接把原文当对话发过去会被当成聊天内容回复。
"""

import json
from typing import Dict, List, Union

import aiohttp

from . import Engine
from ..exception import EngineError, RatelimitException
from ...os_bot_base.util import AsyncTokenBucket

# 单次翻译的文本长度上限(字符)，超过则提示用户分段
MAX_TEXT_LENGTH = 2000

# 请求超时(秒)
REQUEST_TIMEOUT = 60

# 翻译指令，改写自 Hy-MT2 官方模板。官方示例把指令与原文放在同一条 user 消息里，
# 这里用 system 角色承载指令、原文单独作为 user 消息，实测两种形态在网关上均可用。
SYSTEM_PROMPT = ("将以下文本翻译为{target}，注意只需要输出翻译后的结果，不要额外解释。"
                 "输出必须全部使用{target}，不要输出源语言或原文")

# prompt 中使用的目标语言名。
# 实测中文名最稳定：英文名"Traditional Chinese"会被忽略(仍输出简体)、
# "Cantonese"会输出英语，而"繁体中文"、"粤语"均正确。
LANG_PROMPT_NAMES: Dict[str, str] = {
    "zh-cn": "简体中文",
    "zh-tc": "繁体中文",
    "zh-tw": "繁体中文",
    "zh-yue": "粤语",
    "zh-wyw": "文言文",
    "en": "英语",
    "ja": "日语",
    "ko": "韩语",
    "fr": "法语",
    "es": "西班牙语",
    "it": "意大利语",
    "de": "德语",
    "tr": "土耳其语",
    "ru": "俄语",
    "pt": "葡萄牙语",
    "vi": "越南语",
    "id": "印度尼西亚语",
    "th": "泰语",
    "ms": "马来语",
    "ar": "阿拉伯语",
    "hi": "印地语",
}


def alias_lang_keys(allow_dict: Dict[str, Union[List[str],
                                                str]]) -> Dict[str, Union[List[str], str]]:
    """
        langs 中繁体中文的语言标识为`zh-tc`，而腾讯引擎的语言表沿用旧接口的`zh-tw`，
        导致用户输入"繁体中文"匹配不到语言表。这里让两个标识互为别名：
        语言表的键与各键的目标语言列表都要认这两个标识。
    """
    result: Dict[str, Union[List[str], str]] = {}
    for key, value in allow_dict.items():
        if isinstance(value, list):
            target_list = list(value)
            for src, dst in (("zh-tw", "zh-tc"), ("zh-tc", "zh-tw")):
                if src in target_list and dst not in target_list:
                    target_list.append(dst)
            result[key] = target_list
        else:
            result[key] = value
    for src, dst in (("zh-tw", "zh-tc"), ("zh-tc", "zh-tw")):
        if src in result and dst not in result:
            result[dst] = result[src]
    return result


class TokenHubEngineError(EngineError):
    """
        TokenHub引擎引起的错误
    """
    pass


class TokenHubEngine(Engine):
    """
        TokenHub OpenAI 兼容接口翻译引擎基类

        子类只需要提供名称、别名、语言表与各自的接口配置。
    """

    def __init__(self, name: str, enable: bool,
                 allow_dict: Dict[str, Union[List[str], str]], alias: List[str],
                 api_base: str, api_key: str, model: str,
                 ratelimit: int) -> None:
        super().__init__(name=name,
                         enable=enable,
                         allow_dict=alias_lang_keys(allow_dict),
                         change_dict={},
                         alias=alias)
        self._api_base = api_base.strip().rstrip("/")
        self._api_key = api_key
        self._model = model
        if self.enable and (not self._api_base or not self._api_key):
            raise EngineError("请设置接口地址与密钥后再启用此引擎！")
        self.bucket = AsyncTokenBucket(ratelimit, 1, 0, int(ratelimit) or 1)

    def prompt_lang_name(self, lang: str) -> str:
        """
            语言标识转为 prompt 中使用的语言名
        """
        return LANG_PROMPT_NAMES.get(lang, lang)

    async def tokenhub_text_translate(self, target: str, content: str) -> dict:
        """
            调用 TokenHub 的 chat/completions 接口
        """
        url = F"{self._api_base}/chat/completions"
        headers = {
            "Authorization": F"Bearer {self._api_key}",
            "Content-Type": "application/json; charset=utf-8"
        }
        params = {
            "model": self._model,
            "stream": False,
            "messages": [{
                "role": "system",
                "content": SYSTEM_PROMPT.format(target=target)
            }, {
                "role": "user",
                "content": content
            }]
        }
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        async with aiohttp.request("post",
                                   url,
                                   headers=headers,
                                   data=json.dumps(params,
                                                   ensure_ascii=False),
                                   timeout=timeout) as resp:
            code = resp.status
            body = await resp.read()
        if code != 200:
            raise TokenHubEngineError(
                F"网络异常 - {code} 待翻内容 ({target}) {content} 响应 {body!r}",
                replay=F"接口错误 {code}")
        try:
            return json.loads(body)
        except Exception as e:
            raise TokenHubEngineError(
                F"响应解析异常 待翻内容 ({target}) {content} 响应 {body!r} 错误 {e}",
                replay="接口响应异常！")

    async def trans(self, source: str, target: str, content: str) -> str:
        if not self.enable:
            raise EngineError("引擎未启用", replay="引擎未启用")
        content = content.strip()
        if not content:
            raise TokenHubEngineError("待翻译内容为空", replay="没有可以翻译的内容哦")
        if len(content) > MAX_TEXT_LENGTH:
            raise TokenHubEngineError(
                F"待翻内容过长({len(content)}字) 上限{MAX_TEXT_LENGTH}字",
                replay=F"文本超过{MAX_TEXT_LENGTH}字啦，拆开来再翻译吧")
        if not await self.bucket.wait_consume(1, 5):
            raise RatelimitException("速率限制！")
        # 该模型自动识别源语言，prompt 中只需要给出目标语言
        target_name = self.prompt_lang_name(target)
        try:
            res = await self.tokenhub_text_translate(target_name, content)
        except EngineError as e:
            raise e
        except Exception as e:
            raise TokenHubEngineError(
                F"网络连接异常 待翻内容 ({source}-{target}) {content} 错误 {e}",
                replay="网络状态异常！")
        try:
            choice = res["choices"][0]
            text: str = choice["message"]["content"]
        except Exception as e:
            raise TokenHubEngineError(
                F"响应异常 待翻内容 ({source}-{target}) {content} 响应 {res} 错误 {e}",
                replay="接口响应异常！")
        if choice.get("finish_reason") == "length":
            raise TokenHubEngineError(
                F"译文被截断 待翻内容 ({source}-{target}) {content} 响应 {res}",
                replay="译文太长被截断了，拆开来再翻译吧")
        text = text.strip()
        if not text:
            raise TokenHubEngineError(
                F"译文为空 待翻内容 ({source}-{target}) {content} 响应 {res}",
                replay="没有得到译文，稍后再试试吧")
        return text
