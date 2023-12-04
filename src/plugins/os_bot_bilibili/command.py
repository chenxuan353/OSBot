import asyncio
import base64
import random
from time import time
from typing import Any, Dict, List
from nonebot import on_command, on_message
from nonebot.matcher import Matcher
from nonebot.params import CommandArg, EventMessage
from nonebot.permission import SUPERUSER
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN, GROUP_OWNER, PRIVATE_FRIEND
from nonebot.adapters.onebot import v11
from bilibili_api import Credential, Picture, ResponseCodeException
from bilibili_api.dynamic import BuildDynmaic, send_dynamic, Dynamic
from bilibili_api.live import LiveRoom
from .exception import BilibiliOprateFailure
from .config import BilibiliSession
from .logger import logger
from .bilibili import BilibiliOprateUtil, get_qrcode, check_qrcode_events, QrCodeLoginEvents, get_area_list_sub, async_load_url

from ..os_bot_base.depends import SessionDepend
from ..os_bot_base import matcher_exception_try, Adapter, AdapterDepend
from ..os_bot_base import only_command
from ..os_bot_base.permission import PermManage, perm_check_permission
from ..os_bot_base.util import RateLimitDepend, RateLimitUtil, inhibiting_exception

PermManage.register("B级人员",
                    "操作B站相关功能",
                    auth=False,
                    for_group_member=True,
                    only_super_oprate=False)

bilibili_login = on_command("B站登录",
                            aliases={"B站登入","B站登陆",  "b站登入", "b站登录", "b站登陆", "登录B站", "登入B站", "登陆B站", "登录b站", "登入b站", "登陆b站"},
                            block=True,
                            rule=only_command(),
                            permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER
                            | PRIVATE_FRIEND | perm_check_permission("B级人员"))


@bilibili_login.handle(parameterless=[
    RateLimitDepend(RateLimitUtil.PER_M(1)),
    RateLimitDepend(RateLimitUtil.PER_M(4, minutes=3),
                    prompts=["使用次数过多，指令正在冷却中……", "负载过高，请稍后再试！"],
                    scope=RateLimitUtil.SCOPE_HANDLE),
    RateLimitDepend(RateLimitUtil.PER_15M(15),
                    prompts=["使用次数过多，指令正在冷却中……", "负载过高，请稍后再试！"],
                    scope=RateLimitUtil.SCOPE_HANDLE)
])
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: v11.Bot,
            mevent: v11.MessageEvent,
            adapter: Adapter = AdapterDepend(),
            session: BilibiliSession = SessionDepend(BilibiliSession)):
    credential = await session.get_credential()
    if credential:
        await matcher.finish("已经登录，若存在问题请使用`B站登出`指令后再试！")

    @inhibiting_exception()
    async def login_wait():
        async with session:
            start_time = time()
            qrcode_image, login_key = await get_qrcode()

            with open(qrcode_image, mode="rb") as f:
                filedata = f.read()
            b64 = str(base64.b64encode(filedata), "utf-8")
            filedata = None
            qrcode_tips = ["请在3分钟内扫描，并确认~", "呐，要在三分钟之内确认哦！", "三分钟内扫码确认哦~"]
            qrcode_tip = qrcode_tips[random.randint(0, len(qrcode_tips) - 1)]
            await bot.send(
                mevent,
                v11.MessageSegment.text(qrcode_tip) +
                v11.MessageSegment.image(f"base64://{b64}"))
            try:
                while True:
                    await asyncio.sleep(5)
                    if session.sessdata:
                        logger.debug("登录等待已失效……")
                        await bot.send(mevent,"登录等待失效，请联系管理员！")
                        return

                    event, data = await check_qrcode_events(login_key)
                    if event == QrCodeLoginEvents.DONE:
                        credential: Credential = data  # type: ignore
                        break
                    logger.debug("B站登录检查：{} {}", event, data)
                    if time() - start_time > 165:
                        finish_msgs = ('登录超时！', '二维码失效了……', '没有确认登录哦！')
                        await bot.send(
                            mevent,
                            finish_msgs[random.randint(0,
                                                       len(finish_msgs) - 1)])
                        return
            except ResponseCodeException as e:
                raise BilibiliOprateFailure(e.msg, cause=e)
            except Exception:
                logger.opt(exception=True).warning("登录失败")
                finish_msgs = ('登录失败', '登录异常')
                await bot.send(
                    mevent, finish_msgs[random.randint(0,
                                                       len(finish_msgs) - 1)])
                return
            try:
                credential.raise_for_no_bili_jct()
                credential.raise_for_no_sessdata()
            except Exception:
                finish_msgs = ('登录失败', '未能成功登录')
                await bot.send(
                    mevent, finish_msgs[random.randint(0,
                                                       len(finish_msgs) - 1)])
                return
            await asyncio.sleep(0.15)
            session.sessdata = credential.sessdata
            session.bili_jct = credential.bili_jct
            user_info = await session.get_self_info()
            user_name = user_info['name']
            logger.info("B站用户 {} 登录成功", user_name)
            finish_msgs = ('登录成功~', '成功啦！', f'欢迎您{user_name}！')
            await bot.send(
                mevent, finish_msgs[random.randint(0,
                                                   len(finish_msgs) - 1)])

    asyncio.gather(login_wait())


