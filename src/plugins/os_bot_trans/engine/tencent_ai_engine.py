import hashlib
import hmac
import json
import time
import random
import aiohttp
from datetime import datetime
import base64

from . import Engine, EngineError
from pydantic import BaseSettings, Field
from nonebot import get_driver
from ..exception import RatelimitException
from ...os_bot_base.util import AsyncTokenBucket


class Config(BaseSettings):
    # Your Config Here
    trans_tencent_ai_enable: bool = Field(default=False)
    trans_tencent_ai_region: str = Field(default="ap-guangzhou")
    trans_tencent_ai_ratelimit: int = Field(default=5)
    trans_tencent_ai_id: str = Field(default="")
    trans_tencent_ai_key: str = Field(default="")

    class Config:
        extra = "ignore"


global_config = get_driver().config
config = Config(**global_config.dict())


class TencentAiEngineError(EngineError):
    """
        腾讯引擎引起的错误
    """
    pass


class TencentAiEngine(Engine):

    def __init__(self) -> None:

        alllangs = [
            'zh-cn', 'zh-tw', 'zh-yue', 'ja', "ko", "es", "fr", "th",
            "ar", "ru", "pt", "de", "it", "en"
        ]
        allowDict = {}
        for lang in alllangs:
            allowDict[lang] = alllangs
        allowDict["auto"] = alllangs
        change_dict = {
            "zh-cn": "zh",
            "zh-tw": "zh-TR",
            "zh-yue": "yue"
        }

        super().__init__(
            name="智能腾讯",
            enable=config.trans_tencent_ai_enable,
            allow_dict=allowDict,
            change_dict=change_dict,
            alias=["aitc", "aitencent", "ai腾讯", "AI腾讯"])
        self._region = config.trans_tencent_ai_region
        self._secret_id = config.trans_tencent_ai_id
        self._secret_key = config.trans_tencent_ai_key
        if self.enable and (not self._secret_id or not self._secret_key):
            raise EngineError("请设置密钥后再启用此引擎！")
        self.bucket = AsyncTokenBucket(
            config.trans_tencent_ai_ratelimit, 1, 0,
            int(config.trans_tencent_ai_ratelimit) or 1)

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
            "host": "hunyuan.tencentcloudapi.com",
            "action": "ChatTranslations",
            "version": "2023-09-01",
            "region": self._region,
            "params": {
                "Model": "hunyuan-translation",
                "Stream": False,
                "Text": text,
                "Source": source,
                "Target": target,
                # "Field": "游戏剧情",
                # "GlossaryIDs": [
                #     "3177dfae1f8cb180dfcc1bea2ddf19f6"
                # ],
                # "References": [
                #     {
                #         "Type": "sentence",
                #         "Text": "Computer games are a perfect recipe for strengthening our cognitive skills",
                #         "Translation": "电脑游戏是增强我们认知能力的完美秘诀"
                #     }
                # ]
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
                raise TencentAiEngineError(
                    F"网络异常 - {code} 待翻内容 ({source}-{target}){text}",
                    replay=f"网络异常 {code}")
            res = json.loads(await resp.read())
            return res

    async def trans(self, source: str, target: str, content: str) -> str:
        if not self.enable:
            raise EngineError("引擎未启用", replay="引擎未启用")
        if not await self.bucket.wait_consume(1, 5):
            raise RatelimitException("速率限制！")
        source = self.conversion_lang(source)
        target = self.conversion_lang(target)
        try:
            res = await self.tencent_TextTranslate(source,
                                                   target,
                                                   content,
                                                   useV3=True)
        except EngineError as e:
            raise e
        except Exception as e:
            raise TencentAiEngineError(
                F"网络连接异常 待翻内容 ({source}-{target}) {content} 错误 {e}",
                replay="网络状态异常！")
        if "Error" in res["Response"]:
            errmsg = res['Response']['Error']['Message']
            errcode = res['Response']['Error']['Code']
            raise TencentAiEngineError(
                F" 参数 ({source}-{target}) {content} | 错误代码 {errmsg}({errcode})",
                replay=f"API错误：{errmsg}({errcode})")
        try:
            choices = res["Response"]["Choices"]
            remsgs = []
            for choice in choices:
                remsgs.append(choice["Message"]["Content"])
            return "\n".join(remsgs)
        except Exception as e:
            raise TencentAiEngineError(
                F"响应异常 待翻内容 ({source}-{target}) {content} 响应 {res} 错误 {e}",
                replay="网络状态异常！")

"""
    腾讯引擎

    支持语言列表:
    简体中文：zh，繁体中文：zh-TR，粤语：yue，英语：en，法语：fr，葡萄牙语：pt，西班牙语：es，日语：ja，土耳其语：tr，俄语：ru，阿拉伯语：ar，韩语：ko，泰语：th，意大利语：it，德语：de，越南语：vi，马来语：ms，印尼语：id
    以下语种仅 hunyuan-translation 模型支持：
    菲律宾语：fil，印地语：hi，波兰语：pl，捷克语：cs，荷兰语：nl，高棉语：km，缅甸语：my，波斯语：fa，古吉拉特语：gu，乌尔都语：ur，泰卢固语：te，马拉地语：mr，希伯来语：he，孟加拉语：bn，泰米尔语：ta，乌克兰语：uk，藏语：bo，哈萨克语：kk，蒙古语：mn，维吾尔语：ug
    示例值：zh
"""
