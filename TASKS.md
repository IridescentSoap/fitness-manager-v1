# TASKS — AI Coding 分阶段任务

> 按 T0→T6 顺序执行。每次只完成一个阶段并提供：实现文件、迁移结果、测试命令及实际输出、未完成项。勿擅自扩展 V2 功能。业务语义以 docs/03 为准。

## T0. 工程初始化

- [x] 建立 `frontend/` Vue3+TS+Vite，安装 Router/Pinia/Element Plus/ECharts；建立运动主题 tokens 和统一主框架。
- [x] 建立 `backend/` FastAPI、SQLAlchemy2/Pydantic2/Alembic、依赖管理与分层结构。
- [x] 建立 `.env.example`、`.gitignore`、健康检查、开发脚本与基础 CI/测试命令。
- [x] 全部核心路由为空状态可访问（不使用硬编码统计假数据作为持久功能）。
- **验收：** 前后端本机开发启动成功、前端构建成功、pytest 初始套件通过。

## T1. 用户认证、权限与动作库

- [x] 创建 users/sessions_auth/user_settings/comparison_settings/exercises 迁移。
- [x] 首次仅 loopback 初始化管理员；登录/退出、session Cookie/CSRF、密码修改/重置、管理员创建/停用用户。
- [x] 用户 A/B 隔离；各登录状态变化与过期处理；预置动作库和自定义动作管理。
- [x] 页面：登录页、基本系统设置/用户管理与动作库。
- **验收：** T01/T02/T27，CSRF、登录限速、权限测试通过。

## T2. 周循环计划与日期覆盖

- [x] 实现 fitness_plans/plan_days/plan_exercises/plan_revisions/date_overrides/schedule_occurrences 迁移及模型。
- [x] 周计划 CRUD/复制/启用/停用，一用户唯一 ACTIVE；日期覆盖 REST/REPLACE/ADD。
- [x] 计划 occurrence 预生成与滚动补齐、历史冻结；补偿系统离线日期；冲突事务与 409 提示。
- [x] 页面：周计划列表/编辑抽屉、月历视图、日期覆盖编辑。
- **验收：** T03~T08/T14/T29；同一计划反复启用和改动不会重复生成任务。

## T3. 训练后记录与历史

- [x] 实现 workout_sessions/workout_exercises/audit_logs 迁移与业务。
- [x] 根据 occurrence 创建或获取草稿（幂等），逐动作勾选、版本冲突、手动提交、历史 reopen/重新提交、软删除、AD_HOC。
- [x] 页面：日期任务选择器、动作表格、保存状态反馈、提交二次确认、历史列表。
- **验收：** T09~T17/T19/T26；刷新与跨设备操作后保留实际保存结果。

## T4. 个人统计与体重

- [x] 实现 weight_records 迁移、体重 CRUD/目标体重/日末体重曲线。
- [x] 单一统计 service 实现 P_due、P_full、动作完成率、训练次数/天数、日历与汇总/趋势。
- [x] 数据概览、统计分析页面接真实 API；空值/null 处理及时间筛选。
- **验收：** T18/T20/T21 与固定统计样例 33.33% / 60% / 3次 / 2天。

## T5. 多用户排行榜、图表、共享

- [x] 共享设置三个独立开关、候选用户授权过滤、排行四指标、同周期用户比较。
- [x] 体重变化授权和原始体重授权分开校验；变更后立即撤销可见性。
- [x] 对比页面：排行榜、训练次数/完成率图、体重变化或原始趋势图；无综合分数。
- **验收：** T22~T25、越权和缓存测试通过。

## T6. Windows 本地部署与发布验收

- [x] `scripts/build.ps1/start.ps1/stop.ps1/backup.ps1/restore.ps1`、同源静态部署、SQLite WAL、开机补跑调度。
- [x] 管理员备份/恢复接口；每日自动备份与30天清理；恢复前备份与校验。
- [x] 1366px PC 主布局、375px 手机兼容、Loading/Error/Empty、无障碍重点检查。
- [x] Playwright E2E（`scripts/e2e.ps1`：T01/T02/T05/T10/T11/T20/T22/T23/T28 + T30 375px）与进程内 03:00/00:05 调度；验收清单见 `docs/08-windows-acceptance.md`。
- [ ] 第二台 LAN 真机与正式性能抽检（单机无法替代；清单第二节人工勾选）。
- **验收：** 本机 build + pytest + Playwright 可复跑；T28/T30 自动化覆盖；双机 LAN/性能仍需人工记录。

## 统一交付规范

1. 每阶段实现前先阅读 docs/03、04、05 对应部分；涉及规则修改必须先同步文档和测试。
2. 不允许把 mock/硬编码演示数值混入真实统计 API；前端开发 demo fixture 只限测试环境。
3. 数据库模型有改动必须添加 Alembic 迁移并测试升级；禁止重建库解决迁移错误。
4. 任何非本人数据读取要求清晰授权；默认私有；错误日志不输出体重明细/密码/Cookie。
5. commit 建议 `feat(auth):...`、`feat(plans):...`、`feat(records):...`、`feat(stats):...`、`feat(compare):...`。
6. 每阶段结束给出：`完成项 / API 变更 / 数据迁移 / 测试结果 / 风险与遗留`；未通过关键验收不得自动进入下一阶段。
