"""Charts for the promotion & profitability analysis.

Each function takes result tables produced by `src.pipeline` and saves one PNG.
Caveats are written onto the charts themselves, so they travel with the image
when it is pasted into a slide or an email.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.ticker import FuncFormatter

sns.set_theme(style="whitegrid")
plt.rcParams["figure.dpi"] = 120
plt.rcParams["savefig.bbox"] = "tight"

_RED, _BLUE, _GREY = "#C44E52", "#4C72B0", "#7F7F7F"


def _footnote(fig: plt.Figure, text: str) -> None:
    fig.text(0.01, -0.02, text, ha="left", va="top", fontsize=8, color=_GREY, wrap=True)


def _save(fig: plt.Figure, path: Path) -> Path:
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_breakeven_gap(breakeven: pd.DataFrame, output_dir: Path) -> Path:
    """Volume lift each discount needs to break even vs the basket-size lift actually observed."""
    df = breakeven.replace([np.inf, -np.inf], np.nan)
    labels = [f"{d:.0%}" for d in df["depth"]]
    x = np.arange(len(df))

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.bar(
        x,
        df["required_volume_lift_pct"],
        width=0.55,
        color=_RED,
        label="Volume lift needed to hold profit flat",
    )
    err = [
        df["observed_qty_lift_pct"] - df["observed_ci_low_pct"],
        df["observed_ci_high_pct"] - df["observed_qty_lift_pct"],
    ]
    ax.errorbar(
        x,
        df["observed_qty_lift_pct"],
        yerr=err,
        fmt="o",
        color=_BLUE,
        capsize=5,
        markersize=7,
        label="Observed lift in units per transaction (95% CI)",
        zorder=3,
    )
    top = df["required_volume_lift_pct"].max()
    for i, row in df.reset_index(drop=True).iterrows():
        ax.annotate(
            f"needs +{row['required_volume_lift_pct']:.0f}%",
            (i, row["required_volume_lift_pct"]),
            ha="center",
            va="bottom",
            fontsize=9,
            xytext=(0, 3),
            textcoords="offset points",
        )
        ax.annotate(
            f"observed {row['observed_qty_lift_pct']:+.2f}%",
            (i, 0),
            ha="center",
            va="top",
            fontsize=9,
            color=_BLUE,
            xytext=(0, -14),
            textcoords="offset points",
        )
    ax.axhline(0, color="#333", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_xlabel("Discount depth")
    ax.set_ylabel("Volume lift (%)")
    ax.set_ylim(-0.08 * top, top * 1.15)
    ax.set_title("Each discount needs far more volume than the data shows")
    ax.legend(loc="upper left")
    _footnote(
        fig,
        "Observed = change in units per transaction. Extra transactions (traffic) cannot be observed in this data.",
    )
    return _save(fig, output_dir / "breakeven_gap.png")


def plot_scenario_curves(scenario_curve: pd.DataFrame, breakeven_elasticities: pd.DataFrame, output_dir: Path) -> Path:
    """Profit change from capping discounts, across demand responses, with break-even points."""
    fig, ax = plt.subplots(figsize=(9.5, 5.8))
    caps = sorted(scenario_curve["cap"].unique())
    palette = dict(zip(caps, sns.color_palette("viridis", len(caps)), strict=True))
    be = breakeven_elasticities.set_index("cap")["breakeven_elasticity"]
    for cap, g in scenario_curve.groupby("cap"):
        g = g.sort_values("elasticity", ascending=False)
        label = "Cap 0% (no discounts)" if cap == 0 else f"Cap {cap:.0%}"
        ax.plot(
            g["elasticity"],
            g["profit_change"] / 1e6,
            color=palette[cap],
            linewidth=2,
            label=label,
        )
        if np.isfinite(be.get(cap, np.nan)):
            ax.plot(be[cap], 0, "o", color=palette[cap], markersize=7)
            ax.annotate(
                f"{be[cap]:.1f}".replace("-", "−"),
                (be[cap], 0),
                xytext=(0, 11),
                textcoords="offset points",
                ha="center",
                fontsize=9,
                color=palette[cap],
                fontweight="bold",
                bbox={
                    "boxstyle": "round,pad=0.15",
                    "fc": "white",
                    "ec": "none",
                    "alpha": 0.9,
                },
            )
    ax.axhline(0, color="#333", linewidth=0.8)
    ax.axvline(-0.003, color=_GREY, linestyle="--", linewidth=1)
    ax.annotate(
        "estimated elasticity\n(−0.003)",
        (-0.003, -22),
        xytext=(6, 0),
        textcoords="offset points",
        fontsize=8,
        color=_GREY,
        ha="left",
        va="center",
    )
    ax.invert_xaxis()
    ax.set_xlabel("Assumed price elasticity (0 = no reaction, −10 = extremely price-sensitive)")
    ax.set_ylabel("Profit change vs today (million SAR)")
    ax.set_title("Capping discounts pays unless demand is extremely price-sensitive")
    ax.legend(loc="upper right")
    _footnote(
        fig,
        "Dots mark the break-even elasticity of each cap. A model, not a forecast: constant elasticity, "
        "no effects on other products, loyalty or competitors.",
    )
    return _save(fig, output_dir / "scenario_profit_curves.png")


def plot_elasticity_estimates(spec_table: pd.DataFrame, category_table: pd.DataFrame, output_dir: Path) -> Path:
    """Forest plot of pooled elasticity estimates with 95% intervals."""
    rows = [(r["specification"], r["elasticity"], r["ci_low"], r["ci_high"]) for _, r in spec_table.iterrows()]
    rows += [
        (str(r["category"]), r["elasticity"], r["ci_low"], r["ci_high"])
        for _, r in category_table.sort_values("category").iterrows()
    ]
    n_specs = len(spec_table)
    y = np.arange(len(rows))[::-1].astype(float)
    y[n_specs:] -= 0.6  # visual gap between the overall estimates and the categories

    fig, ax = plt.subplots(figsize=(9, 5.8))
    for yi, (_, est, lo, hi) in zip(y, rows, strict=True):
        ax.errorbar(
            est,
            yi,
            xerr=[[est - lo], [hi - est]],
            fmt="o",
            color=_BLUE,
            capsize=4,
            markersize=6,
        )
    ax.axvline(0, color="#333", linewidth=0.9)
    ax.axvline(-1, color=_RED, linestyle="--", linewidth=1.2)
    ax.text(
        -0.98,
        y.max(),
        "unit elastic (−1)",
        color=_RED,
        fontsize=9,
        va="center",
        ha="left",
    )
    ax.set_yticks(y)
    ax.set_yticklabels([r[0] for r in rows])
    ax.set_xlim(-1.15, 0.3)
    ax.set_xlabel("Price elasticity of demand (95% interval)")
    ax.set_title("Price elasticity is about zero, nowhere near −1")
    _footnote(
        fig,
        "Pooled log-log estimate with SKU fixed effects and SKU-clustered standard errors. Top block: whole dataset; "
        "bottom block: by category.",
    )
    return _save(fig, output_dir / "elasticity_estimates.png")


def plot_return_rate_by_category(return_rate_category: pd.DataFrame, output_dir: Path) -> Path:
    """Bar chart: return rate % by category."""
    df = return_rate_category.sort_values("return_rate_pct", ascending=False)
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.barplot(data=df, x="category", y="return_rate_pct", ax=ax, color="#8172B2")
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.2f}%"))
    ax.set_xlabel("")
    ax.set_ylabel("Returned units / units sold")
    ax.set_title("Return rates are low in every category")
    return _save(fig, output_dir / "return_rate_by_category.png")


def generate_all_charts(results: dict, output_dir: Path) -> list[Path]:
    """Generate the standard chart set from the dict returned by `src.pipeline.run_full_pipeline`."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    return [
        plot_breakeven_gap(results["breakeven"], output_dir),
        plot_scenario_curves(results["scenario_curve"], results["breakeven_elasticity"], output_dir),
        plot_elasticity_estimates(
            results["pooled_elasticity"],
            results["pooled_elasticity_by_category"],
            output_dir,
        ),
        plot_return_rate_by_category(results["return_rate_category"], output_dir),
    ]
