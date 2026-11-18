# Linux 部署（systemd + SSH 隧道）

适合把服务跑在远程 Linux 上，本机用 SSH 端口转发访问；服务默认只监听 `127.0.0.1`，不必对公网开放业务端口。

## 1. 准备

```bash
sudo mkdir -p /opt/fitness-manager-v1
# 将项目同步到该目录后：
cd /opt/fitness-manager-v1

python3.12 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -U pip
pip install -e "backend/[dev]"

cd frontend && npm ci && npm run build && cd ..
chmod +x scripts/linux/*.sh
```

## 2. 安装并开机自启

```bash
sudo bash scripts/linux/install-systemd.sh /opt/fitness-manager-v1
```

可选环境变量：

- `FITMANAGER_USER`：运行用户（默认 `fitmanager`）
- `APP_PORT`：监听端口（默认 `18080`，需为空闲端口）

## 3. 本机访问

```bash
ssh -N -L 18080:127.0.0.1:18080 user@your-server
```

浏览器打开 `http://127.0.0.1:18080`，完成首次管理员初始化。

## 4. 常用命令

```bash
sudo systemctl status fitmanager
sudo systemctl restart fitmanager
sudo systemctl stop fitmanager
sudo journalctl -u fitmanager -f
```

## 5. 说明

- 单元文件模板：`deploy/linux/fitmanager.service`
- 启动脚本：`scripts/linux/run-prod.sh`（加载 `.env`、执行迁移、启动 uvicorn）
- 生产模式会同源托管 `frontend/dist`，并在启动时补做当日自动备份、滚动计划任务
- 防火墙/安全组通常只需放行 SSH（22），不必放行 `APP_PORT`
