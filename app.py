"""
app.py — Flask web UI สำหรับคลังข่าวแจก กองทัพบก
รัน local : python app.py
Deploy     : Render.com / Railway (ดู Procfile)
"""

import os
import sqlite3
from datetime import datetime
from pathlib import Path

from flask import Flask, abort, render_template, request

# ── paths ──
BASE    = Path(__file__).parent
DB_PATH = Path(os.environ.get("DB_PATH", str(BASE / "news.db")))

app = Flask(__name__)

# ══════════════════════════════════════
# Helpers
# ══════════════════════════════════════
MONTHS_SHORT = [
    "", "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
    "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค.",
]

def fmt_date(s):
    """'2025-10-04' → '4 ต.ค. 2568'"""
    if not s:
        return "—"
    try:
        d = datetime.strptime(str(s)[:10], "%Y-%m-%d")
        return f"{d.day} {MONTHS_SHORT[d.month]} {d.year + 543}"
    except Exception:
        return str(s)


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def fetch_meta(conn, ref_code):
    """ดึง tags, units, persons, provinces ของข่าว 1 ฉบับ"""
    tags = [r[0] for r in conn.execute(
        "SELECT t.name FROM tags t "
        "JOIN press_release_tags pt ON t.id=pt.tag_id "
        "WHERE pt.press_release_ref=? ORDER BY t.name", (ref_code,)
    )]
    units = [r[0] for r in conn.execute(
        "SELECT unit_name FROM press_release_units "
        "WHERE press_release_ref=? ORDER BY unit_name", (ref_code,)
    )]
    persons = [r[0] for r in conn.execute(
        "SELECT person_name FROM press_release_persons "
        "WHERE press_release_ref=? ORDER BY person_name", (ref_code,)
    )]
    provinces = [r[0] for r in conn.execute(
        "SELECT province_name FROM press_release_provinces "
        "WHERE press_release_ref=? ORDER BY province_name", (ref_code,)
    )]
    return tags, units, persons, provinces


# ══════════════════════════════════════
# Context processor — inject globals ทุก template
# ══════════════════════════════════════
@app.context_processor
def inject_globals():
    conn = get_db()
    stats = {
        "total":   conn.execute("SELECT COUNT(*) FROM press_releases").fetchone()[0],
        "cats":    conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0],
        "tags":    conn.execute("SELECT COUNT(*) FROM tags").fetchone()[0],
        "pending": conn.execute(
            "SELECT COUNT(*) FROM press_releases WHERE review_status != 'ปกติ'"
        ).fetchone()[0],
    }
    categories = [r[0] for r in conn.execute("SELECT name FROM categories ORDER BY name")]
    conn.close()
    return {"stats": stats, "categories": categories}


# ══════════════════════════════════════
# Routes
# ══════════════════════════════════════

