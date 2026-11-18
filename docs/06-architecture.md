# 06 技术架构与 Windows 部署

## 1. 总体架构

```text
局域网 PC/手机浏览器
  └── HTTP http://<Windows-LAN-IP>:8080
        └── FastAPI (同源托管 frontend/dist 与 /api)
             ├── auth / users / plans / records / weight / stats / comparison
             ├── service 层（业务校验、权限、计划实例化、统计计算）
             ├── SQLAlchemy 2 + Alembic → SQLite (WAL)
             └── backup job → 本机 backups 目录
```

Vue 前端不直接操作 SQLite；统一调用 `/api`；FastAPI 提供 `/api` API 及 SPA history fallback。所有用户通过浏览器访问，服务端集中存储。V1 无云端和第三方身份依赖。

## 2. 开发规范与目录

- Frontend: Vue 3 SFC + TypeScript strict、Vite、Vue Router、Pinia、Element Plus、ECharts；API 层统一 fetch/axios 包装，Cookie `credentials: include`，Mutation 自动附 CSRF token，401 跳转登录，409 显示冲突提示。
- Backend: FastAPI 路由只做参数验证和响应；service 实现业务与授权；repository 负责数据库查询；Pydantic v2 请求/响应模型；SQLAlchemy 2.x Session request-scope；Alembic 管迁移。
- Testing: 后端 pytest/httpx+临时 SQLite（与生产相同开启 foreign_keys）、前端 Vitest、端到端 Playwright。
- 埋点/日志：结构化日志记录 request_id、错误码、耗时、user_id（可选），不打印凭据和敏感体重数值。
- 没有服务端数据库提交，不显示“已保存”；不能把仅存 Pinia 的模拟状态当作已持久化。

## 3. 安全与访问边界

- V1 默认为受信任的家庭/办公室局域网，不开放路由器公网端口；Windows 防火墙仅放通 TCP 8080 的 **Private（专用网络）配置文件**，尽可能限制源地址为局域网网段。
- 登录后会话 Cookie HttpOnly+SameSite=Lax，服务端保存会话 token 哈希、过期时间与 session_version；每次请求校验用户 ACTIVE，密码重置/停用时立即失效。
- POST/PATCH/PUT/DELETE 校验 CSRF token；Origin/Host 检查可信 LAN Host。建议配置 `ALLOWED_HOSTS=localhost,127.0.0.1,192.168.x.x`（填实际主机）；不能允许任意跨域来源。前端打包与 API 同源，默认不启用 CORS。
- HTTP 在本地可信 LAN 可用，但**并不提供传输加密**：不要用于不受信任 Wi-Fi；如跨不可信网络则应在反向代理启用 HTTPS。勿将密码写入启动脚本。
- 密码 Argon2id 哈希（或安全成熟实现），登录失败账户/IP 限流；用户名唯一；应用日志不得包含密码。
- API 数据隔离、体重共享判断必须服务端实现；拒绝未授权 URL 访问；数据库文件绝不可被 SPA 静态服务访问。
- 管理员必须通过本机 `127.0.0.1` 完成首次初始化；初始化成功后接口永久锁定（除显式重装并确认）。

## 4. Windows 环境与命令（脚本目标规范）

环境建议 Windows 10/11 x64，Python 3.12、Node.js LTS、Git。**交付必须提供 PowerShell 脚本**，命令假设仓库根目录：

