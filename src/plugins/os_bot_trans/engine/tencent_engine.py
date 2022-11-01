import hashlib
import hmac
import json
import re
import time
import random
import aiohttp
from datetime import datetime
import base64

from . import Engine, EngineError
from pydantic import BaseSettings, Field
from nonebot import get_driver

try:
    # Wide UCS-4 build
    emoji_regex = re.compile(u'['
        u'\U0001F300-\U0001F64F'
        u'\U0001F680-\U0001F6FF'
        u'\u2600-\u2B55]+',
        re.UNICODE)
except re.error:
    # Narrow UCS-2 build
    emoji_regex = re.compile(u'('
        u'\ud83c[\udf00-\udfff]|'
        u'\ud83d[\udc00-\ude4f\ude80-\udeff]|'
        u'[\u2600-\u2B55])+',
        re.UNICODE)

def filter_emoji(desstr, restr='') -> str:
    # 过滤表情
    return emoji_regex.sub(restr, desstr)


class Config(BaseSettings):
    # Your Config Here
    trans_tencent_enable: bool = Field(default=False)
    trans_tencent_region: str = Field(default="ap-guangzhou")
    trans_tencent_id: str = Field(default="")
    trans_tencent_key: str = Field(default="")

    class Config:
        extra = "ignore"


global_config = get_driver().config
config = Config(**global_config.dict())


class TencentEngineError(EngineError):
    """
        腾讯引擎引起的错误
    """
    pass


class TencentEngine(Engine):
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
            change_dict={
                "zh-cn": "zh",
                "zh-tw": "zh-TW"
            },
            alias=["tc", "tencent"])
        self._region = config.trans_tencent_region
        self._secret_id = config.trans_tencent_id
        self._secret_key = config.trans_tencent_key
        if self.enable and (not self._secret_id or not self._secret_key):
            raise EngineError("请设置密钥后再启用此引擎！")

    @staticmethod
    def tencentApiSign_V3_PostHeaders(secret_id: str, secret_key: str,
                                      host: str, action: str, version: str,
                                      region: str, params: dict):
        service = host[:host.find(".")]
        algorithm = "TC3-HMAC-SHA256"
        timestamp = int(time.time())
        date = datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d")
        # ************* 步骤 1：拼接规范请求串 *************
        http_request_method = "POST"
        canonical_uri = "/"
        canonical_querystring = ""
        ct = "application/json; charset=utf-8"
        payload = json.dumps(params)
        canonical_headers = "content-type:%s\nhost:%s\n" % (ct, host)
        signed_headers = "content-type;host"
        hashed_request_payload = hashlib.sha256(
            payload.encode("utf-8")).hexdigest()
        canonical_request = (http_request_method + "\n" + canonical_uri +
                             "\n" + canonical_querystring + "\n" +
                             canonical_headers + "\n" + signed_headers + "\n" +
                             hashed_request_payload)

        # ************* 步骤 2：拼接待签名字符串 *************
        credential_scope = date + "/" + service + "/" + "tc3_request"
        hashed_canonical_request = hashlib.sha256(
            canonical_request.encode("utf-8")).hexdigest()
        string_to_sign = (algorithm + "\n" + str(timestamp) + "\n" +
                          credential_scope + "\n" + hashed_canonical_request)

        # ************* 步骤 3：计算签名 *************
        # 计算签名摘要函数
        def sign(key, msg):
            return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

        secret_date = sign(("TC3" + secret_key).encode("utf-8"), date)
        secret_service = sign(secret_date, service)
        secret_signing = sign(secret_service, "tc3_request")
        signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"),
                             hashlib.sha256).hexdigest()

        # ************* 步骤 4：拼接 Authorization *************
        authorization = (algorithm + " " + "Credential=" + secret_id + "/" +
                         credential_scope + ", " + "SignedHeaders=" +
                         signed_headers + ", " + "Signature=" + signature)

        return {
            "Host": host,
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": authorization,
            "X-TC-Action": action,
            "X-TC-Timestamp": str(timestamp),
            "X-TC-Version": version,
            "X-TC-Region": region
        }

    @staticmethod
    def tencentApiSign_V1_GetParams(secret_id: str, secret_key: str, host: str,
                                    action: str, version: str, region: str,
                                    params: dict):
        def get_string_to_sign(method, endpoint, params):
            s = method + endpoint + "/?"
            query_str = "&".join("%s=%s" % (k, params[k])
                                 for k in sorted(params))
            return s + query_str

        def sign_str(key, s, method):
            hmac_str = hmac.new(key.encode("utf8"), s.encode("utf8"),
                                method).digest()
            return base64.b64encode(hmac_str)

        data = {
            'Action': action,
            'Nonce': random.randrange(9999, 99999),
            'Region': region,
            'SecretId': secret_id,
            'Timestamp': int(time.time()),
            'Version': version
        }
        for key in params:
            data[key] = params[key]
        s = get_string_to_sign("GET", host, data)
        data["Signature"] = sign_str(secret_key, s, hashlib.sha1)
        return data

    async def tencent_TextTranslate(self,
                                    source: str,
                                    target: str,
                                    text: str,
                                    useV3: bool = False):
        args = {
            "secret_id": self._secret_id,
            "secret_key": self._secret_key,
            "host": "tmt.tencentcloudapi.com",
            "action": "TextTranslate",
            "version": "2018-03-21",
            "region": self._region,
            "params": {
                "ProjectId": 0,
                "Source": source,
                "Target": target,
                "SourceText": text,
            }
        }
        url = "https://" + args["host"]
        if useV3:
            v3headers = self.tencentApiSign_V3_PostHeaders(**args)
            req = aiohttp.request("post",
                                  url,
                                  headers=v3headers,
                                  data=json.dumps(args["params"]))

        else:
            v1params = self.tencentApiSign_V1_GetParams(**args)
            req = aiohttp.request("get", url, params=v1params)
        async with req as resp:
            code = resp.status
            if code != 200:
                raise TencentEngineError(
                    F"网络异常 - {code} 待翻内容 ({source}-{target}){text}",
                    replay=f"网络异常 {code}")
            res = json.loads(await resp.read())
            return res

    async def trans(self, source: str, target: str, content: str) -> str:
        if not self.enable:
            raise EngineError("引擎未启用", replay="引擎未启用")
        source = self.conversion_lang(source)
        target = self.conversion_lang(target)
        content = filter_emoji(content)  # 过滤emoji
        try:
            res = await self.tencent_TextTranslate(source,
                                                   target,
                                                   content,
                                                   useV3=True)
        except EngineError as e:
            raise e
        except Exception as e:
            raise TencentEngineError(
                F"网络连接异常 待翻内容 ({source}-{target}) {content} 错误 {e}",
                replay="网络状态异常！")
        if "Error" in res["Response"]:
            errmsg = res['Response']['Error']['Message']
            errcode = res['Response']['Error']['Code']
            raise TencentEngineError(
                F" 参数 ({source}-{target}) {content} | 错误代码 {errmsg}({errcode})",
                replay=f"API错误：{errmsg}({errcode})")
        return res["Response"]["TargetText"]


