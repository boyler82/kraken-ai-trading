from __future__ import annotations

import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from scripts import run_research


class RunResearchOutputTest(unittest.TestCase):
    def test_quiet_captures_reports_and_executes_every_module(self):
        calls = []
        def fake_run(command, **kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(command, 0, "detailed module report\n", None)
        with tempfile.TemporaryDirectory() as directory, patch.object(run_research, "LOG_PATH", Path(directory) / "run.log"), patch.object(run_research, "STATUS_PATH", Path(directory) / "status.json"), patch.object(run_research.subprocess, "run", side_effect=fake_run):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = run_research.run_quiet({})
            self.assertEqual(code, 0)
            self.assertEqual(len(calls), len(run_research.STEPS) + 1)
            self.assertNotIn("detailed module report", output.getvalue())
            self.assertIn("Research pipeline: SUCCESS", output.getvalue())

    def test_failure_prints_module_code_tail_and_log(self):
        count = 0
        def fake_run(command, **kwargs):
            nonlocal count; count += 1
            code = 3 if count == 2 else 0
            return subprocess.CompletedProcess(command, code, "\n".join(f"line {x}" for x in range(30)), None)
        with tempfile.TemporaryDirectory() as directory, patch.object(run_research, "LOG_PATH", Path(directory) / "run.log"), patch.object(run_research, "STATUS_PATH", Path(directory) / "status.json"), patch.object(run_research.subprocess, "run", side_effect=fake_run):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = run_research.run_quiet({})
            self.assertEqual(code, 3)
            self.assertIn("FAILED MODULE", output.getvalue())
            self.assertIn("RETURN CODE: 3", output.getvalue())
            self.assertIn("line 29", output.getvalue())
            self.assertIn("LOG PATH", output.getvalue())

    def test_verbose_streams_existing_commands(self):
        with patch.object(run_research.subprocess, "run", side_effect=[subprocess.CompletedProcess([], 0), subprocess.CompletedProcess([], 0)]) as mocked:
            self.assertEqual(run_research.run_verbose({}), 0)
            self.assertEqual(mocked.call_count, 2)
            self.assertNotIn("stdout", mocked.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
