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

def db_ready():
    """ตรวจว่า press_releases มีข้อมูลจริง"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        n = conn.execute("SELECT COUNT(*) FROM press_releases").fetchone()[0]
        conn.close()
        return n > 0
    except Exception:
        return False

if db_ready():
    import sqlite3 as _sq
    _n = _sq.connect(str(DB_PATH)).execute("SELECT COUNT(*) FROM press_releases").fetchone()[0]
    print(f"[init_db] DB OK — {_n} rows, skip rebuild")
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
