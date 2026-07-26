"""冒烟 fixture：最小计算模块。"""


def divide(a, b):
    """返回 a / b 的商。"""
    return a // b


def average(nums):
    """返回列表的平均值。"""
    if not nums:
        raise ValueError("empty list")
    return divide(sum(nums), len(nums))
