# smoke-fixture（BudgetLoop 冒烟 fixture）

最小的纯 stdlib Python 项目，用于端到端冒烟：验证 BudgetLoop 全链路
（建任务 → workspace → agent 定位 → 修复 → 跑测试 → 报告）能在
几秒钟内跑通，不依赖 Docker 网络、数据库等重型基础设施。

## Bug

`calc.divide` 把除法写成了整数除法（`//`），调用方期望精确的浮点商。
`average` 基于 `divide`，均值同样被截断。

## 运行测试

```bash
cd demo/smoke-fixture
python -m unittest test_calc.py -v
```

初始状态两个用例失败（`7/2` 得 3 而非 3.5，`average([1,2,2])` 得 1 而非 1.667）。
修复后全绿即冒烟通过。
