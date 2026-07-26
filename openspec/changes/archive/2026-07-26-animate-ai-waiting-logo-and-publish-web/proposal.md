## Why

BudgetLoop 的网页 AI 等待态目前使用字母 B 与轨道粒子，和已确定的双环品牌标识不一致，也无法在普通浏览器中安全地接收用户的项目文件夹。为了让线上版本既有统一、可识别的等待反馈，又能按浏览器权限边界导入项目，需要同时完善共享动画、文件上传和独立生产部署能力。

## What Changes

- 将 AI 规划与任务创建等待态的共享活动标记改为纯 SVG/CSS 实现的双环 Logo 扰动动画，覆盖完整与紧凑尺寸，并保留可访问状态文本和减少动态效果支持。
- 为普通浏览器增加有界的项目文件夹上传：只接受用户显式选择的相对文件集合，服务端校验数量、单文件/总大小和路径后暂存，并在隔离工作区创建时导入；macOS App 继续使用原生文件夹授权，不改变直接访问语义。
- 让首页和配置确认区清楚区分“上传隔离副本”和“macOS App 直接修改项目”，展示上传进度、成功摘要和可恢复错误，不把浏览器上传误称为宿主文件夹授权。
- 增加适用于国内 Coolify 构建的生产部署配置，以 `web/` 作为独立网页构建目录，同时部署所需的服务端控制面与持久化依赖；上游 DeepSeek Key 仅以服务端环境变量注入。
- 在 GitHub 保留主仓库和 PR 迭代记录，经 Gitee 公开镜像供 Coolify 拉取，并绑定 `budgetloop.versecraft.cn` 后执行健康检查和线上冒烟验证。

## Capabilities

### New Capabilities

- `browser-project-upload`: 普通浏览器选择、上传、校验并将项目文件夹副本导入隔离工作区的行为与边界。
- `production-web-deployment`: 网页版独立构建、服务端密钥隔离、国内镜像部署、域名与健康验证的生产契约。

### Modified Capabilities

- `frontend-experience-system`: 共享 AI 等待态改用品牌双环扰动动画，并增加浏览器上传与原生直接访问的可信区分。
- `isolated-session-workspaces`: 隔离工作区可从经校验的浏览器上传快照初始化，但不能借此获得宿主路径访问权。

## Impact

- Affected code: `web/components/brand`, `web/components/home`, shared frontend types/API helpers and tests; backend upload API, request models, workspace provisioning/orchestration and tests; production Docker/Coolify configuration and deployment docs.
- API contract: additive authenticated upload endpoint plus optional opaque upload identifier on team creation; existing clients and the default isolated mode remain compatible.
- Budget: upload does not invoke a model and does not change token/call/cost accounting; storage and request sizes are explicitly bounded.
- Safety: provider Key remains server-side; uploaded paths are normalized, sensitive/escaping paths and symlinks are rejected, and uploads only seed isolated workspaces. Browser code never receives upstream or deployment credentials.
- Migration: additive, with no database schema change; staged uploads live under the configured artifact directory and can be removed independently. Existing macOS direct-folder and isolated task flows remain valid.
- Non-goals: no browser-side direct filesystem writes, no general-purpose file hosting, no change to sandbox semantics, no replacement of the AI gateway, and no redesign of the existing information architecture.
