# 04 SQLite 数据模型与迁移规格

## 1. 总则

- 主键建议 `INTEGER PRIMARY KEY`（SQLite）、对外 ID 为整数；用户资源归属均有 `user_id`，端点以登录会话鉴权，不相信客户端自行提交的 user_id。
- 时间戳使用 UTC ISO8601，日期使用 `YYYY-MM-DD`，浮点金额/重量等采用 `NUMERIC` 或以 Decimal 序列化，体重最多两位小数，避免二进制浮点累计误差。
- 启用 `PRAGMA foreign_keys=ON; journal_mode=WAL; busy_timeout=5000;`；连接每次开启外键，所有写事务短小，严禁多线程共享同一 Session。
- ORM 变更必须通过 Alembic 迁移；禁止生产启动时直接 `create_all` 覆盖迁移流程。
- 所有有所有权的记录执行 `WHERE user_id = current_user.id` 或通过归属关系约束；单靠前端隐藏字段不是授权。

## 2. 核心实体及字段

以下为最小必需字段，字段命名统一 snake_case；`created_at/updated_at` 除特别说明均需设置。

### `users`

| 字段 | 类型/约束 | 说明 |
|---|---|---|
| id | INTEGER PK | 用户编号 |
| username | VARCHAR(64) UNIQUE NOT NULL | 登录名（标准化小写比较） |
| display_name | VARCHAR(64) NOT NULL | 展示名 |
| password_hash | VARCHAR(255) NOT NULL | Argon2id，绝不明文 |
| role | TEXT CHECK `ADMIN/USER` | 角色 |
| status | TEXT CHECK `ACTIVE/DISABLED` | 状态 |
| session_version | INTEGER DEFAULT 1 | 密码重置/停用时递增，废止旧会话 |
| created_at, updated_at | DATETIME NOT NULL | 时间 |

### `sessions_auth`

| 字段 | 类型/约束 | 说明 |
|---|---|---|
| id | TEXT PK | 随机会话 ID 的不可逆摘要，不储存原 Cookie token |
| user_id | INTEGER FK users | 所属用户 |
| session_version | INTEGER | 登录时快照 |
| expires_at | DATETIME | 过期时间 |
| csrf_token_hash | TEXT | CSRF 验证用摘要 |
| created_at, last_seen_at | DATETIME | 时间 |

### `user_settings`

`user_id INTEGER PRIMARY KEY FK users`、`target_weight_kg NUMERIC(5,2) NULL CHECK 20..400`、`updated_at`。V1 体重单位默认 kg、时区统一 `APP_TIMEZONE`，可后续扩展个性化。

### `comparison_settings`

`user_id INTEGER PRIMARY KEY FK users`、`share_training_stats BOOLEAN NOT NULL DEFAULT 0`、`share_weight_change BOOLEAN NOT NULL DEFAULT 0`、`share_weight_values BOOLEAN NOT NULL DEFAULT 0`、`updated_at`。创建用户时同时初始化该行，全为 false。

### `exercises`

`id PK`、`owner_user_id NULL FK users`（空表示系统预置）、`name VARCHAR(100)`、`category TEXT CHECK STRENGTH/CARDIO/STRETCH`、`description TEXT NULL`、`is_active BOOLEAN DEFAULT 1`、`created_at/updated_at`。同一归属的 `(owner_user_id,name)` 不重复；系统预置允许按系统权限读取，普通用户不可修改其他用户动作。

### `fitness_plans`

`id PK`、`user_id FK`、`name VARCHAR(100)`、`status TEXT CHECK DRAFT/ACTIVE/INACTIVE`、`start_date DATE NOT NULL`、`end_date DATE NULL`、`current_revision_id INTEGER NULL`、`created_at/updated_at`。推荐增加 SQLite 部分唯一索引：`CREATE UNIQUE INDEX uq_active_weekly_plan_user ON fitness_plans(user_id) WHERE status='ACTIVE';`。激活时系统事务检查日期合法，替换旧 active 需显式停用。

### `plan_days`

`id PK`、`plan_id FK`、`weekday INTEGER NOT NULL CHECK 1..7`、`title VARCHAR(100)`、`is_rest BOOLEAN NOT NULL DEFAULT 0`、`created_at/updated_at`；`UNIQUE(plan_id,weekday)`。休息日 `is_rest=1` 不得挂有有效训练动作。

### `plan_exercises`

`id PK`、`plan_day_id FK`、`exercise_id FK`、`sort_order INTEGER`、`target_sets INTEGER NULL`、`target_reps INTEGER NULL`、`target_weight_kg NUMERIC(6,2) NULL`、`target_duration_min INTEGER NULL`、`target_distance_km NUMERIC(7,2) NULL`、`capacity TEXT/VARCHAR(64) NULL`（旧自由文本，兼容）、`sets_json TEXT NULL`（结构化组列表 JSON）、`note TEXT NULL`。`sets_json` 元素形如 `{set_index,reps,weight_kg,duration_min,distance_km}`；摘要 `target_*` 由组列表派生（`target_sets=len(sets)`，其余取第 1 组）。`UNIQUE(plan_day_id,sort_order)`。

### `plan_revisions`

`id PK`、`plan_id FK`、`user_id FK`、`effective_from DATE NOT NULL`、`effective_until DATE NULL`、`weekly_snapshot_json TEXT NOT NULL`、`created_at`。JSON 含该修订每周训练/休息日及动作目标；区间按 `[effective_from,effective_until]`；同一计划修订区间不可交叠。用于停机后补齐日期任务，不能仅依赖当前 plan_days。

### `date_overrides`

