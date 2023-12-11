"""
    # 进行了部分改造的`bilibili_api`方法

    优化可能影响性能及不符合异步规范的部分。

    主要工作为将异步但使用同步`httpx`的方法修正为异步。

    以及，将不需要进行的文件处理移除。

    目前已处理的方法
    - `get_qrcode` 获取登录二维码，修改为完整异步请求
    - `check_qrcode_events` 检查是否已登录，修改为完整异步请求
    - `async_check_valid` cookie有效性检查
    - `Picture.__set_picture_meta_from_bytes` 将原本通过文件加载的方式改为直接加载`content`的`bytes`数据
    - `Picture.upload_file` 将非异步加载图片方法改为异步
"""
import os
import random
import tempfile
import uuid
import httpx
import qrcode
from yarl import URL
from typing import Any, List, Optional, Tuple, Union, Dict
from bilibili_api import Credential, Picture
from bilibili_api.login_func import API as LOGIN_API, QrCodeLoginEvents, LoginError
from bilibili_api.utils.Credential import API as CREDENTIAL_API
from bilibili_api.utils.network_httpx import request
from bilibili_api.live_area import get_area_list_sub as __get_area_list_sub
from bilibili_api.live import get_self_live_info
from .exception import BilibiliOprateFailure
from .logger import logger


def randUserAgent():
    UAs = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.117 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.77 Safari/537.36',
        'Mozilla/5.0 (X11; Ubuntu; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2919.83 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_8_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2866.71 Safari/537.36',
        'Mozilla/5.0 (X11; Ubuntu; Linux i686 on x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/53.0.2820.59 Safari/537.36',
    ]
    return UAs[random.randint(0, len(UAs) - 1)]

HEADERS = {"User-Agent": randUserAgent(), "Referer": "https://www.bilibili.com"}

LOGIN_API["qrcode"]["get_qrcode_and_token"] = {
    "url": "https://passport.bilibili.com/x/passport-login/web/qrcode/generate?source=main-fe-header",
    "method": "GET",
    "verify": False,
    "comment": "请求二维码及登录密钥"
}
LOGIN_API["qrcode"]["get_events"] = {
    "url": "https://passport.bilibili.com/x/passport-login/web/qrcode/poll",
    "method": "GET",
    "verify": False,
    "data": {
        "qrcode_key": "str: 登陆密钥",
        "source": "main-fe-header"
    },
    "comment": "获取最新信息"
}


async def make_qrcode(url) -> str:
    qr = qrcode.QRCode()
    qr.add_data(url)
    img = qr.make_image()
    img.save(os.path.join(tempfile.gettempdir(), "qrcode.png"))
    return os.path.join(tempfile.gettempdir(), "qrcode.png")


async def get_qrcode() -> Tuple[str, str]:
    """获取登录二维码 返回值 (二维码文件路径,验证密钥)"""
    api = LOGIN_API["qrcode"]["get_qrcode_and_token"]
    async with httpx.AsyncClient() as client:
        resp = await client.get(api["url"], follow_redirects=True, headers=HEADERS})
        logger.debug(f"获取登录二维码 响应 -> {resp.text}")
        resp_json = resp.json()
    qrcode_login_data = resp_json["data"]
    login_key: str = qrcode_login_data["qrcode_key"]
    qrcode = qrcode_login_data["url"]
    qrcode_image = await make_qrcode(qrcode)
    return (qrcode_image, login_key)

async def check_qrcode_events(
        login_key) -> Tuple[QrCodeLoginEvents, Union[str, "Credential"]]:
    """
    检查登录状态。（建议频率 1s，这个 API 也有风控！）

    Args:
        login_key (str): 登录密钥（get_qrcode 的返回值第二项)

    Returns:
        Tuple[QrCodeLoginEvents, str|Credential]: 状态(第一项）和信息（第二项）（如果成功登录信息为凭据类）
    """
    events_api = LOGIN_API["qrcode"]["get_events"]
    params = {"qrcode_key": login_key}
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            events_api["url"],
            params=params,
            cookies={
                "buvid3": str(uuid.uuid1()),
                "Domain": ".bilibili.com"
            },
            headers=HEADERS
        )
        logger.debug(f"检查登录状态 响应 -> {resp.text}")
        resp_json = resp.json()
    events: Dict[str, Any] = resp_json
    if "code" in events.keys() and events["code"] == -412:
        raise LoginError(events["message"])
    if events["data"]["code"] == 86101:
        return QrCodeLoginEvents.SCAN, events["message"]
    elif events["data"]["code"] == 86090:
        return QrCodeLoginEvents.CONF, events["message"]
    elif events["data"]["code"] == 86038:
        raise BilibiliOprateFailure("登录超时")
    elif events["data"]["code"] == 0:
        url: str = events["data"]["url"]
        cookies_list = url.split("?")[1].split("&")
        sessdata = ""
        bili_jct = ""
        dede = ""
        for cookie in cookies_list:
            if cookie[:8] == "SESSDATA":
                sessdata = cookie[9:]
            if cookie[:8] == "bili_jct":
                bili_jct = cookie[9:]
            if cookie[:11].upper() == "DEDEUSERID=":
                dede = cookie[11:]
        c = Credential(sessdata, bili_jct, dedeuserid=dede)
        return QrCodeLoginEvents.DONE, c
    else:
        raise BilibiliOprateFailure("响应异常")


def get_area_list_sub() -> List[Dict[str, Any]]:
    return __get_area_list_sub()  # type: ignore


async def async_load_url(url: str, imgtype: str = "") -> "Picture":
    """
    加载网络图片。(async 方法)

    Args:
        url (str): 图片链接

    Returns:
        Picture: 加载后的图片对象
    """
    if URL(url).scheme == "":
        url = "https:" + url
    obj = Picture()
    session = httpx.AsyncClient()
    resp = await session.get(
        url,
        headers={
            "User-Agent": "Mozilla/5.0"
        },
    )
    obj.content = resp.read()
    obj.url = url
    obj.__set_picture_meta_from_bytes(imgtype)
    return obj


class BilibiliOprateUtil:

    def __init__(self, credential: Credential) -> None:
        self.credential = credential

    async def live_update_title(self, room_id: int,
                                title: str) -> Optional[Dict[str, Any]]:
        """
            修改直播间标题

            [参考](https://github.com/SocialSisterYi/bilibili-API-collect/blob/master/docs/live/manage.md#更新直播间标题)

            结果字典
            - `code` `0`表示成功
            - `msg` 信息
        """
        api = {
            "method": "POST",
            "url": "https://api.live.bilibili.com/room/v1/Room/update",
        }
        data = {"room_id": room_id, "title": title}
        return await request(api["method"],
                             api["url"],
                             data=data,
                             credential=self.credential)

    async def async_check_valid(self):
        """
        检查 cookies 是否有效

        Returns:
            bool: cookies 是否有效
        """
        if not self.credential.has_sessdata():
            return False
        if not self.credential.has_bili_jct():
            return False
        api = CREDENTIAL_API["valid"]
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                api["url"],
                cookies=self.credential.get_cookies(),
            )
            logger.debug(f"校验登录状态 响应 -> {resp.text}")
            datas = resp.json()

        real_data = datas.get("data", {})
        return real_data.get("isLogin", False)

    async def get_self_live_info(self) -> Dict[str, Any]:
        return await get_self_live_info(self.credential)


# 加载模块补丁

from . import bilibili_patch
