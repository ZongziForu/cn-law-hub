"""Chinese numeral <-> integer conversion."""

_CN_NUMERALS = {
    "零": 0, "一": 1, "二": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
    "十": 10, "百": 100, "千": 1000, "万": 10000,
}
_CN_NUMBERS: dict[int, str] = {}


def chinese_to_int(cn: str) -> int:
    if not cn:
        return 0
    if cn in _CN_NUMBERS:
        return _CN_NUMBERS[cn]
    total = 0
    partial = 0
    for ch in cn:
        val = _CN_NUMERALS.get(ch, 0)
        if val >= 10:
            if partial == 0:
                partial = 1
            total += partial * val
            partial = 0
        else:
            partial = partial * 10 + val if partial else val
    total += partial
    return total


def int_to_chinese(n: int) -> str:
    if n <= 0:
        return ""
    if n in _CN_NUMBERS:
        return _CN_NUMBERS[n]
    if n < 10:
        return ["", "一", "二", "三", "四", "五", "六", "七", "八", "九"][n]
    if n < 20:
        return "十" + ("" if n == 10 else int_to_chinese(n - 10))
    if n < 100:
        tens, ones = divmod(n, 10)
        return int_to_chinese(tens) + "十" + ("" if ones == 0 else int_to_chinese(ones))
    if n < 1000:
        hunds, rest = divmod(n, 100)
        prefix = int_to_chinese(hunds) + "百"
        if rest == 0:
            return prefix
        if rest < 10:
            return prefix + "零" + int_to_chinese(rest)
        if rest < 20:
            return prefix + "一" + int_to_chinese(rest)
        return prefix + int_to_chinese(rest)
    if n < 10000:
        thous, rest = divmod(n, 1000)
        prefix = int_to_chinese(thous) + "千"
        if rest == 0:
            return prefix
        if rest < 100:
            return prefix + "零" + int_to_chinese(rest)
        return prefix + int_to_chinese(rest)
    return str(n)


# Build lookup table for 1-199
for _i in range(1, 200):
    _CN_NUMBERS[_i] = int_to_chinese(_i)
