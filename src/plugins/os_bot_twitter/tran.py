import asyncio
import datetime
import os
import random
from time import localtime, strftime, time
from typing import Any, Dict, Optional
from playwright.async_api import async_playwright
from .logger import logger
from .config import config
from .exception import TransException, BaseException
from ..os_bot_base.util.async_wait_queue import AsyncWaitQueue


def randUserAgent():
    UAs = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.117 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.77 Safari/537.36',
        'Mozilla/5.0 (X11; Ubuntu; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2919.83 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_8_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2866.71 Safari/537.36',
        'Mozilla/5.0 (X11; Ubuntu; Linux i686 on x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/53.0.2820.59 Safari/537.36',
    ]
    return UAs[random.randint(0, len(UAs) - 1)]


class TwitterTrans:
    """
        烤推

        异步烤推
    """

    def __init__(self) -> None:
        """
            初始化

            会加载烤推脚本
        """
        self._enable = False
        self.script_filename = config.os_twitter_trans_script
        self.script_str = None
        self.debug = config.os_twitter_trans_debug
        self.screenshot_path = os.path.join(config.os_data_path,
                                            "twitter_trans", "screenshot")
        self.load_script()

    @property
    def enable(self):
        return self._enable

    async def async_startup(self):
        """
            烤推启动
        """
        # asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        proxy: Any = None
        if config.os_twitter_trans_proxy:
            proxy = {
                "server": config.os_twitter_trans_proxy,
            }
        self.playwright = await async_playwright().start()
        self.browser_type = self.playwright.chromium
        self.browser = await self.browser_type.launch(headless=not self.debug)
        self.context = await self.browser.new_context(
            accept_downloads=False,
            proxy=proxy,
            locale='zh-CN',
            timezone_id='Asia/Shanghai',
            viewport={
                'width': 1920,
                'height': 3200
            },
            # user_agent=randUserAgent(),
        )
        await self.context.set_extra_http_headers({
            "accept-language": "zh-CN,zh;q=0.9"
        })
        self._enable = True

    async def async_reload(self):
        """
            烤推重启

            关闭并等待3秒后重新启动
        """
        await self.context.close()
        await self.async_stop()
        self._enable = False
        await asyncio.sleep(3)
        await self.async_startup()

    async def async_stop(self):
        await self.playwright.stop()  # type: ignore
        self._enable = False

    async def trans(self,
                    tweet_id: str,
                    trans: Optional[Dict[str, Any]] = None,
                    trans_str: Optional[str] = None,
                    tweet_username: str = "normal") -> str:
        """
            烤推

            url： 合法的推文链接
            trans: 烤推字典

            返回值：截图文件名
        """
        if not self._enable:
            raise TransException("烤推引擎已关闭")
        if not self.script_str:
            raise TransException("烤推脚本未加载！")
        if trans is None and trans_str is None:
            raise BaseException("必须提供`trans`与`trans_str`的其中一个参数")
        try:
            screenshot_filename = f"{tweet_id}-{tweet_username}-{int(time()*1000)}-{random.randint(1000, 9999)}.jpg"
            screenshot_path = os.path.join(self.screenshot_path,
                                           screenshot_filename)
            while os.path.isfile(screenshot_path):
                screenshot_filename = f"{tweet_id}-{tweet_username}-{int(time()*1000)}-{random.randint(1000, 9999)}.jpg"
                screenshot_path = os.path.join(self.screenshot_path,
                                            screenshot_filename)
            logger.debug("烤推开始 {} 存档文件 {}", tweet_id, screenshot_filename)
            page = await self.context.new_page()
            await page.goto(
                f"https://twitter.com/{tweet_username}/status/{tweet_id}")

            async def print_args(msg):
                logstr = ""
                values = []
                for arg in msg.args:
                    result = await arg.json_value()
                    if isinstance(result, str):
                        logstr += " " + result
                    else:
                        logstr += " {}"
                        values.append(result)
                if logstr:
                    logger.debug(f"烤推脚本输出 - {logstr}", *values)

            page.on("console", print_args)

            playwright_config = {
                "ENABLE_PLAYWRIGHT": True,
                "WAIT_TIMEOUT": config.os_twitter_trans_timeout,
                "TRANS_DICT": trans,
                "TRANS_STR": trans_str,
                "USE_STR": True,
                "SCREENSHOTS": not trans and not trans_str
            }

            result = await page.evaluate(
                f'async (playwright_config) => {{return await (function(){{{self.script_str}}})()}}',
                playwright_config)

            if not result:
                raise TransException("烤推脚本未返回结果！")
            if not result[0]:
                raise TransException(f"失败了，{result[1]}",
                                     cause=Exception(result))
            logger.debug("烤推完成 {} 正在存档", tweet_id)
            await page.locator("#static_elem").screenshot(path=screenshot_path)
            await page.close()
            logger.debug("烤推存档完成 {} 存档文件 {}", tweet_id, screenshot_filename)
            return screenshot_filename
        except (BaseException, TransException) as e:
            raise e
        except Exception as e:
            raise TransException("未知原因异常，请联系管理员", cause=e)

    def load_script(self):
        """
            加载或重新加载脚本
        """
        try:
            with open(self.script_filename, encoding='utf-8') as file_obj:
                self.script_str = file_obj.read()
        except Exception as e:
            raise BaseException("读取脚本时异常！", cause=e)


