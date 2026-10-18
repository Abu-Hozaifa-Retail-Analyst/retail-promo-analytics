"""Break-even analysis: how much extra volume must a discount create to pay for itself?

For a product with margin m at list price, a discount of depth d leaves a unit
profit of (m - d) per unit of list price instead of m. Volume must therefore
rise by d / (m - d) just to keep total profit flat. At d >= m the product sells
at or below cost and no amount of extra volume can recover the loss.

Working in dollars (not per-transaction ratios) keeps the maths exact when a
band mixes products with different margins:

    required volume lift = discount given / profit actually earned

This is compared with the lift in quantity per transaction that the data
actually shows. Any gap has to come from extra transactions (traffic), which
this dataset cannot observe.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

DEPTH_STEP = 0.05  # discounts are stored to the cent, so snap to the nearest 5 points


def nominal_depth(discount_pct: pd.Series, step: float = DEPTH_STEP) -> pd.Series:
    """Snap a discount fraction to its nominal depth (0.0499 and 0.0501 both become 0.05)."""
    return ((discount_pct / step).round() * step).round(4)


def breakeven_table(
    df: pd.DataFrame,
    group_cols: list[str] | None = None,
    step: float = DEPTH_STEP,
) -> pd.DataFrame:
    """Required vs observed volume lift for each discount depth.

    Args:
        df: Analysis table (valid, non-return rows) with `is_promo`,
            `discount_pct`, `gross_sales`, `cost_amount`, `discount_amount`,
            `net_sales` and `quantity`.
        group_cols: Optional extra grouping, e.g. ["category"], so each
            depth is evaluated within each group (baseline quantity is then
            the group's own non-promo quantity).
        step: Width used to snap discount depths into bands.

    Returns:
        One row per (group, depth) with the margin at full price, the volume
        lift needed to hold profit flat, the quantity lift actually observed
        (with a 95% interval), the extra transaction growth still needed on
        top of that, and how many sales were priced at or below cost.
        `inf` means no volume lift can break even.
    """
    group_cols = list(group_cols or [])
    promo = df[df["is_promo"] & (df["gross_sales"] > 0)].copy()
    promo["depth"] = nominal_depth(promo["discount_pct"], step)
    promo["below_cost"] = promo["net_sales"] <= promo["cost_amount"]

    keys = group_cols + ["depth"]
    band = (
        promo.groupby(keys)
        .agg(
            txns=("quantity", "size"),
            gross=("gross_sales", "sum"),
            cost=("cost_amount", "sum"),
            discount=("discount_amount", "sum"),
            qty_mean=("quantity", "mean"),
            qty_var=("quantity", "var"),
            below_cost_txns=("below_cost", "sum"),
        )
        .reset_index()
    )

    # Baseline: quantity per transaction when there is no discount.
    non = df[~df["is_promo"]]
    if group_cols:
        base = non.groupby(group_cols)["quantity"].agg(base_mean="mean", base_var="var", base_n="size").reset_index()
        band = band.merge(base, on=group_cols, how="left")
    else:
        band["base_mean"] = non["quantity"].mean()
        band["base_var"] = non["quantity"].var()
        band["base_n"] = len(non)

    list_profit = band["gross"] - band["cost"]
    actual_profit = list_profit - band["discount"]
    required = np.where(actual_profit > 0, band["discount"] / actual_profit, np.inf)

    diff = band["qty_mean"] - band["base_mean"]
    se = np.sqrt(band["qty_var"] / band["txns"] + band["base_var"] / band["base_n"])
    observed = diff / band["base_mean"]

    out = band[keys + ["txns"]].copy()
    out["avg_discount_pct"] = (band["discount"] / band["gross"] * 100).round(1)
    out["full_price_margin_pct"] = (list_profit / band["gross"] * 100).round(1)
    out["required_volume_lift_pct"] = np.round(required * 100, 1)
    out["observed_qty_lift_pct"] = (observed * 100).round(2)
    out["observed_ci_low_pct"] = ((diff - 1.96 * se) / band["base_mean"] * 100).round(2)
    out["observed_ci_high_pct"] = ((diff + 1.96 * se) / band["base_mean"] * 100).round(2)
    out["extra_txn_growth_needed_pct"] = np.round(((1 + required) / (1 + observed) - 1) * 100, 1)
    out["below_cost_txns"] = band["below_cost_txns"].astype(int)
    out["below_cost_share_pct"] = (band["below_cost_txns"] / band["txns"] * 100).round(1)
    return out.sort_values(keys).reset_index(drop=True)


def discount_cost_summary(df: pd.DataFrame) -> dict:
    """What discounts cost in total, and how much volume could be lost before removing them pays.

    `max_tolerable_volume_loss_pct` answers the practical question: if every
    discount were removed, what share of the promoted volume could walk away
    before profit fell below today's level? It equals discount given divided by
    the profit those same sales would earn at list price.
    """
    promo = df[df["is_promo"]]
    discount = float(promo["discount_amount"].sum())
    profit = float(df["profit_amount"].sum())
    promo_list_profit = float(promo["profit_amount"].sum()) + discount
    below = promo[promo["net_sales"] <= promo["cost_amount"]]
    return {
        "promo_txns": int(len(promo)),
        "promo_share_pct": round(len(promo) / len(df) * 100, 1),
        "total_discount_given": round(discount),
        "total_profit": round(profit),
        "discount_pct_of_profit": round(discount / profit * 100, 1),
        "profit_if_no_discounts_same_volume": round(profit + discount),
        "max_tolerable_volume_loss_pct": round(discount / promo_list_profit * 100, 1),
        "below_cost_txns": int(len(below)),
        "below_cost_share_of_promo_pct": round(len(below) / len(promo) * 100, 1),
        "loss_on_below_cost_txns": round(float(below["profit_amount"].sum())),
    }