bilibili_logout = on_command(
    "B站登出",
    aliases={"B站注销", "退出B站登录", "登出B站", "清除B站cookie", "b站登出", "登出b站", "退出b站登录"},
    block=True,
    rule=only_command(),
    permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER
    | PRIVATE_FRIEND | perm_check_permission("B级人员"))


@bilibili_logout.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.MessageEvent,
            adapter: Adapter = AdapterDepend(),
            session: BilibiliSession = SessionDepend(BilibiliSession)):
    if not session.sessdata and not session.bili_jct:
        await matcher.finish("还没有登录过哦")

    async with session:
        await session.logout()

    await matcher.finish("成功退出啦！")


async def credential_check(matcher: Matcher,
                           session: BilibiliSession) -> Credential:
    credential = await session.get_credential()
    if not credential:
        finish_msgs = ('登录已失效或未登录！', '失败>_<，登录可能已失效', '似乎登录状态失效了……？')
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    return credential


bilibili_dynamic_start = on_command(
    "开始动态发送",
    aliases={"开始发送动态", "写草稿"},
    block=True,
    rule=only_command(),
    permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER
    | PRIVATE_FRIEND | perm_check_permission("B级人员"))


@bilibili_dynamic_start.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.MessageEvent,
            adapter: Adapter = AdapterDepend(),
            session: BilibiliSession = SessionDepend(BilibiliSession)):
    await credential_check(matcher, session)

    mark = await adapter.mark(bot, event)
    if session._tmp_time and time() - session._tmp_time < 600:
        await matcher.send("已清空过往草稿")
    session._tmp_mask = mark
    session._tmp_msg = ""
    session._tmp_imgs = []
    session._tmp_time = time()
    session._tmp_wait_confirm = False
    finish_msgs = ('好，开始吧！请以发送动态结束哦~', '好诶，草稿本准备好了，以发送动态结束哦~',
                   '草稿开启~通过发送动态结束！')
    await matcher.finish(finish_msgs[random.randint(0, len(finish_msgs) - 1)])


bilibili_dynamic_send_spy = on_message(priority=5, block=False, rule=None)


