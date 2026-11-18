# 05 REST API 契约（v1）

## 1. 通用规范

- 基址 `/api`；JSON，UTF-8；请求认证 Cookie（`fm_session`）为 HttpOnly、SameSite=Lax，生产使用局域网 HTTP 时 Secure=false（仅可信内网），如启用 HTTPS 需 Secure=true。
- 任何修改请求 `POST/PATCH/PUT/DELETE` 必须附 `X-CSRF-Token`，由登录/会话信息接口颁发并与服务端会话绑定；**不使用未保护的跨站 Cookie 写入**。
- 客户端不发送 `user_id` 作为数据权限来源，服务端从会话身份得出。管理员路径须显式鉴权。
- 分页统一 `?page=1&page_size=20`（最大 100），返回 `items,total,page,page_size`；日期范围 `from=YYYY-MM-DD&to=YYYY-MM-DD`。默认本月；最大 366 天。
- 成功响应结构：`{"data": ...}`；错误：`{"error":{"code":"...","message":"...","details":{}}}`。列表也在 data 内；新增成功 201；删除成功 204；校验 422；未登录 401；禁止 403；资源不可见 404；版本/状态冲突 409。
- 日期无时区，时间戳含 `Z`；金额/体重使用 JSON number，在服务端 Decimal 严格验证两位小数。
- 所有含用户、训练、体重和比较数据响应加 `Cache-Control: no-store`。

## 2. 认证与管理员

| 方法 | 路径 | 权限 | 请求要点 / 响应 |
|---|---|---|---|
| GET | `/api/setup/status` | 公共 | 仅返回是否完成初始化，不泄露账号信息 |
| POST | `/api/setup/initialize` | 仅本机首次 | `{username,display_name,password}`；创建首位 ADMIN；只能从 127.0.0.1/::1；已初始化则409 |
| POST | `/api/auth/login` | 公共 | `{username,password}`；设置 Cookie，返回 user 和 csrf_token |
| GET | `/api/auth/me` | 登录 | 当前用户、role、display_name、csrf_token |
| POST | `/api/auth/logout` | 登录 | 注销当前会话，204 |
| PATCH | `/api/auth/password` | 登录 | `{old_password,new_password}`；更新后其他会话失效 |
| GET/POST | `/api/admin/users` | ADMIN | 查询或创建普通用户 |
| PATCH | `/api/admin/users/{id}` | ADMIN | 修改 display_name / status；停用即使会话失效 |
| POST | `/api/admin/users/{id}/reset-password` | ADMIN | `{new_password}`；回收旧会话 |

密码策略：非空即可（长度 1~128），无复杂度/弱口令限制；登录失败限速；不在日志打印密码或登录 Cookie。

## 3. 动作库与计划

| 方法 | 路径 | 权限 | 用途 |
|---|---|---|---|
| GET/POST | `/api/exercises` | 登录 | 系统动作+个人动作查询；新增个人动作 |
| PATCH/DELETE | `/api/exercises/{id}` | 归属人 | 修改/软停用自定义动作 |
| GET/POST | `/api/plans` | 登录 | 列表/创建周期计划 |
| GET/PATCH | `/api/plans/{id}` | 归属人 | 详情/更新计划，含 days 与动作 |
| POST | `/api/plans/{id}/activate` | 归属人 | 启用计划，若已有 active 返回 409，需先停用 |
| POST | `/api/plans/{id}/deactivate` | 归属人 | 停用计划；不改历史 |
| POST | `/api/plans/{id}/duplicate` | 归属人 | 复制为 DRAFT |
| GET | `/api/schedule?from=&to=` | 登录 | 日期安排（包含计划任务、状态、来源） |
| PUT | `/api/schedule/overrides/{date}` | 登录 | 设置 REPLACE/ADD/REST |
| DELETE | `/api/schedule/overrides/{date}` | 登录 | 撤销该日期调整，受历史冻结规则约束 |

创建/修改计划示例：

```json
{
  "name":"五日分化训练", "start_date":"2026-11-16", "end_date":null,
  "days":[
    {"weekday":1,"title":"胸部训练","is_rest":false,"exercises":[
      {"exercise_id":1,"sort_order":1,"sets":[
        {"reps":10,"weight_kg":60},
        {"reps":8,"weight_kg":65}
      ],"note":""}
    ]},
    {"weekday":3,"title":"休息","is_rest":true,"exercises":[]}
  ]
}
```

也可继续传摘要 `target_sets/target_reps/...`，服务端会展开为等量组。日期覆盖请求示例（替换）：

```json
{"mode":"REPLACE","title":"游泳训练","exercises":[
  {"exercise_id":20,"sort_order":1,"sets":[{"duration_min":40}]}
]}
```

`ADD` 同结构，`REST` 必须没有 exercises；由后端在事务内刷新 `schedule_occurrences`，冲突统一返回 `409 TASK_HAS_RECORD`。`/api/schedule` 每条计划任务返回 `occurrence_id, workout_date, slot, source, title, status, actions_count, record_status, completion_result`；无安排日期由前端日历空状态显示。

