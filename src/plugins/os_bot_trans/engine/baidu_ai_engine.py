import aiohttp
import json
import random
from hashlib import md5
from pydantic import BaseSettings, Field
from nonebot import get_driver
from . import Engine, EngineError
from ..exception import RatelimitException
from ...os_bot_base.util import AsyncTokenBucket


class Config(BaseSettings):
    # Your Config Here
    trans_baidu_ai_enable: bool = Field(default=False)
    trans_baidu_ai_ratelimit: int = Field(default=1)
    trans_baidu_ai_id: str = Field(default="")
    trans_baidu_ai_secret: str = Field(default="")

    class Config:
        extra = "ignore"


global_config = get_driver().config
config = Config(**global_config.dict())


class BaiduAiEngineError(EngineError):
    """
        百度引擎引起的错误
    """
    pass


class BaiduAiEngine(Engine):

    def __init__(self) -> None:
        alllangs = [
            'zh-cn', 'zh-tw', 'zh-yue', 'zh-wyw', 'ja', "ko", "es", "fr", "th",
            "ar", "ru", "pt", "de", "it", "el", "nl", "pl", "bg", "et", "da",
            "fi", "cs", "ro", "sl", "swe", "hu", "vi", "en"
        ]
        allowDict = {}
        for lang in alllangs:
            allowDict[lang] = alllangs
        allowDict["auto"] = alllangs
        change_dict = {
            "zh-cn": "zh",
            "zh-tw": "cht",
            "zh-yue": "yue",
            "zh-wyw": "wyw",
            "ja": "jp",
            "ko": "kor",
            "fr": "fra",
            "es": "spa",
            "ar": "ara",
            "bg": "bul",
            "et": "est",
            "da": "dan",
            "fi": "fin",
            "ro": "rom",
            "sl": "slo",
            "sv": "swe",
            "vi": "vie",
        }
        super().__init__(name="百度AI",
                         enable=config.trans_baidu_ai_enable,
                         allow_dict=allowDict,
                         change_dict=change_dict,
                         alias=["baiduai", "bdai", "baiai"])
        self._secret_id = config.trans_baidu_ai_id
        self._secret_key = config.trans_baidu_ai_secret
        if self.enable and (not self._secret_id or not self._secret_key):
            raise EngineError("请设置密钥后再启用此引擎！")
        self.bucket = AsyncTokenBucket(config.trans_baidu_ai_ratelimit, 1, 0,
                                       int(config.trans_baidu_ai_ratelimit) or 1)

    async def baidu_errcode(self, code):
        """
            详情参考 https://fanyi-api.baidu.com/product/133
        """
        errstr = {
            "52000": ["成功", "——"],
            "52001": ["请求超时", "检查传入的 q 参数是否是正常文本，以及 from 或 to 参数是否在支持的语种列表中"],
            "52002": ["系统错误", "请重试"],
            "52003": ["未授权用户", "请检查appid是否正确，或是否已开通对应服务服务是否开通"],
            "54000": ["必填参数为空", "请检查是否漏传、误传参数"],
            "54001": ["签名错误或token错误", "请检查签名生成方法，或token填写是否正确"],
            "54003": ["访问频率受限", "请降低您的调用频率，或在管理控制台进行身份认证后切换为高级版/尊享版"],
            "54004": ["账户余额不足", "请前往管理控制台为账户充值。如后台显示还有余额，说明当天用量计费金额已超过账户余额"],
            "54005": ["长query请求频繁", "请降低长度大于1万字节query的发送频率，3s后再试"],
            "58000": ["客户端IP非法", "检查开发者信息页面填写的对应服务器IP地址是否正确，如服务器为动态IP，建议留空不填"],
            "58001": ["译文语言方向不支持", "检查译文语言是否在语言列表里，个人标准版和高级版支持28个常见语种，企业尊享版支持全部语种"],
            "58002": ["服务当前已关闭", "请前往管理控制台开启服务"],
            "58003": ["此IP已被封禁", "同一IP当日使用多个APPID发送翻译请求，则该IP将被封禁当日请求权限，次日解封。请勿将APPID和密钥填写到第三方软件中。"],
            "58004": ["模型参数错误", "检查model_tyep是否为“llm”或“nmt”"],
            "59002": ["翻译指令过长", "reference参数超过500字符上限"],
            "59003": ["请求文本过长", "q参数超过6000字符上限"],
            "59004": ["QPS超限", "当前接口QPS已触及上限"],
            "59005": ["tag_handling 参数非法", "确认参数为0或1"],
            "59006": ["标签解析失败", "标签未闭合或为空"],
            "59007": ["ignore_tags长度超限", "长度上限为20"],
            "90107": ["认证未通过或未生效", "请前往我的认证查看认证进度"],
            "20003": ["请求内容存在安全风险", "请检查请求文本是否涉及反动，暴力等相关内容"]
        }
        return errstr[code]

    async def baidu_trans_request(self, source: str, target: str, text: str):
        endpoint = 'https://fanyi-api.baidu.com'
        path = '/ait/api/aiTextTranslate'
        appid = self._secret_id
        appkey = self._secret_key
        url = endpoint + path

        def make_md5(s, encoding='utf-8'):
            return md5(s.encode(encoding)).hexdigest()

        salt = random.randint(32768, 65536)
        sign = make_md5(appid + text + str(salt) + appkey)

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        payload = {
            'appid': appid,
            'q': text,
            'from': source,
            'to': target,
            'salt': salt,
            'sign': sign
        }

        req = aiohttp.request("post", url, params=payload, headers=headers)
        async with req as resp:
            code = resp.status
            if code != 200:
                raise BaiduAiEngineError(
                    F"网络异常 - {code} 待翻内容 ({source}-{target}){text}",
                    replay="网络异常")
            res = json.loads(await resp.read())
            return res

    async def baidu_trans(self, source: str, target: str, text: str):
        msg = ""
        res = await self.baidu_trans_request(source, target, text)
        if "trans_result" in res:
            res = res["trans_result"]
        else:
            if "error_code" in res:
                errmsg = await self.baidu_errcode(res['error_code'])
                raise BaiduAiEngineError(
                    F"翻译异常 - 待翻内容 ({source}-{target}){text} => {res['error_code']}:{errmsg[0]} | {errmsg[1]}",
                    replay=f"翻译失败{res['error_code']}:{errmsg[0]}")
            else:
                raise BaiduAiEngineError(
                    F"翻译结果解析异常 - 待翻内容 ({source}-{target}){text} => {json.dumps(res)}",
                    replay="翻译结果解析异常")
        for item in res:
            msg += item["dst"] + "\n"
        return msg.strip()

    async def trans(self, source: str, target: str, content: str) -> str:
        if not self.enable:
            raise EngineError("引擎未启用", replay="引擎未启用")
        if not await self.bucket.wait_consume(1, 5):
            raise RatelimitException("速率限制！")
        source = self.conversion_lang(source)
        target = self.conversion_lang(target)
        try:
            return await self.baidu_trans(source, target, content)
        except EngineError as e:
            raise e
        except Exception as e:
            raise BaiduAiEngineError(f"网络连接异常：{e}", replay="网络连接异常")


"""
    支持列表

    自动检测	auto
    中文	zh
    英语	en
    粤语	yue
    繁体中文	cht
    文言文	wyw
    日语	jp
    韩语	kor
    法语	fra
    西班牙语	spa
    泰语	th
    阿拉伯语	ara
    俄语	ru
    葡萄牙语	pt
    德语	de
    意大利语	it
    希腊语	el
    荷兰语	nl
    波兰语	pl
    保加利亚语	bul
    爱沙尼亚语	est
    丹麦语	dan
    芬兰语	fin
    捷克语	cs
    罗马尼亚语	rom
    斯洛文尼亚语	slo
    瑞典语	swe
    匈牙利语	hu
    越南语	vie
"""
