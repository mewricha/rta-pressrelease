"""
init_db.py — สร้าง news.db จาก seed.sql ก่อน gunicorn start
รันโดย Procfile: python init_db.py && gunicorn ...
"""
import os
import sqlite3
from pathlib import Path

BASE     = Path(__file__).parent
DB_PATH  = Path(os.environ.get("DB_PATH", str(BASE / "news.db")))
SEED_SQL = BASE / "seed.sql"

if DB_PATH.exists() and DB_PATH.stat().st_size > 1024:
    print(f"[init_db] {DB_PATH} already exists ({DB_PATH.stat().st_size:,} bytes) — skip")
else:
    if not SEED_SQL.exists():
        print(f"[init_db] ERROR: {SEED_SQL} not found")
        raise SystemExit(1)
    if DB_PATH.exists():
        DB_PATH.unlink()
    print(f"[init_db] building {DB_PATH} from seed.sql …")
    conn = sqlite3.connect(str(DB_PATH))
    conn.executescript(SEED_SQL.read_text(encoding="utf-8"))
    conn.close()
    print(f"[init_db] done — {DB_PATH.stat().st_size:,} bytes")
