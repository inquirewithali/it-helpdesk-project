"""
IT Help Desk Analytics Dashboard — Streamlit App
Run: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import io

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Help Desk Analytics",
    page_icon="🖥️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Theme / CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* overall background */
    .stApp { background-color: #0f1117; }
    section[data-testid="stSidebar"] { background-color: #161b22; }

    /* KPI cards */
    .kpi-card {
        background: linear-gradient(135deg, #1e2530 0%, #232d3f 100%);
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 18px 20px 14px;
        text-align: center;
        min-height: 110px;
    }
    .kpi-value { font-size: 2rem; font-weight: 700; margin: 4px 0 2px; }
    .kpi-label { font-size: 0.78rem; color: #8b949e; text-transform: uppercase; letter-spacing: .06em; }
    .kpi-delta { font-size: 0.78rem; margin-top: 4px; }
    .delta-up   { color: #3fb950; }
    .delta-down { color: #f85149; }
    .delta-neut { color: #8b949e; }

    /* insight cards */
    .insight-card {
        background: #161b22;
        border-left: 4px solid #388bfd;
        border-radius: 6px;
        padding: 10px 14px;
        margin-bottom: 8px;
        font-size: 0.875rem;
        color: #c9d1d9;
        line-height: 1.5;
    }
    .insight-warn { border-left-color: #f0883e; }
    .insight-good { border-left-color: #3fb950; }
    .insight-bad  { border-left-color: #f85149; }

    /* hide streamlit chrome */
    #MainMenu, footer, header { visibility: hidden; }
    .block-container { padding-top: 1.2rem; }

    /* table styling */
    .dataframe thead { background-color: #21262d !important; }
</style>
""", unsafe_allow_html=True)

PRIORITY_ORDER   = ["P1 - Critical", "P2 - High", "P3 - Medium", "P4 - Low"]
PRIORITY_COLORS  = {"P1 - Critical": "#f85149", "P2 - High": "#f0883e",
                    "P3 - Medium": "#d29922", "P4 - Low": "#3fb950"}
STATUS_COLORS    = {"Resolved": "#3fb950", "Closed": "#388bfd",
                    "Open": "#f85149", "In Progress": "#f0883e", "Pending User": "#d29922"}
SLA_TARGETS      = {"P1 - Critical": 4, "P2 - High": 24, "P3 - Medium": 72, "P4 - Low": 168}
PLOTLY_THEME     = "plotly_dark"
CHART_BG         = "rgba(0,0,0,0)"
GRID_COLOR       = "rgba(255,255,255,0.06)"


# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    df = pd.read_csv("data/tickets.csv")
    df["created_at"]  = pd.to_datetime(df["created_at"])
    df["resolved_at"] = pd.to_datetime(df["resolved_at"], errors="coerce")
    df["resolution_hours"]   = pd.to_numeric(df["resolution_hours"],   errors="coerce")
    df["satisfaction_score"] = pd.to_numeric(df["satisfaction_score"], errors="coerce")
    df["met_sla"] = df["met_sla"].astype(str).map({"True": True, "False": False})
    df["month"]   = df["created_at"].dt.to_period("M").astype(str)
    df["week"]    = df["created_at"].dt.to_period("W").astype(str)
    df["weekday"] = df["created_at"].dt.day_name()
    df["hour"]    = df["created_at"].dt.hour
    df["date"]    = df["created_at"].dt.date
    return df


def apply_filters(df, date_range, priorities, categories, departments, agents, statuses, search):
    mask = (
        (df["created_at"].dt.date >= date_range[0]) &
        (df["created_at"].dt.date <= date_range[1])
    )
    if priorities:
        mask &= df["priority"].isin(priorities)
    if categories:
        mask &= df["category"].isin(categories)
    if departments:
        mask &= df["department"].isin(departments)
    if agents:
        mask &= df["assigned_agent"].isin(agents)
    if statuses:
        mask &= df["status"].isin(statuses)
    filtered = df[mask]
    if search.strip():
        q = search.strip().lower()
        filtered = filtered[
            filtered["ticket_id"].str.lower().str.contains(q) |
            filtered["subject"].str.lower().str.contains(q) |
            filtered["department"].str.lower().str.contains(q) |
            filtered["assigned_agent"].str.lower().str.contains(q) |
            filtered["category"].str.lower().str.contains(q)
        ]
    return filtered


