"""calc 模块测试（stdlib unittest，初始应失败）。

运行：
    cd demo/smoke-fixture
    python -m unittest test_calc.py -v
"""
import unittest

from calc import average, divide


class CalcTest(unittest.TestCase):
    def test_divide_returns_exact_quotient(self):
        self.assertAlmostEqual(divide(7, 2), 3.5)
        self.assertAlmostEqual(divide(1, 3), 1 / 3)

    def test_average(self):
        self.assertAlmostEqual(average([1, 2, 2]), 5 / 3)
        self.assertAlmostEqual(average([10, 20]), 15.0)


if __name__ == "__main__":
    unittest.main()
