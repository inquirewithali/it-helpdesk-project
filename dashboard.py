"""
IT Help Desk Analytics Dashboard
Generates a multi-panel KPI report and saves it to output/dashboard.png.
Run: python dashboard.py
"""

import matplotlib
matplotlib.use("Agg")  # headless — safe in all environments
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
from matplotlib.ticker import MaxNLocator
import numpy as np
from pathlib import Path

PALETTE = {
    "primary":   "#1B4F8A",
    "accent":    "#F07F26",
    "green":     "#2ECC71",
    "red":       "#E74C3C",
    "light_bg":  "#F4F6F9",
    "mid_grey":  "#BDC3C7",
    "text":      "#2C3E50",
}

PRIORITY_ORDER = ["P1 - Critical", "P2 - High", "P3 - Medium", "P4 - Low"]
PRIORITY_COLORS = ["#E74C3C", "#F07F26", "#F1C40F", "#2ECC71"]


def load_data(path="data/tickets.csv"):
    df = pd.read_csv(path, parse_dates=["created_at", "resolved_at"])
    df["resolution_hours"] = pd.to_numeric(df["resolution_hours"], errors="coerce")
    df["satisfaction_score"] = pd.to_numeric(df["satisfaction_score"], errors="coerce")
    df["met_sla"] = df["met_sla"].astype(str).map({"True": True, "False": False})
    df["month"] = df["created_at"].dt.to_period("M")
    df["hour"] = df["created_at"].dt.hour
    return df


def kpi_tile(ax, value, label, color=None, fmt="{:.0f}"):
    ax.set_facecolor(PALETTE["light_bg"])
    ax.axis("off")
    ax.text(0.5, 0.62, fmt.format(value) if isinstance(value, (int, float)) else value,
            ha="center", va="center", fontsize=28, fontweight="bold",
            color=color or PALETTE["primary"], transform=ax.transAxes)
    ax.text(0.5, 0.28, label, ha="center", va="center", fontsize=9,
            color=PALETTE["text"], transform=ax.transAxes)
    for spine in ax.spines.values():
        spine.set_visible(False)


def plot_monthly_trend(ax, df):
    monthly = df.groupby("month").size().reset_index(name="count")
    monthly["month_str"] = monthly["month"].astype(str)

    x = range(len(monthly))
    ax.fill_between(x, monthly["count"], alpha=0.18, color=PALETTE["primary"])
    ax.plot(x, monthly["count"], color=PALETTE["primary"], linewidth=2, marker="o", markersize=4)

    # rolling 3-month average
    avg = monthly["count"].rolling(3, center=True).mean()
    ax.plot(x, avg, color=PALETTE["accent"], linewidth=1.8, linestyle="--", label="3-mo avg")

    step = max(1, len(monthly) // 8)
    ax.set_xticks(list(x)[::step])
    ax.set_xticklabels(monthly["month_str"].tolist()[::step], rotation=30, ha="right", fontsize=7)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=5))
    ax.set_title("Monthly Ticket Volume", fontsize=10, fontweight="bold", color=PALETTE["text"], pad=8)
    ax.legend(fontsize=7)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.set_facecolor("white")


def plot_category_bar(ax, df):
    cat_counts = df["category"].value_counts()
    colors = [PALETTE["primary"] if i < 3 else PALETTE["mid_grey"] for i in range(len(cat_counts))]
    bars = ax.barh(cat_counts.index, cat_counts.values, color=colors, edgecolor="white")
    for bar, val in zip(bars, cat_counts.values):
        ax.text(val + 8, bar.get_y() + bar.get_height() / 2,
                str(val), va="center", fontsize=7.5, color=PALETTE["text"])
    ax.set_title("Tickets by Category", fontsize=10, fontweight="bold", color=PALETTE["text"], pad=8)
    ax.invert_yaxis()
    ax.set_xlabel("Ticket Count", fontsize=8)
    ax.grid(axis="x", linestyle="--", alpha=0.4)
    ax.set_facecolor("white")
    ax.tick_params(labelsize=8)


def plot_sla_by_priority(ax, df):
    resolved = df[df["met_sla"].notna()]
    sla = resolved.groupby("priority")["met_sla"].apply(lambda x: 100 * x.sum() / len(x)).reindex(PRIORITY_ORDER)

    bars = ax.bar(PRIORITY_ORDER, sla.values, color=PRIORITY_COLORS, edgecolor="white", width=0.55)
    ax.axhline(90, color=PALETTE["text"], linestyle="--", linewidth=1, label="90% target")
    for bar, val in zip(bars, sla.values):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 1.2,
                f"{val:.1f}%", ha="center", fontsize=8, fontweight="bold", color=PALETTE["text"])
    ax.set_ylim(0, 110)
    ax.set_title("SLA Compliance by Priority", fontsize=10, fontweight="bold", color=PALETTE["text"], pad=8)
    ax.set_ylabel("% Met SLA", fontsize=8)
    ax.tick_params(axis="x", labelsize=7.5)
    ax.legend(fontsize=7)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.set_facecolor("white")


