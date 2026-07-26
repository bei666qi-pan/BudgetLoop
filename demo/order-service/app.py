"""BudgetLoop 演示 fixture：轻量订单服务（FastAPI + psycopg v3）。

真实的迷你业务服务：商品库存 + 下单扣减，跑在 PostgreSQL 之上，
供 BudgetLoop agent 在真实并发场景下定位并修复问题。
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

DATABASE_URL = os.environ.get("FIXTURE_DATABASE_URL", "postgresql://localhost:5432/fixture")

DDL = """
CREATE TABLE IF NOT EXISTS products (
    id    INTEGER PRIMARY KEY,
    name  TEXT NOT NULL,
    stock INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity   INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

SEED = """
INSERT INTO products (id, name, stock) VALUES (1, 'widget', 10)
ON CONFLICT (id) DO NOTHING
"""


def _connect() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(DDL)
        cur.execute(SEED)
        conn.commit()
    yield


app = FastAPI(title="order-service fixture", lifespan=lifespan)


class OrderRequest(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/products/{product_id}")
def get_product(product_id: int):
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, name, stock FROM products WHERE id = %s", (product_id,))
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="商品不存在")
    return {"id": row[0], "name": row[1], "stock": row[2]}


@app.post("/orders", status_code=200)
def create_order(req: OrderRequest):
    # 注意：sync def 端点由 FastAPI 线程池执行，多个请求真正并发进入这里。
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT stock FROM products WHERE id = %s", (req.product_id,))
        stock = cur.fetchone()
        if stock is None:
            raise HTTPException(status_code=404, detail="商品不存在")
        if stock[0] > 0:
            new_stock = stock[0] - req.quantity
            cur.execute(
                "UPDATE products SET stock = %s WHERE id = %s",
                (new_stock, req.product_id),
            )
            cur.execute(
                "INSERT INTO orders (product_id, quantity) VALUES (%s, %s) RETURNING id",
                (req.product_id, req.quantity),
            )
            order_id = cur.fetchone()[0]
            conn.commit()
            return {"order_id": order_id, "product_id": req.product_id, "quantity": req.quantity}
        conn.rollback()
        raise HTTPException(status_code=409, detail="库存不足")


@app.post("/admin/reset")
def reset():
    """测试辅助：恢复初始数据。"""
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM orders")
        cur.execute("UPDATE products SET stock = 10 WHERE id = 1")
        conn.commit()
    return {"status": "reset", "stock": 10}
