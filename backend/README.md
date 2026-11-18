# FitManager Backend

FastAPI + SQLAlchemy 2 + Alembic + SQLite。

## 开发

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
pytest
```
