from __future__ import annotations

import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "journal" / "project_memory.sqlite"


def main() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"SQLite database not found: {DB_PATH}")

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE signals
            SET status = 'STALE_TEST_SIGNAL',
                notes = CASE
                    WHEN notes IS NULL OR TRIM(notes) = '' THEN 'marked stale during cleanup'
                    ELSE notes || '; marked stale during cleanup'
                END
            WHERE status = 'OPEN'
              AND date IN ('2026-06-28', '2026-06-29')
            """
        )
        changed = cur.rowcount if cur.rowcount is not None else 0
        conn.commit()

        status_rows = cur.execute(
            "SELECT status, COUNT(*) FROM signals GROUP BY status ORDER BY status"
        ).fetchall()

    print(f"Changed records: {changed}")
    print("SELECT status, COUNT(*) FROM signals GROUP BY status;")
    for status, count in status_rows:
        print(f"{status} | {count}")


if __name__ == "__main__":
    main()