@bilibili_dynamic_send_spy.handle()
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.MessageEvent,
            msg: v11.Message = EventMessage(),
            adapter: Adapter = AdapterDepend(),
            session: BilibiliSession = SessionDepend(BilibiliSession)):
    if not session._tmp_time:
        return
    interval = time() - session._tmp_time
    if interval > 600:
        session._tmp_mask = None
        session._tmp_msg = None
        session._tmp_imgs = None
        session._tmp_time = 0
        session._tmp_wait_confirm = False
        if interval < 3600:
            finish_msgs = ('草稿已超时清空。', '超时啦，草稿已清空。')
            await matcher.finish(finish_msgs[random.randint(
                0,
                len(finish_msgs) - 1)])
    mark = await adapter.mark(bot, event)
    if session._tmp_mask != mark:
        return

    matcher.stop_propagation()

    assert session._tmp_msg is not None
    assert session._tmp_imgs is not None

    # 功能实现
    msg_text = str(msg).strip()
    if msg_text == "清空草稿":
        session._tmp_msg = ""
        session._tmp_imgs = []
        session._tmp_time = time()
        session._tmp_wait_confirm = False
        finish_msgs = ('好，让我们重新开始~', '刷刷，清空咯！', '换了新的草稿纸~')
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])

    if msg_text == "删除草稿":
        session._tmp_mask = None
        session._tmp_msg = None
        session._tmp_imgs = None
        session._tmp_time = 0
        session._tmp_wait_confirm = False
        finish_msgs = ('清空完成', '揉，丢进垃圾桶。', '好~已经完成啦')
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])

    if msg_text == "续写草稿":
        if not session._tmp_wait_confirm:
            await matcher.finish("请先确认发送哦！")
        session._tmp_wait_confirm = False

    if msg_text == "发送动态":
        if session._tmp_wait_confirm:
            await matcher.finish("请先确认上次的发送哦！")
        session._tmp_wait_confirm = True

        if len(session._tmp_imgs) > 9:
            session._tmp_imgs = session._tmp_imgs[:9]
            await matcher.send("图片超过9张的部分已截断")

        dynamic_msg = v11.Message()
        dynamic_msg += v11.MessageSegment.text(session._tmp_msg)
        wait_send_msg = []

        wait_send_msg.append({
            "type": "node",
            "data": {
                "name":
                "动态~",
                "uin":
                str(bot.self_id),
                "content":
                v11.Message() +
                v11.MessageSegment.text("以下为待发布内容，请回复`确认发送`或`续写草稿`继续")
            }
        })

        wait_send_msg.append({
            "type": "node",
            "data": {
                "name": "动态~",
                "uin": str(bot.self_id),
                "content": dynamic_msg
            }
        })

        if session._tmp_imgs:
            dynamic_imgs = v11.Message()
            for img_url in session._tmp_imgs:
                dynamic_imgs += v11.MessageSegment.image(img_url)
            wait_send_msg.append({
                "type": "node",
                "data": {
                    "name": "动态~",
                    "uin": str(bot.self_id),
                    "content": dynamic_imgs
                }
            })

        if await adapter.msg_is_multi_group(bot, event):
            await bot.call_api(
                "send_group_forward_msg", **{
                    "group_id": await
                    adapter.get_group_id_from_event(bot, event),
                    "messages": wait_send_msg
                })
        else:
            await bot.call_api(
                "send_private_forward_msg", **{
                    "user_id": await
                    adapter.get_unit_id_from_event(bot, event),
                    "messages": wait_send_msg
                })
        await matcher.finish()

    if msg_text == "确认发送":
        if not session._tmp_wait_confirm:
            await matcher.finish("请先发送动态哦！")

        credential = await session.get_credential()
        if not credential:
            session._tmp_mask = None
            session._tmp_msg = None
            session._tmp_imgs = None
            session._tmp_time = 0
            session._tmp_wait_confirm = False
            finish_msgs = ('登录已失效或未登录！', '失败>_<，登录可能已失效', '似乎登录状态失效了……？')
            await matcher.finish(finish_msgs[random.randint(
                0,
                len(finish_msgs) - 1)])

        try:
            dyn = BuildDynmaic.empty()
            dyn.add_text(session._tmp_msg)
            for img_url in session._tmp_imgs:
                dyn.add_image(await async_load_url(img_url))
                await asyncio.sleep(0.2)

            result = await send_dynamic(dyn, credential)
        except ResponseCodeException as e:
            raise BilibiliOprateFailure(e.msg, cause=e)
        # dyn_id = result["dyn_id"]
        logger.info("动态发布成功：{}", result)
        # dynamic = Dynamic(dynamic_id=dyn_id, credential=credential)
        # await asyncio.sleep(1.5)
        # dynamic_info = await dynamic.get_info()
        # logger.info("动态信息：{}", dynamic_info)

        session._tmp_mask = None
        session._tmp_msg = None
        session._tmp_imgs = None
        session._tmp_time = 0
        session._tmp_wait_confirm = False
        await matcher.finish("发送成功~")

    if session._tmp_wait_confirm:
        return

    for msgseg in msg:
        if msgseg.is_text():
            session._tmp_msg += msgseg.data.get("text", "")
        elif msgseg.type == "image":
            url = msgseg.data.get("url", "")
            session._tmp_imgs.append(url)


_area_list: List[Dict[str, Any]] = get_area_list_sub()
collect_area: Dict[str, str] = {}
for area in _area_list:
    sub_list = area["list"]
    for sub_area in sub_list:
        if sub_area["name"] in collect_area:
            logger.warning("分区重名：{}-{} | {}", area["name"], sub_area["name"],
                           sub_area["id"])
            continue
        collect_area[sub_area["name"]] = sub_area["id"]

bilibili_live_start = on_command(
    "开启直播间",
    aliases={
        "开始直播", "开始B站直播", "开启B站直播间", "开始b站直播", "开启b站直播间", "开播", "开启直播", "开启直播间", "打开直播间"
    },
    block=True,
    permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER
    | PRIVATE_FRIEND | perm_check_permission("B级人员"))


