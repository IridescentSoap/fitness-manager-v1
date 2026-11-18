# FitManager V1.0 — AI Coding 开发文档

> 状态：需求基线 V1.0 / 2026-11-16。使用场景：**Windows 本地电脑运行服务、局域网内 PC 优先访问、手机兼容、训练结束后集中记录和统计**。视觉风格：现代运动健身主题。本文档集合是实现契约，而非仅供参考的功能清单。

## 1. 产品边界

- 独立多用户账号与管理员；普通用户仅可管理本人的计划、打卡和体重。
- 每人最多一套**有效周循环计划**，并支持指定日期的「替换、追加、休息」调整。
- 训练完成后选择日期、逐动作勾选；勾选自动保存**草稿**，点击**提交记录**方计入正式统计。支持补录与受控修改。
- 个人训练统计、体重记录/目标/趋势、多用户训练排行榜及图表对比；共享权限默认全部关闭，分别授权训练汇总、体重变化、体重原始值。
- Windows 本地部署，访问方式 `http://<LAN_IP>:8080`。数据本地持久化、备份恢复。

**明确不做：**训练时计时器、组间休息提醒、动作视频、运动处方、自动 AI 训练建议、微信登录、云同步、公开互联网访问、逐组实际重量记录、好友/群组聊天、积分/综合评分。

## 2. 技术基线

| 层 | 选型 |
|---|---|
| 前端 | Vue 3 + TypeScript + Vite + Vue Router + Pinia + Element Plus + ECharts |
| 后端 | Python 3.12 + FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic |
| 数据库 | SQLite（WAL，外键开启，busy_timeout） |
| 身份认证 | 安全会话 Cookie（HttpOnly、SameSite=Lax）+ 服务端会话过期与 CSRF 防护 |
| 部署 | Windows 10/11 本地进程/服务，前端打包由 FastAPI 同源托管；支持后续 Docker，但 V1 不要求 |
| 测试 | pytest + httpx，Vitest，Playwright（关键路径） |

## 3. 文档索引与阅读顺序

1. [`docs/01-requirements.md`](docs/01-requirements.md) — 功能范围、用户故事及验收目标
2. [`docs/03-business-rules.md`](docs/03-business-rules.md) — **唯一业务规则权威来源**，包括统计公式与冲突处理
3. [`docs/04-database.md`](docs/04-database.md) — 数据表、关系、约束和迁移
4. [`docs/05-api.md`](docs/05-api.md) — 接口契约与错误处理
5. [`docs/02-ui-design.md`](docs/02-ui-design.md) — 六个页面、UI 主题、交互状态、响应式约束
6. [`docs/06-architecture.md`](docs/06-architecture.md) — 安全、Windows 部署、备份、开发运行
7. [`docs/07-test-cases.md`](docs/07-test-cases.md) — 测试案例、验收矩阵
8. [`docs/08-windows-acceptance.md`](docs/08-windows-acceptance.md) — Windows 实机 / E2E / LAN 验收清单
9. [`TASKS.md`](TASKS.md) — 迭代任务、依赖和 Definition of Done

若文档冲突：业务语义以 `03-business-rules.md` 为准；数据库字段以 `04-database.md` 为准；接口格式以 `05-api.md` 为准；在实现前将冲突记录在任务日志并同步修正，不静默猜测。

## 4. 推荐仓库结构（由 Coding Agent 创建）

```text
fitness-manager/
  README.md  TASKS.md  docs/
  frontend/  # Vue3 + Vite + TS
    src/{api,assets,components,layouts,pages,router,stores,styles,types,utils}/
  backend/
    app/{api,core,models,schemas,services,repositories,tests}/
    alembic/  pyproject.toml
  scripts/{dev.ps1,build.ps1,start.ps1,stop.ps1,backup.ps1,restore.ps1,e2e.ps1}/
  e2e/         # Playwright 关键路径
  data/        # .gitignore，不提交用户数据
  backups/     # .gitignore
  .env.example
```

## 5. 执行提示（可直接复制给 AI Coding 工具）

> 请完整阅读 README、docs/01~07 和 TASKS.md。严格按 TASKS.md 顺序实现，每阶段只实现对应能力，执行该阶段测试并报告通过/失败项。以 docs/03-business-rules.md 为业务真值，不擅自更改统计口径、共享权限、日期覆盖规则。禁止任何用户数据默认共享；所有跨用户查询均须在后端授权。实现完整 API 校验、迁移、单元/集成测试和 Windows 启停脚本。先完成可运行的最小闭环，再迭代页面美化；不得用硬编码演示数据替代真实 API。发现规范冲突应列出具体位置、采用保守默认并更新文档与测试。

## 6. 本机运行

开发时开两个终端：

```powershell
.\scripts\dev.ps1 backend
.\scripts\dev.ps1 frontend
```

前端开发地址是 `http://127.0.0.1:5173`，接口代理到 `8000`。首次管理员只能在这台电脑打开 `http://127.0.0.1:8000` 初始化。

局域网同源运行：

```powershell
.\scripts\build.ps1
.\scripts\start.ps1
.\scripts\stop.ps1
.\scripts\backup.ps1
.\scripts\restore.ps1 -BackupId fitness-YYYYMMDD-HHMMSS.db -Confirm RESTORE
.\scripts\e2e.ps1
```

`start.ps1` 会把服务绑到 `0.0.0.0:8080`，并自动把本机局域网 IPv4 写入进程内 `ALLOWED_HOSTS`。首次放行防火墙请用**管理员** PowerShell 执行 `.\scripts\open-lan-firewall.ps1`（专用网络 TCP 8080 / 5173）。其他设备请打开脚本打印的 `LAN: http://<本机IP>:8080`（填**服务主机**的 IP，不是手机/另一台电脑自己的 IP）。电脑休眠、关机或关掉进程后，局域网访问会中断；下次启动会按计划修订补齐停机期间的任务，并在生产模式下补做当天备份。发布验收见 [`docs/08-windows-acceptance.md`](docs/08-windows-acceptance.md)。

查找本机 IPv4：`ipconfig`，看正在使用的无线或以太网适配器。开发模式 Vite 监听 `0.0.0.0:5173`，局域网可打开 `http://<本机IP>:5173`（仍由本机代理到 `8000`）。不要把数据库目录放到 `frontend/dist`。

Linux（systemd 开机自启 + SSH 隧道）：见 [`deploy/linux/README.md`](deploy/linux/README.md)。简要步骤：

```bash
# 构建前端与 Python 依赖后
sudo bash scripts/linux/install-systemd.sh /opt/fitness-manager-v1
# 本机：ssh -N -L 18080:127.0.0.1:18080 user@server
# 浏览器：http://127.0.0.1:18080
```

## 7. 完成定义

- Windows 新机器按 `06-architecture.md` 从零部署可成功；局域网同网段浏览器可访问。
- 管理员首次初始化、两个普通用户数据隔离；真实数据库支持计划、日期调整、训练记录和体重。
- 六页面可实际操作，不依赖模拟数据；统计和对比指标通过相同后端统计服务计算。
- 关键测试全部通过，尤其历史数据不随计划改变、共享权限撤销立即生效、备份恢复完整。
