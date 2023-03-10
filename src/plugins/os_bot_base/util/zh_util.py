def is_chinese(uchar):
    """判断一个unicode是否是汉字"""
    if uchar >= u'\u4e00' and uchar <= u'\u9fa5':
        return True
    else:
        return False


def is_alphabet(uchar):
    """判断一个unicode是否是半角英文字母"""
    if (uchar >= u'\u0041' and uchar <= u'\u005a') or (uchar >= u'\u0061'
                                                       and uchar <= u'\u007a'):
        return True
    else:
        return False


def is_Qalphabet(uchar):
    """判断一个unicode是否是全角英文字母"""
    if (uchar >= u'\uff21' and uchar <= u'\uff3a') or (uchar >= u'\uff41'
                                                       and uchar <= u'\uff5a'):
        return True
    else:
        return False


def is_number(uchar):
    """判断一个unicode是否是半角数字"""
    if uchar >= u'\u0030' and uchar <= u'\u0039':
        return True
    else:
        return False


def is_Qnumber(uchar):
    """判断一个unicode是否是全角数字"""
    if uchar >= u'\uff10' and uchar <= u'\uff19':
        return True
    else:
        return False


def Q2B(uchar):
    """单个字符 全角转半角"""
    inside_code = ord(uchar)
    if inside_code == 0x3000:
        inside_code = 0x0020
    else:
        inside_code -= 0xfee0
    if inside_code < 0x0020 or inside_code > 0x7e:  #转完之后不是半角字符返回原来的字符
        return uchar
    return chr(inside_code)


def B2Q(uchar):
    """单个字符 半角转全角"""
    inside_code = ord(uchar)
    if inside_code < 0x0020 or inside_code > 0x7e:  # 不是半角字符就返回原来的字符
        return uchar
    if inside_code == 0x0020:  # 除了空格其他的全角半角的公式为: 半角 = 全角 - 0xfee0
        inside_code = 0x3000
    else:
        inside_code += 0xfee0
    return chr(inside_code)


def stringB2Q(ustring: str):
    """把字符串半角转全角"""
    return "".join([B2Q(uchar) for uchar in ustring])


def stringQ2B(ustring: str):
    """把字符串全角转半角"""
    return "".join([Q2B(uchar) for uchar in ustring])


def stringpartQ2B(ustring: str):
    """把字符串中数字和字母全角转半角"""
    return "".join([
        Q2B(uchar) if is_Qnumber(uchar) or is_Qalphabet(uchar) else uchar
        for uchar in ustring
    ])


def strip_control_characters(s):
    """移除字符串中不可见控制字符"""
    word = ''
    for i in s:
        if ord(i)>31 or ord(i) == 10 or ord(i) ==13:
            word += i
    return word