@app.route("/")
def index():
    q      = request.args.get("q", "").strip()
    cat    = request.args.get("cat", "").strip()
    tag    = request.args.get("tag", "").strip()
    year   = request.args.get("year", "").strip()
    review = request.args.get("review", "").strip()

    conn = get_db()

    # ── year distribution ──
    year_rows = conn.execute("""
        SELECT strftime('%Y', publish_date) AS yr, COUNT(*) AS cnt
        FROM press_releases WHERE publish_date IS NOT NULL
        GROUP BY yr ORDER BY yr
    """).fetchall()
    years_data = [(r["yr"], int(str(r["yr"])) + 543, r["cnt"]) for r in year_rows]

    # ── filter options ──
    all_tags = [r[0] for r in conn.execute(
        "SELECT name FROM tags WHERE status='approved' ORDER BY name"
    )]
    all_years = [str(int(r[0]) + 543) for r in conn.execute(
        "SELECT DISTINCT strftime('%Y', publish_date) AS yr "
        "FROM press_releases WHERE publish_date IS NOT NULL ORDER BY yr"
    )]

    # ── search / list ──
    results = []

    if q:
        fts_q   = q.replace('"', '""')
        year_ce = str(int(year) - 543) if year else ""
        results = conn.execute("""
            SELECT pr.ref_code, pr.publish_date, pr.title, pr.summary,
                   pr.review_status, pr.priority,
                   c.name AS category
            FROM press_releases_fts fts
            JOIN press_releases pr ON fts.ref_code = pr.ref_code
            LEFT JOIN categories c ON pr.category_id = c.id
            WHERE press_releases_fts MATCH ?
              AND (? = '' OR c.name = ?)
              AND (? = '' OR strftime('%Y', pr.publish_date) = ?)
              AND (? = '' OR pr.review_status != 'ปกติ')
            ORDER BY rank
            LIMIT 100
        """, (fts_q, cat, cat, year_ce, year_ce, review)).fetchall()
    else:
        where  = []
        params = []
        if cat:
            where.append("c.name = ?")
            params.append(cat)
        if tag:
            where.append(
                "pr.ref_code IN ("
                "SELECT press_release_ref FROM press_release_tags pt "
                "JOIN tags t ON pt.tag_id=t.id WHERE t.name=?)"
            )
            params.append(tag)
        if year:
            where.append("strftime('%Y', pr.publish_date) = ?")
            params.append(str(int(year) - 543))
        if review:
            where.append("pr.review_status != 'ปกติ'")

        sql = (
            "SELECT pr.ref_code, pr.publish_date, pr.title, pr.summary, "
            "pr.review_status, pr.priority, c.name AS category "
            "FROM press_releases pr "
            "LEFT JOIN categories c ON pr.category_id = c.id"
        )
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY pr.publish_date DESC LIMIT 100"
        results = conn.execute(sql, params).fetchall()

    # ── fetch tags for each result (up to 5) ──
    result_tags = {}
    for r in results:
        result_tags[r["ref_code"]] = [row[0] for row in conn.execute(
            "SELECT t.name FROM tags t JOIN press_release_tags pt ON t.id=pt.tag_id "
            "WHERE pt.press_release_ref=? LIMIT 5", (r["ref_code"],)
        )]

    conn.close()

    return render_template(
        "index.html",
        years_data=years_data,
        all_tags=all_tags,
        all_years=all_years,
        results=results,
        result_tags=result_tags,
        fmt_date=fmt_date,
        q=q, cat=cat, tag=tag, year=year, review=review,
    )


@app.route("/news/<ref_code>")
def detail(ref_code):
    conn = get_db()

    pr = conn.execute("""
        SELECT pr.*, c.name AS category
        FROM press_releases pr
        LEFT JOIN categories c ON pr.category_id = c.id
        WHERE pr.ref_code = ?
    """, (ref_code,)).fetchone()

    if not pr:
        conn.close()
        abort(404)

    content_row = conn.execute(
        "SELECT full_text FROM press_release_content WHERE ref_code=?",
        (ref_code,)
    ).fetchone()
    full_text = content_row["full_text"] if content_row else ""

    tags, units, persons, provinces = fetch_meta(conn, ref_code)

    prev_r = conn.execute(
        "SELECT ref_code, title FROM press_releases "
        "WHERE publish_date < ? ORDER BY publish_date DESC LIMIT 1",
        (pr["publish_date"],)
    ).fetchone()
    next_r = conn.execute(
        "SELECT ref_code, title FROM press_releases "
        "WHERE publish_date > ? ORDER BY publish_date ASC LIMIT 1",
        (pr["publish_date"],)
    ).fetchone()

    conn.close()

    return render_template(
        "detail.html",
        pr=pr,
        full_text=full_text,
        tags=tags,
        units=units,
        persons=persons,
        provinces=provinces,
        fmt_date=fmt_date,
        prev_r=prev_r,
        next_r=next_r,
    )


# ══════════════════════════════════════
# Dev runner
# ══════════════════════════════════════
if __name__ == "__main__":
    app.run(debug=True, port=5000)