`id PK`、`user_id FK`、`workout_date DATE`、`mode TEXT CHECK REPLACE/ADD/REST`、`title VARCHAR(100) NULL`、`snapshot_json TEXT NULL`（REPLACE/ADD 必须含至少一项动作目标，REST 为空）、`updated_at/created_at`；`UNIQUE(user_id,workout_date)`。修改留存 `audit_logs`。覆盖未来任务之前先检查冲突，不可用过去的覆盖消除历史未完成任务。

### `schedule_occurrences`

| 字段 | 类型/约束 | 说明 |
|---|---|---|
| id | INTEGER PK | 任务发生实例 |
| user_id | INTEGER FK | 所属用户 |
| workout_date | DATE NOT NULL | 应执行日期 |
| slot | TEXT CHECK BASE/EXTRA | 日期内计划任务槽位 |
| source | TEXT CHECK WEEKLY/OVERRIDE | 来源 |
| revision_id | INTEGER NULL FK plan_revisions | 原计划修订 |
| title_snapshot | VARCHAR(100) NOT NULL | 训练主题快照 |
| exercise_snapshot_json | TEXT NOT NULL | **动作序列及目标快照** |
| status | TEXT CHECK PLANNED/CANCELLED | 是否仍应执行 |
| created_at, updated_at | DATETIME | 时间 |

唯一 `(user_id,workout_date,slot)`；允许以事务更新**未录入、非历史**的 PLANNED 实例（保留 audit），已经提交或过去的实例冻结；避免删除历史。`exercise_snapshot_json` 数组元素包含 `exercise_id/name/category/target_* /sort_order/note`。

### `workout_sessions`

| 字段 | 类型/约束 | 说明 |
|---|---|---|
| id | INTEGER PK | 训练记录 |
| user_id | INTEGER FK | 所属用户 |
| occurrence_id | INTEGER NULL FK schedule_occurrences | null 表示 AD_HOC |
| workout_date | DATE | 实际训练归属日期 |
| title_snapshot | VARCHAR(100) | 训练标题 |
| origin | TEXT CHECK PLAN/AD_HOC | 来源 |
| status | TEXT CHECK DRAFT/SUBMITTED | 草稿/提交 |
| version | INTEGER DEFAULT 1 | 乐观锁，修改即 +1 |
| submitted_at | DATETIME NULL | 提交时间 |
| deleted_at | DATETIME NULL | 软删除标记 |
| created_at, updated_at | DATETIME | 时间 |

`UNIQUE(occurrence_id)`（SQLite 允许多 NULL），确保计划任务只有一份有效历史；为支持软删后重新录入，建议**复用软删行恢复**而非重复创建同 occurrence_id。自主训练可以同日多条。

### `workout_exercises`

`id PK`、`session_id FK`、`exercise_id NULL FK`、`exercise_name_snapshot`、`category_snapshot`、`target_snapshot_json`、`sort_order`、`completed BOOLEAN NOT NULL DEFAULT 0`、`completed_at DATETIME NULL`、`created_at/updated_at`。即使原动作库软停用/改名也能读取快照。`UNIQUE(session_id,sort_order)`。

`target_snapshot_json` 含摘要目标与 `sets: [{set_index,reps,weight_kg,duration_min,distance_km,completed,completed_at}]`；`completed` 列与「全部组已完成」保持一致。会话 `completed_count/total_count` 按组统计。

### `weight_records`

`id PK`、`user_id FK`、`record_date DATE NOT NULL`、`recorded_at DATETIME NOT NULL`、`weight_kg NUMERIC(5,2) NOT NULL CHECK 20..400`、`note TEXT NULL`、`deleted_at DATETIME NULL`、`created_at/updated_at`。`INDEX(user_id,record_date,recorded_at)`；同日可多条。

### `audit_logs`

`id PK`、`actor_user_id FK`、`entity_type`、`entity_id`、`action`、`detail_json`（不得包含明文密码或会话 token） 、`created_at`。关键记录：历史 reopen/submit/delete、计划调整、共享设置、管理员用户管理、备份恢复。

### `system_kv`

`key TEXT PRIMARY KEY`、`value_json TEXT`、`updated_at`；存 `initialized=true`、schema 版本/备份调度元数据；不要存储明文密钥。

## 3. 关系约束

```text
users 1--1 user_settings / comparison_settings
users 1--N fitness_plans / date_overrides / schedule_occurrences / workout_sessions / weight_records
fitness_plans 1--N plan_days / plan_revisions
plan_days 1--N plan_exercises
schedule_occurrences 0..1--1 workout_sessions
workout_sessions 1--N workout_exercises
```

- 所有父子归属必须在业务层校验，例如 session 归属于 user A，绑定的 occurrence 也须属于 user A。
- `schedule_occurrences` 采用 BASE/EXTRA 槽位，对未来调整只更改未冻结实例；不存在的 EXTRA 不必创建 CANCELLED 空行。
- 迁移必须可在空库创建所有表、索引，并从已有旧版本升级；体重、历史 session 不得因迁移丢失。

## 4. 数据库创建与种子

- 第一次启动运行 Alembic upgrade head，预置基础动作库（可重复执行，幂等）。
- 首次管理员通过 `POST /api/setup/initialize` 在 **127.0.0.1** 访问时创建；无需默认固定密码，也不要硬编码演示用户。
- 生产数据保存在 `<APP_DATA_DIR>/fitness.db`；日志与备份分别存放，不允许浏览器直接下载整个数据库。

## 5. 备份一致性

SQLite WAL 模式不可简单复制使用中的 `.db` 文件；必须使用 SQLite 在线 backup API 生成一致性快照，必要时验证 `PRAGMA integrity_check`。恢复前停止写入、生成恢复前备份、验证备份有效并按运维流程替换，再重启连接；恢复操作写入系统审计日志。
