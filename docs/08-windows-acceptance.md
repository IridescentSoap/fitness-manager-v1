# Windows T6 实机 / E2E 验收清单

本清单对应 `TASKS.md` T6 与 `docs/07-test-cases.md` 中的发布验收项。

## 1. 本机一键验证

```powershell
.\scripts\build.ps1
.\scripts\e2e.ps1
```

`e2e.ps1` 会：

1. 使用隔离目录 `data/e2e`、`backups/e2e`
2. 在 `127.0.0.1:18080`（可用 `E2E_PORT` 覆盖）启动生产模式服务
3. 运行 Playwright：桌面 1366（T01/T02/T05/T10/T11/T20/T22/T23/T28）与手机 375（T30）
4. 结束后停止 E2E 进程

后端回归：

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
```

## 2. 局域网双机检查（人工）

在**服务主机**上：

1. `.\scripts\build.ps1` 后 `.\scripts\start.ps1`
2. 记录脚本打印的 `LAN: http://<IP>:8080`（必须是**服务主机** IP，不是访问端自己的 IP）
3. `start.ps1` 会自动合并本机局域网 IP 到 `ALLOWED_HOSTS`；也可手动写入 `.env`
4. 管理员 PowerShell 执行一次 `.\scripts\open-lan-firewall.ps1`，在「专用」配置文件放行 TCP 8080（及开发用 5173）
5. 首次管理员初始化必须在服务主机浏览器打开 `http://127.0.0.1:8080`

在**同网段第二台设备**上：

| 步骤 | 预期 |
|---|---|
| 浏览器打开 `http://<LAN_IP>:8080` | 登录页可加载 |
| 普通用户登录 | 进入数据概览 |
| 勾选动作草稿并提交 | 草稿自动保存；提交后出现在统计 |
| 改共享开关后刷新比较页 | 撤销立即生效 |
| 手机竖屏约 375 宽 | 菜单可开合，主要操作可完成，无关键横向溢出 |

> 单机开发环境无法替代第二台真机；若暂无第二台，至少用另一浏览器配置文件 + 本机 `http://127.0.0.1:8080` 走完流程，并在清单中注明「双机未测」。

## 3. 性能抽检（建议，非硬门禁）

参考 `docs/06-architecture.md` 目标：普通四核 / 8GB / SSD / 局域网。

| 场景 | 观察 |
|---|---|
| 概览 / 计划 / 记录主要 GET | 体感流畅；可用浏览器 Network 看 P95 是否约 <500ms |
| 勾选动作 PATCH | 约 <800ms，无丢失勾选 |
| 多用户比较 | 约 <1s |
| 5 个会话同时勾选 | 无互相覆盖写丢（版本冲突应提示） |

## 4. 备份与调度

| 项 | 验证方式 |
|---|---|
| 手动备份 / 恢复 | 设置页或 `scripts/backup.ps1` / `restore.ps1`；E2E T28 |
| 生产启动补跑 | `APP_ENV=production` 启动时补齐日程并尝试当日备份 |
| 03:00 日备 / 00:05 滚动 | 进程内调度器（见 `backend/app/core/scheduler.py`）；单元测试 `test_scheduler.py` |

## 5. 结果记录模板

```text
日期：
主机 OS：
Playwright：通过 / 失败（附报告路径 e2e/playwright-report）
pytest：N passed
LAN 第二台：已测 / 未测（设备：）
性能抽检：通过 / 未测 / 备注
遗留：
```
