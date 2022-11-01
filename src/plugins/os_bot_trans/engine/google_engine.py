import aiohttp
import json
import random
from . import Engine, EngineError
from pydantic import BaseSettings, Field
from nonebot import get_driver


class Config(BaseSettings):
    # Your Config Here
    trans_google_enable: bool = Field(default=False)
    trans_google_baseurl: str = Field(default="https://translate.google.cn")

    class Config:
        extra = "ignore"


global_config = get_driver().config
config = Config(**global_config.dict())


class GoogleEngineError(EngineError):
    """
        腾讯引擎引起的错误
    """
    pass


class GoogleEngine(Engine):
    def __init__(self) -> None:
        alllangs = [
            'af', 'sq', 'am', 'ar', 'hy', 'az', 'eu', 'be', 'bn', 'bs', 'bg',
            'ca', 'ceb', 'zh-cn', 'zh-tw', 'co', 'hr', 'cs', 'da', 'nl', 'en',
            'eo', 'et', 'fi', 'fr', 'fy', 'gl', 'ka', 'de', 'el', 'gu', 'ht',
            'ha', 'haw ', 'he', 'hi', 'hmn', 'hu', 'is', 'ig', 'id', 'ga',
            'it', 'ja', 'jv', 'kn', 'kk', 'km', 'rw', 'ko', 'ku', 'ky', 'lo',
            'la', 'lv', 'lt', 'lb', 'mk', 'mg', 'ms', 'ml', 'mt', 'mi', 'mr',
            'mn', 'my', 'ne', 'no', 'ny', 'or', 'ps', 'fa', 'pl', 'pt', 'pa',
            'ro', 'ru', 'sm', 'gd', 'sr', 'st', 'sn', 'sd', 'si', 'sk', 'sl',
            'so', 'es', 'su', 'sw', 'sv', 'tl', 'tg', 'ta', 'tt', 'te', 'th',
            'tr', 'tk', 'uk', 'ur', 'ug', 'uz', 'vi', 'cy', 'xh', 'yi', 'yo',
            'zu'
        ]
        allowDict = {}
        for lang in alllangs:
            allowDict[lang] = alllangs
        allowDict["auto"] = alllangs
        super().__init__("谷歌", config.trans_google_enable, allowDict, {},
                         ["google", "谷歌翻译"])
        self._trans_google_baseurl = config.trans_google_baseurl

    @staticmethod
    def randUserAgent():
        UAs = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.117 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.77 Safari/537.36',
            'Mozilla/5.0 (X11; Ubuntu; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2919.83 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_8_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2866.71 Safari/537.36',
            'Mozilla/5.0 (X11; Ubuntu; Linux i686 on x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/53.0.2820.59 Safari/537.36',
            'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:53.0) Gecko/20100101 Firefox/53.0'
        ]
        return UAs[random.randint(0, len(UAs) - 1)]

    async def google_MachineTrans(self,
                                  SourceText,
                                  Source='auto',
                                  Target='zh'):
        url = (
            self._trans_google_baseurl
            if self._trans_google_baseurl else "https://translate.google.cn"
        ) + "/translate_a/single?client=at&dt=t&dj=1&ie=UTF-8&sl={Source}&tl={Target}&q={SourceText}"
        headers = {
            "referer": "https://translate.google.cn/",
            "content-type": "application/x-www-form-urlencoded",
            "Accept": "application/json, text/plain, */*",
            'X-Requested-With': 'XMLHttpRequest',
            'User-Agent': self.randUserAgent()
        }
        requrl = url.format(SourceText=SourceText,
                            Source=Source,
                            Target=Target)
        try:
            async with aiohttp.request("get", url=requrl,
                                       headers=headers) as resp:
                code = resp.status
                if code != 200:
                    raise GoogleEngineError(
                        F"网络异常！ code {code} - 待翻内容 ({Source}-{Target}) {SourceText}",
                        replay=f"响应异常 {code}")
                res = json.loads(await resp.read())
                try:
                    msg = ''
                    for t in res['sentences']:
                        msg = msg + t['trans']
                    return msg
                except Exception:
                    raise GoogleEngineError(
                        F"处理翻译结果时异常！ 待翻内容 ({Source}-{Target}) {SourceText} 响应结果 {res}",
                        replay="翻译结果解析异常！")
        except EngineError as e:
            raise e
        except Exception as e:
            raise GoogleEngineError(
                F"谷歌引擎连接异常！ 待翻内容 ({Source}-{Target}) {SourceText} 错误 {e}",
                replay="网络异常！")

    async def trans(self, source: str, target: str, content: str) -> str:
        if not self.enable:
            raise EngineError("引擎未启用", replay="引擎未启用")
        source = self.conversion_lang(source)
        target = self.conversion_lang(target)
        return await self.google_MachineTrans(content, source, target)
