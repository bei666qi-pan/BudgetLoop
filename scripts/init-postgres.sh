#!/bin/bash
# 创建四个逻辑库：budgetloop（业务）、newapi（默认网关）、litellm（兼容网关）、fixture（演示订单服务）
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE budgetloop;
    CREATE DATABASE newapi;
    CREATE DATABASE litellm;
    CREATE DATABASE fixture;
EOSQL
