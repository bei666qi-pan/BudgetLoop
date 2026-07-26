# BudgetLoop 网页版（Coolify）

生产资源使用仓库根目录的 `docker-compose.production.yml`。GitHub `main` 是源仓库，Gitee `master` 是 Coolify 在国内服务器上的拉取源；Coolify 只把 `web:3000` 绑定到公网域名，控制面凭证和上游模型 Key 不进入浏览器包。

必填的 Coolify 服务端变量：

- `POSTGRES_PASSWORD`：随机数据库密码
- `API_TOKEN`：随机控制面令牌，同时只注入 web 服务端 BFF 与后端
- `AI_GATEWAY_API_KEY`：DeepSeek Key，仅注入 control-plane/worker

推荐显式变量：

- `AI_GATEWAY_BASE_URL=https://api.deepseek.com`
- `AI_GATEWAY_RECOMMENDATION_MODEL=deepseek-v4-flash`
- `AI_GATEWAY_DEFAULT_MODEL=deepseek-v4-flash`

域名：`https://budgetloop.versecraft.cn` → `web:3000`。发布完成的判据是 Compose 服务全部健康、首页可访问、`/api/control/api/health` 返回 `{"status":"ok"}`，并且一次 `/api/task-drafts` 冒烟调用返回 AI 或明确的可恢复错误。任何真实值只保存在 Coolify，不写入本目录。