class TwitterTransManage:
    """
        烤推管理器
    """

    def __init__(self) -> None:
        self.queue = AsyncWaitQueue(
            concurrent=config.os_twitter_trans_concurrent_limit,
            queue_size=config.os_twitter_trans_task_limit,
            name="烤推队列")
        self.twitter_trans = TwitterTrans()

    @property
    def screenshot_path(self):
        return self.twitter_trans.screenshot_path

    async def submit_trans(self,
                           tweet_id: str,
                           trans: Optional[Dict[str, Any]] = None,
                           trans_str: Optional[str] = None,
                           tweet_username: str = "normal"):
        """
            提交烤推任务

            返回值 可等待对象，需等待的队伍数量，预计等待时间
            异常 QueueFullException
        """
        if not self.twitter_trans._enable:
            raise TransException("烤推引擎离线，可能在重启哦")
        return self.queue.submit(
            self.twitter_trans.trans(tweet_id,
                                     trans=trans,
                                     trans_str=trans_str,
                                     tweet_username=tweet_username))

    async def startup(self):
        """启动"""
        await self.queue.startup()
        await self.twitter_trans.async_startup()

    async def restart(self):
        """重启"""
        await self.queue.restart()
        await self.twitter_trans.async_reload()

    async def reload_script(self):
        """重新加载脚本"""
        self.queue.statistics.clear()
        self.twitter_trans.load_script()

    async def clear_screenshot_file(self):
        """清理7天以上的烤推文件"""
        expire_days = 7
        current_time = strftime("%Y-%m-%d", localtime(time()))
        current_timeList = current_time.split("-")
        current_time_day = datetime.datetime(int(current_timeList[0]),
                                             int(current_timeList[1]),
                                             int(current_timeList[2]))
        path = self.screenshot_path

        for root, dirs, files in os.walk(path):
            for item in files:
                file_path = os.path.join(root, item)
                create_time = strftime(
                    "%Y-%m-%d", localtime((os.stat(file_path)).st_mtime))
                create_timeList = create_time.split("-")
                create_time_day = datetime.datetime(int(create_timeList[0]),
                                                    int(create_timeList[1]),
                                                    int(create_timeList[2]))
                time_difference = (current_time_day - create_time_day).days
                if time_difference > expire_days:
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        logger.error(
                            "移除超过{}天的烤推文件时异常 {} {} | {}", str(expire_days), e.__class__.__name__, str(e), file_path)
                        continue
                    logger.debug("移除超过{}天的烤推文件 {}", str(expire_days),
                                 file_path)

    async def stop(self):
        await self.twitter_trans.async_stop()