def prior_period(df, date_range):
    span = (date_range[1] - date_range[0]).days + 1
    p_end   = date_range[0] - timedelta(days=1)
    p_start = p_end - timedelta(days=span - 1)
    return df[(df["created_at"].dt.date >= p_start) & (df["created_at"].dt.date <= p_end)]


def delta_html(curr, prev, higher_is_better=True, fmt=".1f", suffix=""):
    if prev == 0 or pd.isna(prev):
        return f'<span class="delta-neut">— no prior data</span>'
    pct = (curr - prev) / abs(prev) * 100
    arrow = "▲" if pct > 0 else "▼"
    cls = ("delta-up" if pct > 0 else "delta-down") if higher_is_better else \
          ("delta-down" if pct > 0 else "delta-up")
    return f'<span class="{cls}">{arrow} {abs(pct):.1f}% vs prior period</span>'


def kpi(col, value_str, label, delta_html_str="", color="#c9d1d9"):
    col.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value" style="color:{color}">{value_str}</div>
        <div class="kpi-delta">{delta_html_str}</div>
    </div>""", unsafe_allow_html=True)


# ── Insight engine ────────────────────────────────────────────────────────────
def generate_insights(df, prev_df):
    insights = []

    resolved = df[df["status"].isin(["Resolved", "Closed"])]
    sla_pct = 100 * df["met_sla"].sum() / df["met_sla"].notna().sum() if df["met_sla"].notna().sum() > 0 else 0

    # SLA health
    if sla_pct < 80:
        insights.append(("bad",  f"⚠️ SLA compliance is <b>{sla_pct:.1f}%</b> — below the 80% minimum threshold. Investigate P2/P3 backlog immediately."))
    elif sla_pct < 90:
        insights.append(("warn", f"SLA compliance is <b>{sla_pct:.1f}%</b> — approaching the 90% target. Monitor P2 ticket queue."))
    else:
        insights.append(("good", f"SLA compliance is healthy at <b>{sla_pct:.1f}%</b>."))

    # Worst category by avg resolution
    if len(resolved) > 0:
        cat_mttr = resolved.groupby("category")["resolution_hours"].mean()
        worst_cat = cat_mttr.idxmax()
        insights.append(("warn", f"<b>{worst_cat}</b> tickets take the longest to resolve on average ({cat_mttr[worst_cat]:.1f} hrs). Consider dedicated triage."))

    # Low CSAT agent
    if df["satisfaction_score"].notna().sum() > 10:
        agent_csat = df.groupby("assigned_agent")["satisfaction_score"].mean()
        low_agent = agent_csat.idxmin()
        if agent_csat[low_agent] < 3.5:
            insights.append(("bad", f"<b>{low_agent}</b> has the lowest CSAT score ({agent_csat[low_agent]:.2f}/5). Review recent tickets and consider coaching."))

    # Backlog spike
    open_count = df[df["status"].isin(["Open", "In Progress", "Pending User"])].shape[0]
    if len(df) > 0:
        open_pct = 100 * open_count / len(df)
        if open_pct > 12:
            insights.append(("bad", f"Open backlog is <b>{open_pct:.1f}%</b> of total tickets ({open_count} open). Capacity may be insufficient."))

    # Volume trend vs prior period
    if len(prev_df) > 0:
        vol_change = (len(df) - len(prev_df)) / len(prev_df) * 100
        if vol_change > 15:
            insights.append(("warn", f"Ticket volume is up <b>{vol_change:.1f}%</b> vs the prior period — may signal a systemic issue."))
        elif vol_change < -15:
            insights.append(("good", f"Ticket volume is down <b>{abs(vol_change):.1f}%</b> vs the prior period — positive trend."))

    # Monday pattern
    if "weekday" in df.columns:
        dow = df.groupby("weekday").size()
        if "Monday" in dow and dow.get("Monday", 0) > 0:
            avg_other = dow.drop("Monday", errors="ignore").mean()
            if dow["Monday"] > avg_other * 1.3:
                insights.append(("warn", f"Monday receives <b>{dow['Monday']}</b> tickets on average — {((dow['Monday']/avg_other-1)*100):.0f}% above the weekly mean. Consider staggered on-call coverage."))

    return insights[:5]  # cap at 5


# ── Chart helpers ─────────────────────────────────────────────────────────────
def fig_defaults(fig, height=320):
    fig.update_layout(
        template=PLOTLY_THEME,
        paper_bgcolor=CHART_BG,
        plot_bgcolor=CHART_BG,
        margin=dict(l=10, r=10, t=36, b=10),
        height=height,
        font=dict(family="Inter, sans-serif", size=11, color="#c9d1d9"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                    bgcolor="rgba(0,0,0,0)", font=dict(size=10)),
    )
    fig.update_xaxes(gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR)
    fig.update_yaxes(gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR)
    return fig


def chart_volume_trend(df):
    monthly = df.groupby("month").size().reset_index(name="tickets")
    rolling = monthly["tickets"].rolling(3, center=True, min_periods=1).mean().round(1)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=monthly["month"], y=monthly["tickets"],
        fill="tozeroy", fillcolor="rgba(56,139,253,0.12)",
        line=dict(color="#388bfd", width=2),
        name="Monthly volume", mode="lines+markers",
        marker=dict(size=4),
    ))
    fig.add_trace(go.Scatter(
        x=monthly["month"], y=rolling,
        line=dict(color="#f0883e", width=1.8, dash="dot"),
        name="3-mo avg", mode="lines",
    ))
    fig.update_layout(title="Monthly Ticket Volume")
    return fig_defaults(fig)


def chart_priority_donut(df):
    counts = df["priority"].value_counts().reindex(PRIORITY_ORDER, fill_value=0)
    fig = go.Figure(go.Pie(
        labels=counts.index,
        values=counts.values,
        hole=0.55,
        marker=dict(colors=[PRIORITY_COLORS[p] for p in counts.index],
                    line=dict(color="#0f1117", width=2)),
        textinfo="percent",
        textfont=dict(size=11),
    ))
    fig.update_layout(title="Priority Split", showlegend=True)
    return fig_defaults(fig, height=300)


def chart_sla_by_priority(df):
    resolved = df[df["met_sla"].notna()]
    sla = resolved.groupby("priority")["met_sla"].apply(
        lambda x: round(100 * x.sum() / len(x), 1)
    ).reindex(PRIORITY_ORDER, fill_value=0).reset_index()
    sla.columns = ["priority", "sla_pct"]
    sla["color"] = sla["sla_pct"].apply(lambda v: "#3fb950" if v >= 90 else "#f0883e" if v >= 75 else "#f85149")
    fig = go.Figure(go.Bar(
        x=sla["priority"], y=sla["sla_pct"],
        marker_color=sla["color"],
        text=sla["sla_pct"].apply(lambda v: f"{v:.1f}%"),
        textposition="outside", textfont=dict(size=11),
    ))
    fig.add_hline(y=90, line_dash="dot", line_color="#8b949e",
                  annotation_text="90% target", annotation_position="top right")
    fig.update_yaxes(range=[0, 115])
    fig.update_layout(title="SLA Compliance by Priority")
    return fig_defaults(fig)


def chart_category_bar(df):
    cat = df["category"].value_counts().reset_index()
    cat.columns = ["category", "count"]
    fig = px.bar(cat, x="count", y="category", orientation="h",
                 color="count", color_continuous_scale=["#1e2530", "#388bfd"],
                 labels={"count": "Tickets", "category": ""})
    fig.update_layout(title="Tickets by Category", coloraxis_showscale=False)
    fig.update_traces(texttemplate="%{x}", textposition="outside")
    return fig_defaults(fig)


def chart_agent_performance(df):
    resolved = df[df["status"].isin(["Resolved", "Closed"])]
    agg = resolved.groupby("assigned_agent").agg(
        tickets=("ticket_id", "count"),
        avg_hrs=("resolution_hours", "mean"),
        avg_csat=("satisfaction_score", "mean"),
    ).reset_index()
    sla_agg = df[df["met_sla"].notna()].groupby("assigned_agent")["met_sla"].apply(
        lambda x: round(100 * x.sum() / len(x), 1)
    ).reset_index()
    sla_agg.columns = ["assigned_agent", "sla_pct"]
    agg = agg.merge(sla_agg, on="assigned_agent", how="left")
    agg = agg.sort_values("avg_csat", ascending=True)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=agg["assigned_agent"], x=agg["avg_csat"],
        orientation="h",
        marker_color=[
            "#3fb950" if v >= 4.0 else "#f0883e" if v >= 3.5 else "#f85149"
            for v in agg["avg_csat"]
        ],
        text=agg["avg_csat"].round(2),
        textposition="outside",
        name="CSAT",
    ))
    fig.add_vline(x=4.0, line_dash="dot", line_color="#8b949e",
                  annotation_text="4.0 target")
    fig.update_xaxes(range=[0, 5.6])
    fig.update_layout(title="Agent CSAT Score")
    return fig_defaults(fig, height=300)


def chart_hourly(df):
    hourly = df.groupby("hour").size().reset_index(name="tickets")
    hourly["label"] = hourly["hour"].apply(lambda h: f"{h:02d}:00")
    hourly["color"] = hourly["hour"].apply(
        lambda h: "#f85149" if 9 <= h <= 11 or 13 <= h <= 15 else
                  "#388bfd" if 7 <= h <= 18 else "#30363d"
    )
    fig = go.Figure(go.Bar(
        x=hourly["label"], y=hourly["tickets"],
        marker_color=hourly["color"],
    ))
    fig.update_layout(title="Submission Volume by Hour of Day")
    return fig_defaults(fig)


def chart_heatmap_dow(df):
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    dow = df.groupby(["weekday", "hour"]).size().reset_index(name="tickets")
    pivot = dow.pivot(index="weekday", columns="hour", values="tickets").fillna(0)
    pivot = pivot.reindex([d for d in order if d in pivot.index])
    fig = go.Figure(go.Heatmap(
        z=pivot.values,
        x=[f"{h:02d}:00" for h in pivot.columns],
        y=pivot.index.tolist(),
        colorscale="Blues",
        hoverongaps=False,
        showscale=False,
    ))
    fig.update_layout(title="Ticket Heatmap — Day × Hour")
    return fig_defaults(fig, height=260)


def chart_status_donut(df):
    counts = df["status"].value_counts()
    fig = go.Figure(go.Pie(
        labels=counts.index,
        values=counts.values,
        hole=0.55,
        marker=dict(colors=[STATUS_COLORS.get(s, "#8b949e") for s in counts.index],
                    line=dict(color="#0f1117", width=2)),
        textinfo="percent",
    ))
    fig.update_layout(title="Status Breakdown", showlegend=True)
    return fig_defaults(fig, height=280)


def chart_resolution_box(df):
    resolved = df[df["resolution_hours"].notna()].copy()
    fig = px.box(
        resolved, x="priority", y="resolution_hours",
        color="priority",
        color_discrete_map=PRIORITY_COLORS,
        category_orders={"priority": PRIORITY_ORDER},
        labels={"resolution_hours": "Hours", "priority": ""},
        points=False,
    )
    # add SLA target lines
    for p, target in SLA_TARGETS.items():
        fig.add_shape(type="line", x0=-0.5, x1=3.5, y0=target, y1=target,
                      line=dict(dash="dot", color="#8b949e", width=1))
    fig.update_layout(title="Resolution Time Distribution by Priority", showlegend=False)
    return fig_defaults(fig)


# ── Main app ──────────────────────────────────────────────────────────────────
def main():
    df_raw = load_data()

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("## 🖥️ Help Desk Analytics")
        st.markdown("---")

        st.markdown("### Search")
        search = st.text_input("", placeholder="Ticket ID, subject, agent…", label_visibility="collapsed")

        st.markdown("### Date Range")
        min_date = df_raw["created_at"].dt.date.min()
        max_date = df_raw["created_at"].dt.date.max()
        date_range = st.date_input(
            "", value=(min_date, max_date),
            min_value=min_date, max_value=max_date,
            label_visibility="collapsed",
        )
        if isinstance(date_range, tuple) and len(date_range) == 2:
            d_start, d_end = date_range
        else:
            d_start, d_end = min_date, max_date

        st.markdown("### Priority")
        priorities = st.multiselect("", PRIORITY_ORDER, default=[], label_visibility="collapsed",
                                    placeholder="All priorities")

        st.markdown("### Category")
        all_cats = sorted(df_raw["category"].unique())
        categories = st.multiselect("", all_cats, default=[], label_visibility="collapsed",
                                    placeholder="All categories")

        st.markdown("### Department")
        all_depts = sorted(df_raw["department"].unique())
        departments = st.multiselect("", all_depts, default=[], label_visibility="collapsed",
                                     placeholder="All departments")

        st.markdown("### Agent")
        all_agents = sorted(df_raw["assigned_agent"].unique())
        agents = st.multiselect("", all_agents, default=[], label_visibility="collapsed",
                                placeholder="All agents")

        st.markdown("### Status")
        all_statuses = sorted(df_raw["status"].unique())
        statuses = st.multiselect("", all_statuses, default=[], label_visibility="collapsed",
                                  placeholder="All statuses")

        st.markdown("---")
        if st.button("Reset Filters", use_container_width=True):
            st.rerun()

    # Apply filters
    df = apply_filters(df_raw, (d_start, d_end), priorities, categories, departments, agents, statuses, search)
    df_prev = prior_period(df_raw, (d_start, d_end))

    if len(df) == 0:
        st.warning("No tickets match the current filters.")
        return

    # Compute KPIs
    total          = len(df)
    prev_total     = len(df_prev)
    resolved_df    = df[df["status"].isin(["Resolved", "Closed"])]
    prev_resolved  = df_prev[df_prev["status"].isin(["Resolved", "Closed"])]
    res_rate       = 100 * len(resolved_df) / total if total > 0 else 0
    prev_res_rate  = 100 * len(prev_resolved) / len(df_prev) if len(df_prev) > 0 else 0
    mttr           = df["resolution_hours"].mean()
    prev_mttr      = df_prev["resolution_hours"].mean()
    sla_d          = df["met_sla"].notna().sum()
    sla_pct        = 100 * df["met_sla"].sum() / sla_d if sla_d > 0 else 0
    prev_sla_d     = df_prev["met_sla"].notna().sum()
    prev_sla_pct   = 100 * df_prev["met_sla"].sum() / prev_sla_d if prev_sla_d > 0 else 0
    csat           = df["satisfaction_score"].mean()
    prev_csat      = df_prev["satisfaction_score"].mean()
    open_count     = df[df["status"].isin(["Open", "In Progress", "Pending User"])].shape[0]
    prev_open      = df_prev[df_prev["status"].isin(["Open", "In Progress", "Pending User"])].shape[0]
    p1_count       = df[df["priority"] == "P1 - Critical"].shape[0]

    # ── Header ────────────────────────────────────────────────────────────────
    h1, h2 = st.columns([4, 1])
    with h1:
        st.markdown("## IT Help Desk Analytics Dashboard")
        st.caption(f"Showing **{total:,}** tickets · {d_start} → {d_end}")
    with h2:
        csv_bytes = df.drop(columns=["month","week","weekday","hour","date"], errors="ignore").to_csv(index=False).encode()
        st.download_button("⬇ Export CSV", csv_bytes, "filtered_tickets.csv", "text/csv", use_container_width=True)

    st.markdown("---")

    # ── KPI row ───────────────────────────────────────────────────────────────
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    kpi(k1, f"{total:,}",        "Total Tickets",
        delta_html(total, prev_total, higher_is_better=False, fmt=".0f"), "#388bfd")
    kpi(k2, f"{res_rate:.1f}%",  "Resolution Rate",
        delta_html(res_rate, prev_res_rate), "#3fb950")
    kpi(k3, f"{mttr:.1f} hrs",   "Avg MTTR",
        delta_html(mttr, prev_mttr, higher_is_better=False), "#f0883e")
    kpi(k4, f"{sla_pct:.1f}%",   "SLA Compliance",
        delta_html(sla_pct, prev_sla_pct), "#3fb950" if sla_pct >= 90 else "#f0883e")
    kpi(k5, f"{csat:.2f} / 5",   "Avg CSAT",
        delta_html(csat, prev_csat), "#3fb950" if csat >= 4.0 else "#f0883e")
    kpi(k6, f"{open_count}",     "Open / Backlog",
        delta_html(open_count, prev_open, higher_is_better=False), "#f85149" if open_count > 50 else "#c9d1d9")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab_overview, tab_agents, tab_trends, tab_tickets, tab_insights = st.tabs([
        "📊 Overview", "👤 Agent Performance", "📈 Trends", "🎫 Ticket Explorer", "💡 Insights"
    ])

    # ── TAB: Overview ─────────────────────────────────────────────────────────
    with tab_overview:
        r1c1, r1c2 = st.columns([2, 1])
        with r1c1:
            st.plotly_chart(chart_volume_trend(df), use_container_width=True, config={"displayModeBar": False})
        with r1c2:
            st.plotly_chart(chart_priority_donut(df), use_container_width=True, config={"displayModeBar": False})

        r2c1, r2c2, r2c3 = st.columns(3)
        with r2c1:
            st.plotly_chart(chart_sla_by_priority(df), use_container_width=True, config={"displayModeBar": False})
        with r2c2:
            st.plotly_chart(chart_category_bar(df), use_container_width=True, config={"displayModeBar": False})
        with r2c3:
            st.plotly_chart(chart_status_donut(df), use_container_width=True, config={"displayModeBar": False})

        st.plotly_chart(chart_resolution_box(df), use_container_width=True, config={"displayModeBar": False})

    # ── TAB: Agent Performance ────────────────────────────────────────────────
    with tab_agents:
        resolved = df[df["status"].isin(["Resolved", "Closed"])]
        agent_agg = resolved.groupby("assigned_agent").agg(
            tickets_handled=("ticket_id", "count"),
            avg_resolution_hrs=("resolution_hours", lambda x: round(x.mean(), 1)),
            avg_csat=("satisfaction_score", lambda x: round(x.mean(), 2)),
        ).reset_index()
        sla_by_agent = df[df["met_sla"].notna()].groupby("assigned_agent")["met_sla"].apply(
            lambda x: round(100 * x.sum() / len(x), 1)
        ).reset_index()
        sla_by_agent.columns = ["assigned_agent", "sla_compliance_pct"]
        agent_agg = agent_agg.merge(sla_by_agent, on="assigned_agent", how="left")
        p1_by_agent = df[df["priority"] == "P1 - Critical"].groupby("assigned_agent").size().reset_index(name="p1_tickets")
        agent_agg = agent_agg.merge(p1_by_agent, on="assigned_agent", how="left").fillna({"p1_tickets": 0})
        agent_agg["p1_tickets"] = agent_agg["p1_tickets"].astype(int)
        agent_agg = agent_agg.sort_values("avg_csat", ascending=False)

        ac1, ac2 = st.columns([1, 1])
        with ac1:
            st.plotly_chart(chart_agent_performance(df), use_container_width=True, config={"displayModeBar": False})
        with ac2:
            # Scatter: MTTR vs CSAT
            fig_scatter = px.scatter(
                agent_agg, x="avg_resolution_hrs", y="avg_csat",
                size="tickets_handled", color="sla_compliance_pct",
                hover_name="assigned_agent",
                color_continuous_scale="RdYlGn",
                labels={"avg_resolution_hrs": "Avg Resolution (hrs)", "avg_csat": "Avg CSAT", "sla_compliance_pct": "SLA %"},
                title="MTTR vs CSAT by Agent",
                size_max=40,
            )
            fig_scatter = fig_defaults(fig_scatter, height=300)
            st.plotly_chart(fig_scatter, use_container_width=True, config={"displayModeBar": False})

        st.markdown("#### Agent Leaderboard")
        display_df = agent_agg.rename(columns={
            "assigned_agent": "Agent", "tickets_handled": "Tickets Handled",
            "avg_resolution_hrs": "Avg Resolution (hrs)", "avg_csat": "Avg CSAT",
            "sla_compliance_pct": "SLA Compliance %", "p1_tickets": "P1 Tickets",
        })

        def style_csat(v):
            if isinstance(v, float):
                if v >= 4.0: return "color: #3fb950; font-weight:600"
                if v >= 3.5: return "color: #f0883e"
                return "color: #f85149; font-weight:600"
            return ""

        def style_sla(v):
            if isinstance(v, float):
                if v >= 90: return "color: #3fb950; font-weight:600"
                if v >= 75: return "color: #f0883e"
                return "color: #f85149; font-weight:600"
            return ""

        st.dataframe(
            display_df.style
                .applymap(style_csat, subset=["Avg CSAT"])
                .applymap(style_sla, subset=["SLA Compliance %"])
                .format({"Avg CSAT": "{:.2f}", "Avg Resolution (hrs)": "{:.1f}", "SLA Compliance %": "{:.1f}%"}),
            use_container_width=True, hide_index=True,
        )

    # ── TAB: Trends ───────────────────────────────────────────────────────────
    with tab_trends:
        tc1, tc2 = st.columns(2)
        with tc1:
            st.plotly_chart(chart_hourly(df), use_container_width=True, config={"displayModeBar": False})
        with tc2:
            st.plotly_chart(chart_heatmap_dow(df), use_container_width=True, config={"displayModeBar": False})

        # Category trend over time
        cat_monthly = df.groupby(["month", "category"]).size().reset_index(name="tickets")
        fig_cat_trend = px.line(
            cat_monthly, x="month", y="tickets", color="category",
            title="Category Volume Over Time",
            labels={"month": "", "tickets": "Tickets", "category": "Category"},
        )
        fig_cat_trend = fig_defaults(fig_cat_trend, height=340)
        st.plotly_chart(fig_cat_trend, use_container_width=True, config={"displayModeBar": False})

        # Dept bar
        dept = df.groupby("department").agg(
            tickets=("ticket_id", "count"),
            avg_csat=("satisfaction_score", "mean"),
        ).reset_index().sort_values("tickets", ascending=False)
        fig_dept = px.bar(dept, x="department", y="tickets", color="avg_csat",
                          color_continuous_scale="RdYlGn", range_color=[1, 5],
                          title="Tickets by Department (color = CSAT)",
                          labels={"tickets": "Tickets", "department": "", "avg_csat": "CSAT"})
        fig_dept = fig_defaults(fig_dept, height=300)
        st.plotly_chart(fig_dept, use_container_width=True, config={"displayModeBar": False})

    # ── TAB: Ticket Explorer ──────────────────────────────────────────────────
    with tab_tickets:
        te1, te2, te3 = st.columns(3)
        with te1:
            sort_col = st.selectbox("Sort by", ["created_at", "resolution_hours", "satisfaction_score", "priority", "ticket_id"])
        with te2:
            sort_dir = st.radio("Order", ["Descending", "Ascending"], horizontal=True)
        with te3:
            show_n = st.selectbox("Show rows", [25, 50, 100, 250, 500], index=1)

        display_cols = ["ticket_id", "created_at", "priority", "category", "subject",
                        "department", "assigned_agent", "status", "resolution_hours", "satisfaction_score"]
        explore_df = df[display_cols].copy()
        explore_df = explore_df.sort_values(sort_col, ascending=(sort_dir == "Ascending")).head(show_n)
        explore_df["created_at"] = explore_df["created_at"].dt.strftime("%Y-%m-%d %H:%M")
        explore_df["resolution_hours"] = explore_df["resolution_hours"].apply(
            lambda x: f"{x:.1f}" if pd.notna(x) else "—"
        )
        explore_df["satisfaction_score"] = explore_df["satisfaction_score"].apply(
            lambda x: f"{'★' * int(x)}{'☆' * (5-int(x))}" if pd.notna(x) else "—"
        )
        explore_df.columns = [c.replace("_", " ").title() for c in explore_df.columns]

        st.dataframe(explore_df, use_container_width=True, hide_index=True, height=480)

        st.caption(f"Showing {len(explore_df)} of {total:,} filtered tickets")

    # ── TAB: Insights ─────────────────────────────────────────────────────────
    with tab_insights:
        st.markdown("#### Automated Insights")
        st.caption("Generated from the current filtered dataset. Use filters to drill into a specific segment.")

        insights = generate_insights(df, df_prev)
        for kind, text in insights:
            css_class = {"bad": "insight-bad", "warn": "insight-warn", "good": "insight-good"}.get(kind, "insight-card")
            st.markdown(f'<div class="insight-card {css_class}">{text}</div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### Recurring Issues (Top 10)")
        recurring = (
            df.groupby(["subject", "category"])
            .agg(count=("ticket_id", "count"), depts=("department", "nunique"))
            .reset_index()
            .sort_values("count", ascending=False)
            .head(10)
        )
        recurring.columns = ["Subject", "Category", "Occurrences", "Departments Affected"]
        st.dataframe(recurring, use_container_width=True, hide_index=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### Low CSAT Tickets (Rated 1–2)")
        low_csat = df[df["satisfaction_score"].isin([1, 2])][
            ["ticket_id", "created_at", "priority", "category", "subject", "assigned_agent", "resolution_hours"]
        ].copy()
        low_csat["created_at"] = low_csat["created_at"].dt.strftime("%Y-%m-%d")
        low_csat.columns = ["Ticket", "Date", "Priority", "Category", "Subject", "Agent", "Resolution Hrs"]
        low_csat["Resolution Hrs"] = low_csat["Resolution Hrs"].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "—")
        st.dataframe(low_csat.head(30), use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
