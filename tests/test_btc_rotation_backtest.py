from __future__ import annotations
import sys,unittest
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"scripts"))
from btc_rotation_backtest import backtest_rotation
def data(count=500,wave=0):
 ts=pd.date_range("2025-01-01",periods=count,freq="1h",tz="UTC");c=100*np.exp(np.arange(count)*.0001+np.sin(np.arange(count)/20)*wave);return pd.DataFrame({"timestamp":ts,"close":c})
class BacktestTests(unittest.TestCase):
 def test_benchmarks_costs_and_no_same_close(self):
  r=backtest_rotation(data(wave=.05),data());self.assertEqual(r["btc_hold_terminal_btc_units"],1);self.assertIn("usd_hold_terminal_btc_units",r);self.assertGreaterEqual(r["total_fees_and_slippage_btc"],0);self.assertIn("next completed candle",r["execution_assumption"]);self.assertFalse(r["test_optimization_performed"])
 def test_metrics_and_splits(self):
  r=backtest_rotation(data(wave=.08),data());self.assertIn("maximum_drawdown_pct",r);self.assertIn("number_of_rotations",r);self.assertLess(r["train_end_index"],r["validation_end_index"]);self.assertEqual(r["test_start_index"],r["validation_end_index"])
 def test_insufficient_history(self):
  with self.assertRaises(ValueError):backtest_rotation(data(50),data(50))
if __name__=="__main__":unittest.main()
