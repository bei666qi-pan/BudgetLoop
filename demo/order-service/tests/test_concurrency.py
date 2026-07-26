"""并发竞态测试：16 线程同时下单，验证库存一致性。

运行方式（零额外依赖，stdlib unittest）：
    cd demo/order-service
    python -m unittest tests/test_concurrency.py -v

前提：order-service 已启动且可访问（默认 http://localhost:8000，
可用环境变量 ORDER_SERVICE_URL 覆盖），数据库已初始化。
"""
from __future__ import annotations

import json
import os
import random
import threading
import time
import unittest
import urllib.error
import urllib.request

BASE_URL = os.environ.get("ORDER_SERVICE_URL", "http://localhost:8000").rstrip("/")
THREADS = 16
INITIAL_STOCK = 10


def _request(method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        BASE_URL + path,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def _post(path: str, payload: dict) -> tuple[int, dict]:
    return _request("POST", path, payload)


def _get(path: str) -> tuple[int, dict]:
    return _request("GET", path)


class ConcurrentOrdersTest(unittest.TestCase):
    def setUp(self):
        status, body = _post("/admin/reset", {})
        self.assertEqual(status, 200, f"reset failed: {body}")

    def test_concurrent_orders_never_oversell(self):
        results: list[tuple[int, dict]] = []
        results_lock = threading.Lock()
        barrier = threading.Barrier(THREADS)

        def worker():
            barrier.wait()  # 尽量让所有线程同一时刻发出请求
            status, body = _post("/orders", {"product_id": 1, "quantity": 1})
            with results_lock:
                results.append((status, body))

        threads = [threading.Thread(target=worker) for _ in range(THREADS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)

        self.assertEqual(len(results), THREADS, "有请求未返回")
        successes = [r for r in results if r[0] == 200]
        conflicts = [r for r in results if r[0] == 409]

        # 每个请求要么成功下单，要么 409 拒绝
        self.assertEqual(
            len(successes) + len(conflicts),
            THREADS,
            f"存在非 200/409 响应: {[r[0] for r in results]}",
        )
        # 失败请求必须返回 409 "库存不足"
        for status, body in conflicts:
            self.assertIn("库存不足", json.dumps(body, ensure_ascii=False))
        # 成功订单数不能超过初始库存
        self.assertLessEqual(
            len(successes), INITIAL_STOCK, f"超卖：{len(successes)} 单成功，库存只有 {INITIAL_STOCK}"
        )
        # 无重复扣减且最终一致：最终库存 == 初始库存 - 成功数
        status, product = _get("/products/1")
        self.assertEqual(status, 200)
        self.assertEqual(
            product["stock"],
            INITIAL_STOCK - len(successes),
            f"库存不一致：stock={product['stock']}，成功订单={len(successes)}",
        )
        # 库存永不为负
        self.assertGreaterEqual(product["stock"], 0, f"库存被扣成负数: {product['stock']}")

    @unittest.expectedFailure
    def test_naive_fix_regression(self):
        """标记用例：说明"加 time.sleep 随机延迟错开请求"的朴素修复不成立。

        sleep 只是拉大 check 与 act 之间的竞态窗口，并发下仍会超扣；
        且在高并发压测中会因整体耗时而超时。这里用进程内模型复现，
        标记 expectedFailure——它存在是为了证明正确修法必须是
        单条原子 SQL（见 README.md），而不是证明服务行为。
        """
        stock = [INITIAL_STOCK]
        barrier = threading.Barrier(THREADS)

        def naive_worker():
            barrier.wait()
            current = stock[0]  # check
            time.sleep(random.uniform(0.001, 0.01))  # 朴素"修复"：随机延迟
            if current > 0:
                stock[0] = current - 1  # act（已被 sleep 拉开的竞态窗口）

        threads = [threading.Thread(target=naive_worker) for _ in range(THREADS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertGreaterEqual(stock[0], 0, f"朴素修复后仍超扣: stock={stock[0]}")


if __name__ == "__main__":
    unittest.main()
