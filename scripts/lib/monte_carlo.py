from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd


def calculate_equity_curve(
    trade_returns_pct: Iterable[float],
    starting_capital: float,
    position_size_pct: float,
) -> pd.Series:
    """Build an equity curve from a sequence of trade returns in percent."""

    returns = pd.Series(list(trade_returns_pct)).dropna()
    if returns.empty:
        return pd.Series(dtype=float)

    capital = float(starting_capital)
    equity = []

    for trade_return in returns:
        capital = capital * (1 + (float(trade_return) / 100.0) * (position_size_pct / 100.0))
        equity.append(capital)

    return pd.Series(equity, dtype=float)


def calculate_max_drawdown(equity_curve: Iterable[float]) -> float | None:
    """Return max drawdown in percent for an equity curve."""

    equity = pd.Series(list(equity_curve)).dropna()
    if equity.empty:
        return None

    peak = equity.cummax()
    drawdown = equity / peak - 1
    return float(drawdown.min() * 100)


def run_monte_carlo(
    returns_pct: Iterable[float],
    simulations: int = 5000,
    starting_capital: float = 10000,
    position_size_pct: float = 5,
    seed: int = 42,
) -> pd.DataFrame:
    """Bootstrap trade returns and return per-simulation outcome rows."""

    returns = pd.Series(list(returns_pct)).dropna()
    if returns.empty or simulations <= 0:
        return pd.DataFrame(columns=["simulation", "final_capital", "total_return_pct", "max_drawdown_pct"])

    rng = np.random.default_rng(seed)
    base_returns = returns.to_numpy(dtype=float)
    sample_idx = rng.integers(0, len(base_returns), size=(simulations, len(base_returns)))
    sampled_returns = base_returns[sample_idx]

    growth = 1 + (sampled_returns / 100.0) * (position_size_pct / 100.0)
    equity = starting_capital * np.cumprod(growth, axis=1)
    peaks = np.maximum.accumulate(equity, axis=1)
    drawdowns = equity / peaks - 1

    final_capital = equity[:, -1]
    max_drawdown_pct = drawdowns.min(axis=1) * 100

    return pd.DataFrame(
        {
            "simulation": np.arange(1, simulations + 1),
            "final_capital": final_capital,
            "total_return_pct": (final_capital / starting_capital - 1) * 100,
            "max_drawdown_pct": max_drawdown_pct,
        }
    )


def summarize_monte_carlo(results_df: pd.DataFrame) -> dict:
    """Summarize Monte Carlo output into central tendency and tail metrics."""

    if results_df is None or results_df.empty:
        return {
            "simulations": 0,
            "median_final_capital": None,
            "median_return_pct": None,
            "mean_return_pct": None,
            "p5_return_pct": None,
            "p25_return_pct": None,
            "p75_return_pct": None,
            "p95_return_pct": None,
            "probability_loss_pct": None,
            "probability_profit_pct": None,
            "median_max_drawdown_pct": None,
            "p95_max_drawdown_pct": None,
            "worst_max_drawdown_pct": None,
        }

    returns = results_df["total_return_pct"].dropna()
    drawdowns = results_df["max_drawdown_pct"].dropna()
    final_capital = results_df["final_capital"].dropna()

    return {
        "simulations": int(len(results_df)),
        "median_final_capital": float(final_capital.median()) if not final_capital.empty else None,
        "median_return_pct": float(returns.median()) if not returns.empty else None,
        "mean_return_pct": float(returns.mean()) if not returns.empty else None,
        "p5_return_pct": float(returns.quantile(0.05)) if not returns.empty else None,
        "p25_return_pct": float(returns.quantile(0.25)) if not returns.empty else None,
        "p75_return_pct": float(returns.quantile(0.75)) if not returns.empty else None,
        "p95_return_pct": float(returns.quantile(0.95)) if not returns.empty else None,
        "probability_loss_pct": float((returns < 0).mean() * 100) if not returns.empty else None,
        "probability_profit_pct": float((returns > 0).mean() * 100) if not returns.empty else None,
        "median_max_drawdown_pct": float(drawdowns.median()) if not drawdowns.empty else None,
        "p95_max_drawdown_pct": float(drawdowns.quantile(0.95)) if not drawdowns.empty else None,
        "worst_max_drawdown_pct": float(drawdowns.min()) if not drawdowns.empty else None,
    }