## 4. 训练记录

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/records?from=&to=&page=` | 本人历史记录与草稿，分页 |
| POST | `/api/records/drafts` | 为 occurrence 创建或获取草稿（`{occurrence_id}`），或 `AD_HOC`（`{workout_date,title,exercises}`）；同 occurrence 幂等 |
| GET | `/api/records/{id}` | 记录详情、动作快照、`version` |
| POST | `/api/records/{id}/exercises` | 草稿中追加动作（`{expected_version,exercises}`，每项可含 `sets`） |
| PATCH | `/api/records/{id}/actions/{action_id}` | 更新动作完成、组列表或单组字段，自动保存草稿 |
| POST | `/api/records/{id}/submit` | 手动提交草稿；版本校验 |
| POST | `/api/records/{id}/reopen` | 已提交记录转回草稿，审计；版本校验 |
| DELETE | `/api/records/{id}` | 本人软删除，二次确认在前端；删除请求需审计 |

动作 PATCH 请求（动作一键全选 / 单组 / 全量 sets 任选）：

```json
{"completed":true,"expected_version":3}
```

```json
{"set_index":2,"reps":8,"weight_kg":65,"set_completed":true,"expected_version":3}
```

```json
{"sets":[{"reps":10,"weight_kg":60},{"reps":8,"weight_kg":65}],"expected_version":3}
```

响应含最新 `record`（`completed_count/total_count` 按组；每条动作含 `target.sets`）。

提交请求：`{"expected_version":4}`；返回 `status=SUBMITTED, completion_result=PARTIAL|FULL|NONE, completed_count, total_count, submitted_at, version`（计数按组）。同版本重复提交可识别相同请求并返回已提交结果。`reopen` 仅本人，并在 UI 中需确认。

自主训练草稿示例：

```json
{"workout_date":"2026-11-15","title":"自由综合","exercises":[
  {"exercise_id":1,"sort_order":1,"sets":[{"reps":8,"weight_kg":60},{"reps":8,"weight_kg":60}]},
  {"exercise_id":20,"sort_order":2,"sets":[{"duration_min":20}]}
]}
```

未传 `sets` 时默认 1 组空值；计划任务写入时按类别校验组字段。

## 5. 体重与个人统计

| 方法 | 路径 | 用途 |
|---|---|---|
| GET/POST | `/api/weights` | 本人的体重列表/新增，支持日期过滤 |
| PATCH/DELETE | `/api/weights/{id}` | 本人修改/软删除体重 |
| GET | `/api/statistics/overview?from=&to=` | 本人指标：`completed_sessions,training_days,planned_due,planned_full,plan_completion_rate,action_completion_rate,latest_weight` |
| GET | `/api/statistics/training?from=&to=&group_by=week` | 时间序列与动作频次、热力日历 |
| GET | `/api/statistics/weight?from=&to=` | 本人日体重观测、最新、阶段变化、目标体重 |
| PATCH | `/api/settings/profile` | display_name / target_weight_kg |

新增体重请求：`{"record_date":"2026-11-15","recorded_at":"2026-11-15T23:30:00+08:00","weight_kg":72.5,"note":"晨起"}`；服务端校验 date 与 recorded_at 在业务时区的日历日期一致。返回持久化 ID。

统计中的无定义比率返回 `null`，不是 `0`。统计响应附 `from,to,timezone` 便于前后端核对。

## 6. 多用户比较与授权

| 方法 | 路径 | 权限 | 用途 |
|---|---|---|---|
| GET/PATCH | `/api/settings/sharing` | 本人 | 读取/设置三个共享开关 |
| GET | `/api/comparison/users?scope=training|weight_change|weight_values` | 登录 | 当前指标下已授权的候选用户（含本人） |
| GET | `/api/comparison/rankings?metric=&from=&to=` | 登录 | 授权用户排行；`metric=sessions|days|plan_rate|action_rate` |
| GET | `/api/comparison/metrics?user_ids=2,3&metric=&from=&to=` | 登录 | 2~5 个用户，训练指标或体重变化；权限逐用户逐指标校验 |
| GET | `/api/comparison/weight-trends?user_ids=2,3&from=&to=` | 登录 | 原始体重授权用户的日趋势 |

`GET/PATCH /api/settings/sharing` 示例：

```json
{"share_training_stats":true,"share_weight_change":false,"share_weight_values":false}
```

权限策略：候选列表只返回符合 scope 的账号；请求未授权 ID **不返回任何其敏感字段**，整个请求返回 403 `SHARING_NOT_ALLOWED`（不做半截混合成功）；排行榜内部过滤授权用户。所有比较响应 `no-store`。

## 7. 系统运维

| 方法 | 路径 | 权限 | 用途 |
|---|---|---|---|
| GET | `/api/admin/health` | ADMIN | 数据库健康、应用版本、最近备份时间，不泄露秘密 |
| POST | `/api/admin/backups` | ADMIN | 创建在线一致性备份 |
| GET | `/api/admin/backups` | ADMIN | 列出备份元数据 |
| POST | `/api/admin/backups/{backup_id}/restore` | ADMIN | 恢复（提供确认短语），触发安全恢复流程 |

安全要求：备份文件不应暴露为静态 URL；恢复必须原子、安全地关闭写入并重新连接数据库。实现为 Windows 安全的维护子进程/重启脚本更稳妥，不要在仍持有数据库连接时覆盖运行中的 `.db`。

## 8. 错误码与限流

| HTTP | 错误码 | 说明 |
|---|---|---|
| 401 | UNAUTHENTICATED | 未登录/会话过期 |
| 403 | FORBIDDEN / SHARING_NOT_ALLOWED | 无权限/未共享 |
| 404 | NOT_FOUND | 资源不存在或不属于本人 |
| 409 | VERSION_CONFLICT | 编辑版本不匹配 |
| 409 | TASK_HAS_RECORD | 计划调整与已有记录冲突 |
| 409 | PLAN_ALREADY_ACTIVE | 用户已有启用周计划 |
| 409 | INVALID_STATE | 记录状态不允许当前操作 |
| 422 | VALIDATION_ERROR | 参数、类型、日期、目标非法 |
| 429 | RATE_LIMITED | 登录失败等限流 |

关键写入路径记录操作审计但不记录密码、会话 token、体重值到普通访问日志。API 需要生成 OpenAPI 并通过契约测试。