```powershell
# 开发前端
cd frontend
npm ci
npm run dev

# 开发后端（另一个 PowerShell）
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

生产运行目标（由脚本实现，而不是在规范文件内声称已存在）：

```powershell
.\scripts\build.ps1    # npm ci + npm run build；安装/校验 Python 依赖与迁移
.\scripts\start.ps1    # 以配置端口启动同源服务；打印实际局域网 URL
.\scripts\backup.ps1   # 触发一致性备份
```

- 前端开发代理 `/api` → localhost:8000；部署时把前端 `dist` 放入后端静态目录，同源提供。
- Windows 本地默认 `APP_HOST=0.0.0.0`、`APP_PORT=8080`，仅当用户主动配置防火墙允许 LAN 访问。数据库目录不能放在前端 public/dist 下。
- `start.ps1` 检查端口占用、数据目录权限、数据库迁移状态、首次初始化提示、关键服务启动错误。需有 `stop.ps1` 或 Windows 服务停止指南，推荐采用 NSSM/任务计划程序配置开机自动启动（V1 允许选择手动启动）。
- `README` 中需记录运行方式、如何查找主机 IPv4、Windows 防火墙专用网络放行操作、服务在电脑休眠或关机后不可访问的提示。

## 5. `.env.example` 规范

```dotenv
APP_ENV=production
APP_HOST=0.0.0.0
APP_PORT=8080
APP_TIMEZONE=Asia/Shanghai
APP_DATA_DIR=./data
BACKUP_DIR=./backups
BACKUP_RETENTION_DAYS=30
SESSION_IDLE_HOURS=12
ALLOWED_HOSTS=localhost,127.0.0.1
LOG_LEVEL=INFO
```

部署时 `ALLOWED_HOSTS` 应包含电脑的局域网 IP，不能直接复制演示值上线。敏感配置不入 Git，`data/ backups/ *.db* .env` 等加入 `.gitignore`。

## 6. 备份与恢复

- 数据目录建议 `%LOCALAPPDATA%\FitManager\data`（当前运行账户），备份目录 `%LOCALAPPDATA%\FitManager\backups`；可配置修改；多 Windows 用户运行应固定同一个服务账户与同一份数据目录。
- 每日按 `APP_TIMEZONE` 设定本机 03:00 执行备份（PC 关机则开机后补执行一次）；保留最近 30 天，同时支持管理员手动备份。
- 使用 SQLite 在线 backup API 获取一致性快照；命名 `fitness-YYYYMMDD-HHMMSS.db`，附元数据 JSON（schema 版本、生成时间、SHA256、应用版本），生成后执行完整性检查。
- 恢复：仅 ADMIN → 二次确认 → 先做恢复前备份 → 验证所选备份 checksum、integrity_check 与 schema 兼容 → 进入维护模式拒绝新写入 → 关闭 DB 连接池并安全替换文件/重启服务 → 验证数据 → 记录审计。失败回滚到恢复前备份。
- 应演练备份后恢复体重记录、计划历史、用户授权状态与训练记录一致；备份可能包含全部用户敏感数据，备份目录需 Windows NTFS 权限保护，**不要提供给普通用户任意下载**。

## 7. 计划生成调度机制

- 每次启用/变更计划、覆盖指定日期时，在事务内实例化受影响日期的 occurrence；每天本地业务时区 00:05 执行滚动生成（预生成至未来 365 天）。
- 应用启动时运行补齐任务，包括服务停止期间遗漏的过去日期；按照 `plan_revisions` 对应有效区间恢复，而不是沿用当前模板覆盖旧历史。
- 为防启动多进程重复生成，应用同一机器只运行单实例；任务使用幂等 upsert 与 `(user_id,date,slot)` 唯一约束。推荐每日调度独立于 Web 请求，避免多 worker 重复调度。
- SQLite 采用一写者短事务 + WAL，目标 ≤20 账户/≤5 同时在线用户；后续可迁移 PostgreSQL，但 V1 不要提前引入双数据库复杂度。

## 8. 运行质量目标

建议开发验收目标（非外部性能承诺）：测试机器普通四核 CPU/8GB RAM、SSD、局域网下，预置 20 用户与每人 2 年记录，页面主要 GET API 的 P95 <500ms，训练动作 PATCH 的 P95 <800ms；多用户对比请求 P95 <1s；不应因 5 个并发客户端出现写入丢失。Windows 休眠、系统更新、关闭终端导致服务停止属于正常运维限制，应有清晰提示。
