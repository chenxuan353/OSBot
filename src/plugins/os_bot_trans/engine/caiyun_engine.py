import aiohttp
import json
from pydantic import BaseSettings, Field
from nonebot import get_driver
from . import Engine, EngineError


class Config(BaseSettings):
    # Your Config Here
    trans_caiyun_enable: bool = Field(default=False)
    trans_caiyun_token: str = Field(default="")

    class Config:
        extra = "ignore"


global_config = get_driver().config
config = Config(**global_config.dict())


class CaiyunEngineError(EngineError):
    """
        彩云小译引擎引起的错误
    """
    pass


class CaiyunEngine(Engine):

    def __init__(self) -> None:
        super().__init__("彩云小译",
                         config.trans_caiyun_enable,
                         allow_dict={
                             "auto": ["zh-cn"],
                             "zh-cn": ["en", "ja"],
                             "en": ["zh-cn"],
                             "ja": ["zh-cn"]
                         },
                         change_dict={"zh-cn": "zh"},
                         alias=["caiyun", "cy", "彩云"])
        self._token = config.trans_caiyun_token
        if self.enable and not self._token:
            raise EngineError("请设置密钥后再启用此引擎！")

    async def tranlate(self, source, direction):
        if not self._token:
            raise CaiyunEngineError("彩云引擎未配置token!")
        url = "http://api.interpreter.caiyunai.com/v1/translator"
        token = self._token
        payload = {
            "source": source,
            "trans_type": direction,
            "request_id": "demo",
            "detect": True,
        }

        headers = {
            'content-type': "application/json",
            'x-authorization': "token " + token,
        }
        try:
            async with aiohttp.request("post",
                                       url,
                                       data=json.dumps(payload),
                                       headers=headers) as resp:
                code = resp.status
                res = json.loads(await resp.read())
                if code != 200:
                    raise CaiyunEngineError(
                        F"网络异常！ code {code} - 待翻内容 ({direction}) {source}",
                        replay=f"响应异常 {code}")
                result = ""
                for i in range(len(res["target"])):
                    result += "\n" + res["target"][i]
                return result
        except EngineError as e:
            raise e
        except Exception as e:
            raise CaiyunEngineError(f"网络连接异常：{e}", replay="网络连接异常")

    async def trans(self, source: str, target: str, content: str) -> str:
        if not self.enable:
            raise EngineError("引擎未启用", replay="引擎未启用")
        source = self.conversion_lang(source)
        target = self.conversion_lang(target)
        direction = F"{source}2{target}"
        t_source = content.split("\n")
        return await self.tranlate(t_source, direction)