def plot_agent_csat(ax, df):
    agent_stats = (
        df[df["satisfaction_score"].notna()]
        .groupby("assigned_agent")["satisfaction_score"]
        .mean()
        .sort_values(ascending=True)
    )
    colors = [PALETTE["green"] if v >= 4 else PALETTE["accent"] if v >= 3 else PALETTE["red"]
              for v in agent_stats.values]
    bars = ax.barh(agent_stats.index, agent_stats.values, color=colors, edgecolor="white")
    ax.axvline(4.0, color=PALETTE["text"], linestyle="--", linewidth=1, label="4.0 target")
    for bar, val in zip(bars, agent_stats.values):
        ax.text(val + 0.02, bar.get_y() + bar.get_height() / 2,
                f"{val:.2f}", va="center", fontsize=7.5, color=PALETTE["text"])
    ax.set_xlim(0, 5.4)
    ax.set_title("Avg CSAT Score by Agent", fontsize=10, fontweight="bold", color=PALETTE["text"], pad=8)
    ax.set_xlabel("Avg Satisfaction (1–5)", fontsize=8)
    ax.legend(fontsize=7)
    ax.grid(axis="x", linestyle="--", alpha=0.4)
    ax.set_facecolor("white")
    ax.tick_params(labelsize=8)


def plot_hourly_heatmap(ax, df):
    hourly = df.groupby("hour").size().reindex(range(24), fill_value=0)
    colors = [PALETTE["red"] if h in range(9, 12) or h in range(13, 16) else
              PALETTE["accent"] if h in range(8, 18) else PALETTE["mid_grey"]
              for h in range(24)]
    ax.bar(range(24), hourly.values, color=colors, edgecolor="white", width=0.8)
    ax.set_xticks(range(0, 24, 2))
    ax.set_xticklabels([f"{h:02d}:00" for h in range(0, 24, 2)], rotation=45, ha="right", fontsize=7)
    ax.set_title("Submission Volume by Hour of Day", fontsize=10, fontweight="bold", color=PALETTE["text"], pad=8)
    ax.set_ylabel("Tickets", fontsize=8)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.set_facecolor("white")

    handles = [
        mpatches.Patch(color=PALETTE["red"], label="Peak hours"),
        mpatches.Patch(color=PALETTE["accent"], label="Business hours"),
        mpatches.Patch(color=PALETTE["mid_grey"], label="Off-hours"),
    ]
    ax.legend(handles=handles, fontsize=7)


def plot_priority_pie(ax, df):
    counts = df["priority"].value_counts().reindex(PRIORITY_ORDER, fill_value=0)
    wedges, texts, autotexts = ax.pie(
        counts.values,
        labels=PRIORITY_ORDER,
        colors=PRIORITY_COLORS,
        autopct="%1.1f%%",
        startangle=140,
        pctdistance=0.78,
        wedgeprops={"edgecolor": "white", "linewidth": 1.5},
    )
    for t in texts:
        t.set_fontsize(7.5)
    for at in autotexts:
        at.set_fontsize(7.5)
        at.set_color("white")
        at.set_fontweight("bold")
    ax.set_title("Priority Distribution", fontsize=10, fontweight="bold", color=PALETTE["text"], pad=8)


def build_dashboard(df):
    Path("output").mkdir(exist_ok=True)

    total = len(df)
    resolved = df[df["status"].isin(["Resolved", "Closed"])]
    resolution_rate = 100 * len(resolved) / total
    mttr = df["resolution_hours"].mean()
    sla_denom = df["met_sla"].notna().sum()
    sla_pct = 100 * df["met_sla"].sum() / sla_denom if sla_denom > 0 else 0
    csat = df["satisfaction_score"].mean()
    open_count = df[df["status"].isin(["Open", "In Progress", "Pending User"])].shape[0]

    fig = plt.figure(figsize=(18, 13), facecolor=PALETTE["light_bg"])
    fig.suptitle(
        "IT Help Desk Analytics Dashboard",
        fontsize=18, fontweight="bold", color=PALETTE["primary"], y=0.97
    )
    fig.text(0.99, 0.97, "2023–2024  |  Synthetic Dataset", ha="right",
             fontsize=8, color=PALETTE["mid_grey"], style="italic")

    gs = gridspec.GridSpec(
        4, 6,
        figure=fig,
        hspace=0.52,
        wspace=0.45,
        left=0.05, right=0.97,
        top=0.92, bottom=0.05,
    )

    # Row 0 — KPI tiles (6 across)
    kpis = [
        (total,           "Total Tickets",        PALETTE["primary"], "{:,.0f}"),
        (resolution_rate, "Resolution Rate",      PALETTE["green"],   "{:.1f}%"),
        (mttr,            "Avg Resolution (hrs)", PALETTE["accent"],  "{:.1f}"),
        (sla_pct,         "SLA Compliance",       PALETTE["primary"], "{:.1f}%"),
        (csat,            "Avg CSAT Score",        PALETTE["green"],   "{:.2f}"),
        (open_count,      "Open / Backlog",        PALETTE["red"],     "{:,.0f}"),
    ]
    for col, (val, label, color, fmt) in enumerate(kpis):
        ax = fig.add_subplot(gs[0, col])
        kpi_tile(ax, val, label, color, fmt)

    # Row 1 — Monthly trend (span 4) + priority pie (span 2)
    ax_trend = fig.add_subplot(gs[1, :4])
    plot_monthly_trend(ax_trend, df)

    ax_pie = fig.add_subplot(gs[1, 4:])
    plot_priority_pie(ax_pie, df)

    # Row 2 — Category bar (span 3) + SLA by priority (span 3)
    ax_cat = fig.add_subplot(gs[2, :3])
    plot_category_bar(ax_cat, df)

    ax_sla = fig.add_subplot(gs[2, 3:])
    plot_sla_by_priority(ax_sla, df)

    # Row 3 — Hourly (span 4) + Agent CSAT (span 2)
    ax_hour = fig.add_subplot(gs[3, :4])
    plot_hourly_heatmap(ax_hour, df)

    ax_agent = fig.add_subplot(gs[3, 4:])
    plot_agent_csat(ax_agent, df)

    out = "output/dashboard.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"Dashboard saved → {out}")


if __name__ == "__main__":
    df = load_data()
    build_dashboard(df)
