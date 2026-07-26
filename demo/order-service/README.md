# order-service（BudgetLoop 演示 fixture）

一个刻意带有并发缺陷的迷你订单服务，作为 BudgetLoop 的正式演示场景：
agent 需要在**真实 PostgreSQL 并发环境**下定位问题、修复并验证。

## 背景

服务提供商品库存与下单接口，初始库存 10 件。压测（16 线程同时下单）时
会出现**超卖**：成功订单数超过库存，库存被扣成负数。

表面现象：并发测试偶发失败、库存为负、成功订单数 > 10。
真实根因：`POST /orders` 的扣减逻辑是 check-then-act——先 `SELECT stock`，
再在应用侧算出新值 `UPDATE stock = <算好的值>`。在 READ COMMITTED 下，
多个并发事务可以读到同一个旧值，各自通过后写回，互相覆盖。
这是应用层竞态，不是"测试 flaky"，也不是数据库故障。

## 如何运行

```bash
# 容器方式（随 compose 起，使用 fixture 库）
docker compose up -d order-service

# 本地方式（需要一个 PostgreSQL，建一个 fixture 库）
pip install -r requirements.txt
export FIXTURE_DATABASE_URL=postgresql://user:pass@localhost:5432/fixture
uvicorn app:app --port 8000
```

启动时自动建表 `products(id, name, stock)` / `orders(...)` 并插入
`id=1, stock=10` 的测试数据。

## 初始测试为何失败

```bash
cd demo/order-service
python -m unittest tests/test_concurrency.py -v
```

`test_concurrent_orders_never_oversell` 会失败：16 个并发下单中成功数
超过 10，最终库存为负，与"库存永不为负 / 最终一致"的断言冲突。
`test_naive_fix_regression` 标记为 expectedFailure：它复现
"在 check 与 act 之间加 `time.sleep` 随机延迟"的朴素修复——sleep 只会
拉大竞态窗口，并发下依旧超扣，且压测整体耗时会膨胀到超时。

## 演示要点

- 不要让 agent 被"重试就过了"的假象带偏：单跑一次压测可能碰巧通过，
  竞态问题需要并发压测才能稳定暴露。
- 正确修法是把"检查 + 扣减"合并成**一条原子 SQL**，让数据库行锁串行化：

  ```sql
  UPDATE products
  SET stock = stock - %(q)s
  WHERE id = %(id)s AND stock >= %(q)s
  RETURNING stock
  ```

  0 行返回即库存不足，返回 409。（`SELECT ... FOR UPDATE` 也能修，
  但多一次往返、锁持有更久，不是首选。）
- 修复验收标准：上面的并发测试全绿——成功数 ≤ 10、最终库存 == 10 - 成功数、
  库存不为负、失败请求均为 409 "库存不足"。

## 接口

- `GET /health`
- `GET /products/{id}`
- `POST /orders` `{product_id, quantity}` → 200 或 409/404
- `POST /admin/reset`（测试辅助：恢复 stock=10、清空 orders）
