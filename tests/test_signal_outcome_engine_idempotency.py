from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import signal_outcome_engine as engine  # noqa: E402


class SignalOutcomeIdempotencyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.executescript(
            """
            CREATE TABLE signals (
                signal_id TEXT PRIMARY KEY, asset TEXT, recommendation TEXT, status TEXT,
                close_price REAL, real_return_pct REAL, updated_at TEXT
            );
            CREATE TABLE signal_outcomes (
                signal_key TEXT PRIMARY KEY, signal_id TEXT NOT NULL, asset TEXT,
                recommendation TEXT, open_date TEXT, close_date TEXT, close_reason TEXT,
                entry_price REAL, exit_price REAL, real_return_pct REAL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE signal_history (
                history_id INTEGER PRIMARY KEY AUTOINCREMENT, signal_key TEXT NOT NULL,
                signal_id TEXT NOT NULL, run_date TEXT NOT NULL, asset TEXT,
                recommendation TEXT, created_at TEXT NOT NULL,
                UNIQUE(signal_key, run_date)
            );
            INSERT INTO signals VALUES ('s1', 'BTC', 'BUY', 'OPEN', NULL, NULL, NULL);
            """
        )
        engine._ensure_history_status_columns(self.conn)
        self.signal = {"signal_id": "s1", "asset": "BTC", "recommendation": "BUY"}
        self.outcome = {
            "signal_key": "s1", "signal_id": "s1", "asset": "BTC",
            "recommendation": "BUY", "open_date": "2026-07-01", "close_date": "2026-07-05",
            "close_reason": "planned_exit_date_reached", "entry_price": 100.0,
            "exit_price": 105.0, "real_return_pct": 5.0,
            "created_at": "2026-07-05T00:00:00", "updated_at": "2026-07-05T00:00:00",
        }

    def tearDown(self) -> None:
        self.conn.close()

    @staticmethod
    def counters() -> dict[str, int]:
        return {
            "outcomes_inserted": 0, "outcomes_updated": 0,
            "outcomes_already_complete": 0, "signals_closed": 0,
            "duplicate_history_events_skipped": 0,
        }

    def snapshot(self) -> tuple[list[tuple], list[tuple], list[tuple]]:
        return (
            self.conn.execute("SELECT * FROM signal_outcomes ORDER BY signal_key").fetchall(),
            self.conn.execute("SELECT signal_id,status,close_price,real_return_pct FROM signals").fetchall(),
            self.conn.execute("SELECT signal_id,old_status,new_status FROM signal_history ORDER BY history_id").fetchall(),
        )

    def test_insert_repair_and_repeated_run_are_idempotent(self) -> None:
        # A: first run inserts the outcome and closes the signal.
        first = self.counters()
        engine._persist_outcome_and_close(self.conn, self.signal, self.outcome, first)
        self.assertEqual((first["outcomes_inserted"], first["signals_closed"]), (1, 1))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM signal_outcomes").fetchone()[0], 1)
        self.assertEqual(self.conn.execute("SELECT status FROM signals").fetchone()[0], "CLOSED")

        # B: an existing complete outcome repairs an accidentally OPEN signal without duplication.
        self.conn.execute("UPDATE signals SET status='OPEN'")
        second = self.counters()
        engine._persist_outcome_and_close(self.conn, self.signal, self.outcome, second)
        self.assertEqual(second["outcomes_already_complete"], 1)
        self.assertEqual(second["signals_closed"], 1)
        self.assertEqual(second["duplicate_history_events_skipped"], 1)

        # C/D: CLOSED remains CLOSED and two further runs have identical database state.
        before = self.snapshot()
        for _ in range(2):
            engine._persist_outcome_and_close(self.conn, self.signal, self.outcome, self.counters())
            self.assertEqual(self.snapshot(), before)

        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM signal_outcomes GROUP BY signal_key").fetchone()[0], 1
        )
        self.assertEqual(
            self.conn.execute(
                "SELECT COUNT(*) FROM signal_history WHERE signal_id='s1' AND old_status='OPEN' AND new_status='CLOSED'"
            ).fetchone()[0],
            1,
        )

    def test_migration_and_same_asset_recommendation_do_not_collide(self) -> None:
        legacy = dict(self.outcome, signal_key="BTC:BUY")
        fields = engine.OUTCOME_FIELDS
        self.conn.execute(
            f"INSERT INTO signal_outcomes ({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)})",
            tuple(legacy[field] for field in fields),
        )
        self.assertEqual(engine._migrate_outcome_keys(self.conn), 1)
        self.assertEqual(self.conn.execute("SELECT signal_key FROM signal_outcomes").fetchone()[0], "s1")

        self.conn.execute("INSERT INTO signals VALUES ('s2', 'BTC', 'BUY', 'OPEN', NULL, NULL, NULL)")
        second_signal = {"signal_id": "s2", "asset": "BTC", "recommendation": "BUY"}
        second_outcome = dict(self.outcome, signal_key="s2", signal_id="s2", open_date="2026-07-10")
        engine._persist_outcome_and_close(self.conn, second_signal, second_outcome, self.counters())
        keys = self.conn.execute("SELECT signal_key FROM signal_outcomes ORDER BY signal_key").fetchall()
        self.assertEqual(keys, [("s1",), ("s2",)])


if __name__ == "__main__":
    unittest.main()