"""
    腾讯引擎
    支持的语言列表

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

    Target	是	String	目标语言，各源语言的目标语言支持列表如下

    zh（简体中文）：

    en（英语）、ja（日语）、ko（韩语）、fr（法语）、es（西班牙语）、it（意大利语）、de（德语）、tr（土耳其语）、ru（俄语）、pt（葡萄牙语）、vi（越南语）、id（印尼语）、th（泰语）、ms（马来语）
    zh-TW（繁体中文）：

    en（英语）、ja（日语）、ko（韩语）、fr（法语）、es（西班牙语）、it（意大利语）、de（德语）、tr（土耳其语）、ru（俄语）、pt（葡萄牙语）、vi（越南语）、id（印尼语）、th（泰语）、ms（马来语）
    en（英语）：

    zh（中文）、ja（日语）、ko（韩语）、fr（法语）、es（西班牙语）、it（意大利语）、de（德语）、tr（土耳其语）、ru（俄语）、pt（葡萄牙语）、vi（越南语）、id（印尼语）、th（泰语）、ms（马来语）、ar（阿拉伯语）、hi（印地语）
    ja（日语）：

    zh（中文）、en（英语）、ko（韩语）
    ko（韩语）：

    zh（中文）、en（英语）、ja（日语）
    fr（法语）：

    zh（中文）、en（英语）、es（西班牙语）、it（意大利语）、de（德语）、tr（土耳其语）、ru（俄语）、pt（葡萄牙语）
    es（西班牙语）：

    zh（中文）、en（英语）、fr（法语）、it（意大利语）、de（德语）、tr（土耳其语）、ru（俄语）、pt（葡萄牙语）
    it（意大利语）：

    zh（中文）、en（英语）、fr（法语）、es（西班牙语）、de（德语）、tr（土耳其语）、ru（俄语）、pt（葡萄牙语）
    de（德语）：

    zh（中文）、en（英语）、fr（法语）、es（西班牙语）、it（意大利语）、tr（土耳其语）、ru（俄语）、pt（葡萄牙语）
    tr（土耳其语）：

    zh（中文）、en（英语）、fr（法语）、es（西班牙语）、it（意大利语）、de（德语）、ru（俄语）、pt（葡萄牙语）
    ru（俄语）：

    zh（中文）、en（英语）、fr（法语）、es（西班牙语）、it（意大利语）、de（德语）、tr（土耳其语）、pt（葡萄牙语）
    pt（葡萄牙语）：

    zh（中文）、en（英语）、fr（法语）、es（西班牙语）、it（意大利语）、de（德语）、tr（土耳其语）、ru（俄语）
    vi（越南语）：

    zh（中文）、en（英语）
    id（印尼语）：

    zh（中文）、en（英语）
    th（泰语）：

    zh（中文）、en（英语）
    ms（马来语）：

    zh（中文）、en（英语）
    ar（阿拉伯语）：

    en（英语）
    hi（印地语）：

    en（英语）
"""
