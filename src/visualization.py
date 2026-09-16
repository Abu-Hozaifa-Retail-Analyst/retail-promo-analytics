"""Chart generation for the promo & profitability analysis deliverable."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

sns.set_theme(style="whitegrid", palette="Set2")
plt.rcParams["figure.dpi"] = 120
plt.rcParams["savefig.bbox"] = "tight"


def plot_margin_erosion_by_category(
    margin_erosion_category: pd.DataFrame, output_dir: Path
) -> Path:
    """Bar chart: margin % promo vs non-promo, by category."""
    df = margin_erosion_category.sort_values("margin_erosion_pts", ascending=False)
    fig, ax = plt.subplots(figsize=(9, 5))
    x = range(len(df))
    width = 0.38
    ax.bar(
        [i - width / 2 for i in x],
        df["avg_margin_pct_nonpromo"],
        width,
        label="Non-promo margin %",
        color="#4C72B0",
    )
    ax.bar(
        [i + width / 2 for i in x],
        df["avg_margin_pct_promo"],
        width,
        label="Promo margin %",
        color="#DD8452",
    )
    ax.set_xticks(list(x))
    ax.set_xticklabels(df["category"], rotation=30, ha="right")
    ax.set_ylabel("Average gross margin %")
    ax.set_title("Margin Erosion During Promotions, by Category")
    for i, pts in enumerate(df["margin_erosion_pts"]):
        ax.annotate(
            f"-{pts:.1f}pts",
            (i, df["avg_margin_pct_nonpromo"].iloc[i] + 1),
            ha="center",
            fontsize=9,
        )
    ax.legend()
    path = output_dir / "margin_erosion_by_category.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_promo_profitability_scatter(
    ranking_full: pd.DataFrame, output_dir: Path
) -> Path:
    """Scatter: revenue lift % vs incremental profit, one point per SKU."""
    fig, ax = plt.subplots(figsize=(9, 6))
    colors = ranking_full["promo_profitable"].map({True: "#55A868", False: "#C44E52"})
    ax.scatter(
        ranking_full["revenue_lift_pct"],
        ranking_full["incremental_profit_vs_baseline"],
        c=colors,
        alpha=0.6,
        s=28,
        edgecolor="white",
        linewidth=0.3,
    )
    ax.axhline(0, color="#333", linewidth=0.8, linestyle="--")
    ax.axvline(0, color="#333", linewidth=0.8, linestyle="--")
    ax.set_xlabel("Revenue lift during promo (%)")
    ax.set_ylabel("Incremental profit vs. non-promo baseline (SAR)")
    ax.set_title("Promo Profitability by SKU: Revenue Lift vs. Net Profit Impact")
    from matplotlib.patches import Patch

    ax.legend(
        handles=[
            Patch(color="#55A868", label="Net profitable"),
            Patch(color="#C44E52", label="Net unprofitable"),
        ]
    )
    path = output_dir / "promo_profitability_scatter.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_elasticity_distribution(
    elasticity_sku: pd.DataFrame, output_dir: Path
) -> Path:
    """Histogram of estimated price elasticity across SKUs."""
    fig, ax = plt.subplots(figsize=(9, 5))
    sns.histplot(
        elasticity_sku["elasticity"], bins=30, kde=True, ax=ax, color="#4C72B0"
    )
    ax.axvline(
        -1,
        color="#C44E52",
        linestyle="--",
        linewidth=1,
        label="Elastic/inelastic boundary (-1)",
    )
    ax.axvline(0, color="#333", linestyle=":", linewidth=1)
    ax.set_xlabel("Estimated price elasticity of demand")
    ax.set_ylabel("Number of SKUs")
    ax.set_title(
        "Distribution of Price Elasticity Across SKUs\n(Note: only 2% statistically significant — see README)"
    )
    ax.legend()
    path = output_dir / "elasticity_distribution.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_return_rate_by_category(
    return_rate_category: pd.DataFrame, output_dir: Path
) -> Path:
    """Bar chart: return rate % by category."""
    df = return_rate_category.sort_values("return_rate_pct", ascending=False)
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.barplot(data=df, x="category", y="return_rate_pct", ax=ax, color="#8172B2")
    ax.set_xticklabels(ax.get_xticklabels(), rotation=30, ha="right")
    ax.set_ylabel("Return rate (%)")
    ax.set_title("Return Rate by Category")
    path = output_dir / "return_rate_by_category.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def generate_all_charts(
    results: dict[str, pd.DataFrame], output_dir: Path
) -> list[Path]:
    """Generate the full standard chart set from a pipeline results dict."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    return [
        plot_margin_erosion_by_category(results["margin_erosion_category"], output_dir),
        plot_promo_profitability_scatter(results["ranking_full"], output_dir),
        plot_elasticity_distribution(results["elasticity_sku"], output_dir),
        plot_return_rate_by_category(results["return_rate_category"], output_dir),
    ]