@bilibili_live_start.handle(parameterless=[
    RateLimitDepend(RateLimitUtil.PER_M(2)),
    RateLimitDepend(RateLimitUtil.PER_15M(15),
                    prompts=["使用次数过多，指令正在冷却中……", "负载过高，请稍后再试！"],
                    scope=RateLimitUtil.SCOPE_HANDLE)
])
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.MessageEvent,
            adapter: Adapter = AdapterDepend(),
            msg: v11.Message = CommandArg(),
            session: BilibiliSession = SessionDepend(BilibiliSession)):
    credential = await credential_check(matcher, session)

    user_info = await session.get_self_info()
    user_name = user_info['name']
    live_info = await session.get_self_live_info()
    if not live_info['room_id']:
        await matcher.finish("当前账号未开通直播间")

    text = msg.extract_plain_text()
    if text == "虚拟主播":
        await matcher.finish("当前分区需要人脸识别，无法开播。")
    if text not in collect_area:
        finish_msgs = ('要填写正确的分区！', '分区错误，可以参考直播页的分区列表哦！', '分区不存在X')
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    try:
        area_id = collect_area[text]
        liveRoom = LiveRoom(room_display_id=live_info['room_id'],
                            credential=credential)
        result = await liveRoom.start(int(area_id))
        logger.info("成功开播 {} - {} 分区", user_name, text)
        logger.debug("成功开播 {} - {}", user_name, result)
        # 'change': 1, 'status': 'LIVE'
        session.live_rtmp_addr = result['rtmp']['addr']
        session.live_rtmp_code = result['rtmp']['code']
        await session.save()
        finish_msgs = ("开启成功，需要连接信息请使用`推流链接`指令~", "开启成功啦！",
                       "成功~使用`推流链接`指令查看连接信息哦~")
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    except ResponseCodeException as e:
        logger.warning("{}", e)
        finish_msgs = (f"直播间开启失败 {e.msg}", f"失败了，{e.msg}", f"失败惹……{e.msg}")
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])


bilibili_live_stop = on_command(
    "关闭直播间",
    aliases={"关闭直播", "关闭B站直播", "关闭B站直播间", "关闭b站直播", "关闭b站直播间", "下播", "停止直播"},
    block=True,
    rule=only_command(),
    permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER
    | PRIVATE_FRIEND | perm_check_permission("B级人员"))


@bilibili_live_stop.handle(parameterless=[
    RateLimitDepend(RateLimitUtil.PER_M(2)),
    RateLimitDepend(RateLimitUtil.PER_15M(15),
                    prompts=["使用次数过多，指令正在冷却中……", "负载过高，请稍后再试！"],
                    scope=RateLimitUtil.SCOPE_HANDLE)
])
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.MessageEvent,
            adapter: Adapter = AdapterDepend(),
            session: BilibiliSession = SessionDepend(BilibiliSession)):
    credential = await credential_check(matcher, session)

    live_info = await session.get_self_live_info()
    if not live_info['room_id']:
        await matcher.finish("当前账号未开通直播间")

    user_info = await session.get_self_info()
    user_name = user_info['name']

    if not session.live_rtmp_code or not session.live_rtmp_code:
        finish_msgs = ('还没有开播哦', '开播后再试试吧', '需要先开播！')
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])

    try:
        liveRoom = LiveRoom(room_display_id=live_info['room_id'],
                            credential=credential)
        result = await liveRoom.stop()
        logger.info("成功下播 {}", user_name)
        logger.debug("成功下播 {} - {}", user_name, result)
        finish_msgs = ("好耶，收工啦", "已下播~", "关闭成功啦~")
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    except ResponseCodeException as e:
        logger.warning("{}", e)
        finish_msgs = (f"直播间关闭失败 {e.msg}", f"失败了，{e.msg}", f"失败惹……{e.msg}")
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])


bilibili_live_rtmp = on_command(
    "推流链接",
    aliases={"展示rtmp", "显示推流方式", "推流方式"},
    block=True,
    rule=only_command(),
    permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER
    | PRIVATE_FRIEND | perm_check_permission("B级人员"))


