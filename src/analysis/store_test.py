"""Design and analysis helpers for the store-level discount-cap test.

The test caps discounts at 10% in half of the stores and compares them with matched
stores that keep today's discounting. See `docs/store_test_design.md` for the reasoning.

    assign_stores        -> which stores get the cap (matched pairs, random within each pair)
    store_week_table     -> one row per store and week, built from the analysis table
    analyze_store_test   -> change in transactions and profit, with intervals and a verdict
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from src.analysis.breakeven import nominal_depth

BREAKEVEN_LOSS_PCT = 3.5  # a cap adds about 3.5% to profit, so losing 3.5% of transactions cancels it
CAP = 0.10


def assign_stores(store: pd.DataFrame, seed: int) -> pd.DataFrame:
    """Pair similar stores and pick, at random inside each pair, the one that gets the cap.

    Stores are sorted by region and store type, then taken two at a time, so each pair shares a
    region and, where the counts allow, a store type. Random choice inside a pair keeps the
    assignment fair; the fixed seed makes it reproducible and auditable.

    Returns:
        One row per store with `store_id`, `pair_id` and `arm` ("cap" or "control").
    """
    if len(store) % 2:
        raise ValueError("An even number of stores is needed to form matched pairs.")
    ordered = store.sort_values(["region", "store_type", "store_id"]).reset_index(drop=True)
    rng = np.random.default_rng(seed)
    rows: list[dict[str, Any]] = []
    for pair_id in range(len(ordered) // 2):
        first, second = ordered.loc[2 * pair_id, "store_id"], ordered.loc[2 * pair_id + 1, "store_id"]
        capped = first if rng.random() < 0.5 else second
        for store_id in (first, second):
            rows.append({"store_id": store_id, "pair_id": pair_id, "arm": "cap" if store_id == capped else "control"})
    return pd.DataFrame(rows)


def store_week_table(analysis: pd.DataFrame) -> pd.DataFrame:
    """Transactions, profit and the share of sales discounted deeper than the cap, per store and week."""
    df = analysis.copy()
    df["week"] = df["date"].dt.to_period("W").dt.start_time
    df["above_cap"] = nominal_depth(df["discount_pct"]) > CAP + 1e-9
    table = (
        df.groupby(["store_id", "week"])
        .agg(txns=("quantity", "size"), profit=("profit_amount", "sum"), above_cap_share=("above_cap", "mean"))
        .reset_index()
    )
    return table


def _paired_change(panel: pd.DataFrame, assignment: pd.DataFrame, metric: str, confidence: float) -> dict[str, float]:
    wide = panel.pivot(index="week", columns="store_id", values=metric)
    if wide.isna().any().any():
        raise ValueError("Every store needs a row for every week in the test window.")
    differences = []
    for _, pair in assignment.groupby("pair_id"):
        capped = pair.loc[pair["arm"] == "cap", "store_id"].iloc[0]
        control = pair.loc[pair["arm"] == "control", "store_id"].iloc[0]
        differences.append(float((wide[capped] - wide[control]).mean()))
    diff = np.array(differences)
    baseline = float(wide[assignment.loc[assignment["arm"] == "control", "store_id"]].to_numpy().mean())
    half_width = float(stats.t.ppf((1 + confidence) / 2, len(diff) - 1) * diff.std(ddof=1) / np.sqrt(len(diff)))
    mean = float(diff.mean())
    return {
        "change_pct": round(mean / baseline * 100, 2),
        "ci_low_pct": round((mean - half_width) / baseline * 100, 2),
        "ci_high_pct": round((mean + half_width) / baseline * 100, 2),
    }


def analyze_store_test(
    store_week: pd.DataFrame,
    assignment: pd.DataFrame,
    breakeven_loss_pct: float = BREAKEVEN_LOSS_PCT,
    confidence: float = 0.95,
) -> dict[str, Any]:
    """Compare capped stores with their matched controls over the test window.

    Args:
        store_week: Output of `store_week_table`, limited to the test weeks (all stores, all weeks).
        assignment: Output of `assign_stores`.
        breakeven_loss_pct: Loss of transactions that would cancel the profit gain from the cap.
        confidence: Confidence level of the intervals.

    Returns:
        Percentage change (capped vs control) in transactions and in profit per store-week, each with
        an interval, the share of sales above the cap in each arm, and a verdict on transactions:
        "safe" (the interval stays above the break-even loss), "harmful" (it sits wholly below) or
        "inconclusive" (run longer).
    """
    panel = store_week.merge(assignment[["store_id", "arm"]], on="store_id", how="inner")
    transactions = _paired_change(panel, assignment, "txns", confidence)
    profit = _paired_change(panel, assignment, "profit", confidence)
    if transactions["ci_low_pct"] >= -breakeven_loss_pct:
        verdict = "safe"
    elif transactions["ci_high_pct"] < -breakeven_loss_pct:
        verdict = "harmful"
    else:
        verdict = "inconclusive"
    return {
        "transactions": transactions,
        "profit": profit,
        "above_cap_share_pct": {
            str(arm): round(float(g["above_cap_share"].mean() * 100), 1) for arm, g in panel.groupby("arm")
        },
        "breakeven_loss_pct": breakeven_loss_pct,
        "verdict": verdict,
    }
