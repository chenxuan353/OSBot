from ..os_bot_base.exception import MatcherErrorFinsh


class BilibiliCookieVaildFailure(MatcherErrorFinsh):
    """
        B站cookie校验失败
    """


class BilibiliOprateFailure(MatcherErrorFinsh):
    """
        B站API调用失败
    """