@bilibili_live_rtmp.handle(parameterless=[
    RateLimitDepend(RateLimitUtil.PER_M(1)),
    RateLimitDepend(RateLimitUtil.PER_15M(15),
                    prompts=["使用次数过多，指令正在冷却中……", "负载过高，请稍后再试！"],
                    scope=RateLimitUtil.SCOPE_HANDLE)
])
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.MessageEvent,
            adapter: Adapter = AdapterDepend(),
            session: BilibiliSession = SessionDepend(BilibiliSession)):
    await credential_check(matcher, session)

    if not session.live_rtmp_addr or not session.live_rtmp_code:
        finish_msgs = ('还没有开播哦', '开播后再试试吧', '需要先开播！')
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])

    result = await bot.send(
        event, "rtmp推流方式(30秒后撤回)\n"
        f"地址：\n{session.live_rtmp_addr}\n"
        f"推流码：\n{session.live_rtmp_code}")

    if "message_id" not in result:
        return

    await asyncio.sleep(30)

    await bot.delete_msg(message_id=result["message_id"])


bilibili_login_user = on_command(
    "B站登录用户",
    aliases={"查看B站登录用户", "查看b站登录用户", "b站登录用户","B站登陆用户","查看B站登陆用户", "查看b站登陆用户", "b站登陆用户"},
    block=True,
    rule=only_command(),
    permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER
    | PRIVATE_FRIEND | perm_check_permission("B级人员"))


@bilibili_login_user.handle(parameterless=[
    RateLimitDepend(RateLimitUtil.PER_M(1)),
    RateLimitDepend(RateLimitUtil.PER_15M(15),
                    prompts=["使用次数过多，指令正在冷却中……", "负载过高，请稍后再试！"],
                    scope=RateLimitUtil.SCOPE_HANDLE)
])
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.MessageEvent,
            adapter: Adapter = AdapterDepend(),
            session: BilibiliSession = SessionDepend(BilibiliSession)):
    await credential_check(matcher, session)

    user_info = await session.get_self_info()

    result = await matcher.finish(f"当前登录用户：{user_info['name']}")


bilibili_live_rename = on_command(
    "修改直播间标题",
    aliases={"修改直播标题", "设置直播标题", "设置直播间标题", "更新直播间标题", "更新直播标题"},
    block=True,
    permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER
    | PRIVATE_FRIEND | perm_check_permission("B级人员"))


@bilibili_live_rename.handle(parameterless=[
    RateLimitDepend(RateLimitUtil.PER_M(2)),
    RateLimitDepend(RateLimitUtil.PER_15M(15),
                    prompts=["使用次数过多，指令正在冷却中……", "负载过高，请稍后再试！"],
                    scope=RateLimitUtil.SCOPE_HANDLE)
])
@matcher_exception_try()
async def _(matcher: Matcher,
            bot: v11.Bot,
            event: v11.MessageEvent,
            adapter: Adapter = AdapterDepend(),
            msg: v11.Message = CommandArg(),
            session: BilibiliSession = SessionDepend(BilibiliSession)):
    credential = await credential_check(matcher, session)

    user_info = await session.get_self_info()
    user_name = user_info['name']
    live_info = await session.get_self_live_info()
    if not live_info['room_id']:
        await matcher.finish("当前账号未开通直播间")

    title = msg.extract_plain_text()

    try:
        bo = BilibiliOprateUtil(credential)
        result = await bo.live_update_title(live_info['room_id'], title)
        logger.info("修改直播间标题 {} -> {}", user_name, title)
        logger.debug("修改直播间标题 {} - {}", user_name, result)
        finish_msgs = ("好耶，成功啦", "改好啦！", "w好的，已经成功了")
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])
    except ResponseCodeException as e:
        logger.warning("{}", e)
        finish_msgs = (f"直播间关闭失败 {e.msg}", f"失败了，{e.msg}", f"失败惹……{e.msg}")
        await matcher.finish(finish_msgs[random.randint(
            0,
            len(finish_msgs) - 1)])


bilibili_help_msg = f"""
无特殊说明的指令需要ATbot或者感叹号起始(如 !在吗)
登录相关：B站登录、B站登出
发动态："写草稿"指令之后会进入写草稿状态，动态仅支持图片与文字。
进入写草稿状态后支持删除草稿、清空草稿、续写草稿以及发送动态等操作(无需前缀)。
直播间："开播 分区"、"下播"、"更新直播标题 新标题"
若需要授权其他人操作可使用`授权 B级人员 @群成员`进行（仅允许管理员操作）
""".strip()

bilibili_help = on_command("B站功能帮助",
                           aliases={"B站帮助", "b站帮助", "b站功能帮助"},
                           block=True)


@bilibili_help.handle(parameterless=[RateLimitDepend(RateLimitUtil.PER_M(1))])
@matcher_exception_try()
async def _(matcher: Matcher):
    await matcher.finish(bilibili_help_msg)
