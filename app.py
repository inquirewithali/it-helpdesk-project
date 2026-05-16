"""
IT Help Desk Analytics Dashboard
Run: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import timedelta

st.set_page_config(
    page_title="Help Desk Analytics",
    page_icon="🖥️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .stApp { background-color: #0f1117; }
    section[data-testid="stSidebar"] { background-color: #161b22; }

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

    footer { visibility: hidden; }
    .block-container { padding-top: 1.2rem; }

    .find-bar input {
        background: #1e2530 !important;
        border: 1px solid #30363d !important;
        border-radius: 8px !important;
        color: #c9d1d9 !important;
        font-size: 0.9rem !important;
    }
    .match-count {
        font-size: 0.78rem;
        color: #8b949e;
        margin-top: 4px;
    }
</style>
""", unsafe_allow_html=True)

PRIORITY_ORDER  = ["P1 - Critical", "P2 - High", "P3 - Medium", "P4 - Low"]
PRIORITY_COLORS = {"P1 - Critical": "#f85149", "P2 - High": "#f0883e",
                   "P3 - Medium":   "#d29922", "P4 - Low":  "#3fb950"}
STATUS_COLORS   = {"Resolved": "#3fb950", "Closed": "#388bfd",
                   "Open": "#f85149", "In Progress": "#f0883e", "Pending User": "#d29922"}
SLA_TARGETS     = {"P1 - Critical": 4, "P2 - High": 24, "P3 - Medium": 72, "P4 - Low": 168}
CHART_BG        = "rgba(0,0,0,0)"
GRID_COLOR      = "rgba(255,255,255,0.06)"
OPEN_STATUSES   = ["Open", "In Progress", "Pending User"]
CLOSED_STATUSES = ["Resolved", "Closed"]


@st.cache_data
def load_data():
    df = pd.read_csv("data/tickets.csv")
    df["created_at"]         = pd.to_datetime(df["created_at"])
    df["resolved_at"]        = pd.to_datetime(df["resolved_at"], errors="coerce")
    df["resolution_hours"]   = pd.to_numeric(df["resolution_hours"],   errors="coerce")
    df["satisfaction_score"] = pd.to_numeric(df["satisfaction_score"], errors="coerce")
    df["met_sla"]  = df["met_sla"].astype(str).map({"True": True, "False": False})
    df["month"]    = df["created_at"].dt.to_period("M").astype(str)
    df["weekday"]  = df["created_at"].dt.day_name()
    df["hour"]     = df["created_at"].dt.hour
    return df


def apply_filters(df, d_start, d_end, priorities, categories, departments, agents, statuses, search):
    mask = (df["created_at"].dt.date >= d_start) & (df["created_at"].dt.date <= d_end)
    if priorities:   mask &= df["priority"].isin(priorities)
    if categories:   mask &= df["category"].isin(categories)
    if departments:  mask &= df["department"].isin(departments)
    if agents:       mask &= df["assigned_agent"].isin(agents)
    if statuses:     mask &= df["status"].isin(statuses)
    out = df[mask]
    if search.strip():
        q = search.strip().lower()
        out = out[
            out["ticket_id"].str.lower().str.contains(q, na=False) |
            out["subject"].str.lower().str.contains(q, na=False) |
            out["department"].str.lower().str.contains(q, na=False) |
            out["assigned_agent"].str.lower().str.contains(q, na=False) |
            out["category"].str.lower().str.contains(q, na=False)
        ]
    return out


def get_prior(df, d_start, d_end):
    span    = (d_end - d_start).days + 1
    p_end   = d_start - timedelta(days=1)
    p_start = p_end   - timedelta(days=span - 1)
    return df[(df["created_at"].dt.date >= p_start) & (df["created_at"].dt.date <= p_end)]


def delta_html(curr, prev, higher_is_better=True):
    if prev == 0 or pd.isna(prev):
        return ""
    pct   = (curr - prev) / abs(prev) * 100
    arrow = "▲" if pct > 0 else "▼"
    good  = pct > 0 if higher_is_better else pct < 0
    cls   = "delta-up" if good else "delta-down"
    return f'<span class="{cls}">{arrow} {abs(pct):.1f}% vs prior period</span>'


def kpi_card(col, value, label, delta="", color="#c9d1d9"):
    col.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value" style="color:{color}">{value}</div>
        <div class="kpi-delta">{delta}</div>
    </div>""", unsafe_allow_html=True)


def fig_base(fig, height=320):
    fig.update_layout(
        template="plotly_dark",
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
    monthly  = df.groupby("month").size().reset_index(name="tickets")
    rolling  = monthly["tickets"].rolling(3, center=True, min_periods=1).mean().round(1)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=monthly["month"], y=monthly["tickets"],
        fill="tozeroy", fillcolor="rgba(56,139,253,0.12)",
        line=dict(color="#388bfd", width=2),
        name="Monthly volume", mode="lines+markers", marker=dict(size=4),
    ))
    fig.add_trace(go.Scatter(
        x=monthly["month"], y=rolling,
        line=dict(color="#f0883e", width=1.8, dash="dot"),
        name="3-mo avg", mode="lines",
    ))
    fig.update_layout(title="Monthly Ticket Volume")
    return fig_base(fig)


def chart_priority_donut(df):
    counts = df["priority"].value_counts().reindex(PRIORITY_ORDER, fill_value=0)
    pct    = (counts / counts.sum() * 100).round(1)
    labels = [f"{p}  {pct[p]}%" for p in counts.index]
    fig = go.Figure(go.Pie(
        labels=labels, values=counts.values, hole=0.58,
        marker=dict(colors=[PRIORITY_COLORS[p] for p in counts.index],
                    line=dict(color="#0f1117", width=2)),
        textinfo="none",
        hovertemplate="<b>%{label}</b><br>Tickets: %{value}<extra></extra>",
        domain=dict(y=[0.15, 1.0]),
    ))
    fig = fig_base(fig, height=300)
    fig.update_layout(
        title=dict(text="Priority Split", y=0.97, x=0.5, xanchor="center"),
        margin=dict(l=10, r=10, t=36, b=10),
        legend=dict(
            orientation="h", x=0.5, xanchor="center",
            y=0.08, yanchor="top",
            font=dict(size=9), bgcolor="rgba(0,0,0,0)",
        ),
    )
    return fig


def chart_sla_by_priority(df):
    resolved = df[df["met_sla"].notna()]
    sla = (
        resolved.groupby("priority")["met_sla"]
        .apply(lambda x: round(100 * x.sum() / len(x), 1))
        .reindex(PRIORITY_ORDER, fill_value=0)
        .reset_index()
    )
    sla.columns = ["priority", "sla_pct"]
    sla["color"] = sla["sla_pct"].apply(
        lambda v: "#3fb950" if v >= 90 else "#f0883e" if v >= 75 else "#f85149"
    )
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
    return fig_base(fig)


def chart_category_bar(df):
    cat = df["category"].value_counts().reset_index()
    cat.columns = ["category", "count"]
    fig = px.bar(cat, x="count", y="category", orientation="h",
                 color="count", color_continuous_scale=["#1e2530", "#388bfd"],
                 labels={"count": "Tickets", "category": ""})
    fig.update_layout(title="Tickets by Category", coloraxis_showscale=False)
    fig.update_traces(texttemplate="%{x}", textposition="outside")
    return fig_base(fig)


def chart_status_donut(df):
    counts = df["status"].value_counts()
    fig = go.Figure(go.Pie(
        labels=counts.index, values=counts.values, hole=0.55,
        marker=dict(colors=[STATUS_COLORS.get(s, "#8b949e") for s in counts.index],
                    line=dict(color="#0f1117", width=2)),
        textinfo="percent",
        domain=dict(y=[0.15, 1.0]),
    ))
    fig = fig_base(fig, height=300)
    fig.update_layout(
        title=dict(text="Status Breakdown", y=0.97, x=0.5, xanchor="center"),
        margin=dict(l=10, r=10, t=36, b=10),
        legend=dict(
            orientation="h", x=0.5, xanchor="center",
            y=0.08, yanchor="top",
            font=dict(size=9), bgcolor="rgba(0,0,0,0)",
        ),
    )
    return fig


def chart_resolution_box(df):
    resolved = df[df["resolution_hours"].notna()].copy()
    fig = px.box(
        resolved, x="priority", y="resolution_hours",
        color="priority", color_discrete_map=PRIORITY_COLORS,
        category_orders={"priority": PRIORITY_ORDER},
        labels={"resolution_hours": "Hours", "priority": ""}, points=False,
    )
    for p, target in SLA_TARGETS.items():
        fig.add_shape(type="line", x0=-0.5, x1=3.5, y0=target, y1=target,
                      line=dict(dash="dot", color="#8b949e", width=1))
    fig.update_layout(title="Resolution Time Distribution by Priority", showlegend=False)
    return fig_base(fig)


def chart_agent_csat(df):
    resolved = df[df["status"].isin(CLOSED_STATUSES)]
    agg = resolved.groupby("assigned_agent")["satisfaction_score"].mean().sort_values()
    fig = go.Figure(go.Bar(
        y=agg.index, x=agg.values, orientation="h",
        marker_color=["#3fb950" if v >= 4.0 else "#f0883e" if v >= 3.5 else "#f85149"
                      for v in agg.values],
        text=agg.round(2).values, textposition="outside",
    ))
    fig.add_vline(x=4.0, line_dash="dot", line_color="#8b949e", annotation_text="4.0 target")
    fig.update_xaxes(range=[0, 5.6])
    fig.update_layout(title="Agent CSAT Score")
    return fig_base(fig, height=300)


def chart_hourly(df):
    hourly = df.groupby("hour").size().reset_index(name="tickets")
    hourly["label"] = hourly["hour"].apply(lambda h: f"{h:02d}:00")
    hourly["color"] = hourly["hour"].apply(
        lambda h: "#f85149" if (9 <= h <= 11 or 13 <= h <= 15)
        else "#388bfd" if 7 <= h <= 18 else "#30363d"
    )
    fig = go.Figure(go.Bar(x=hourly["label"], y=hourly["tickets"], marker_color=hourly["color"]))
    fig.update_layout(title="Submission Volume by Hour of Day")
    return fig_base(fig)


def chart_heatmap(df):
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    dow   = df.groupby(["weekday", "hour"]).size().reset_index(name="tickets")
    pivot = dow.pivot(index="weekday", columns="hour", values="tickets").fillna(0)
    pivot = pivot.reindex([d for d in order if d in pivot.index])
    fig = go.Figure(go.Heatmap(
        z=pivot.values,
        x=[f"{h:02d}:00" for h in pivot.columns],
        y=pivot.index.tolist(),
        colorscale="Blues", hoverongaps=False, showscale=False,
    ))
    fig.update_layout(title="Ticket Heatmap — Day × Hour")
    return fig_base(fig, height=260)


def generate_insights(df, prev_df):
    insights = []
    resolved = df[df["status"].isin(CLOSED_STATUSES)]

    sla_denom = df["met_sla"].notna().sum()
    sla_pct   = 100 * df["met_sla"].sum() / sla_denom if sla_denom > 0 else 0

    if sla_pct < 80:
        insights.append(("bad",  f"⚠️ SLA compliance is <b>{sla_pct:.1f}%</b> — below the 80% minimum. Investigate P2/P3 backlog immediately."))
    elif sla_pct < 90:
        insights.append(("warn", f"SLA compliance is <b>{sla_pct:.1f}%</b> — approaching the 90% target. Monitor the P2 queue."))
    else:
        insights.append(("good", f"SLA compliance is healthy at <b>{sla_pct:.1f}%</b>."))

    if len(resolved) > 0:
        cat_mttr  = resolved.groupby("category")["resolution_hours"].mean()
        worst_cat = cat_mttr.idxmax()
        insights.append(("warn", f"<b>{worst_cat}</b> tickets take the longest to resolve ({cat_mttr[worst_cat]:.1f} hrs avg). Consider dedicated triage."))

    if df["satisfaction_score"].notna().sum() > 10:
        agent_csat = df.groupby("assigned_agent")["satisfaction_score"].mean()
        low_agent  = agent_csat.idxmin()
        if agent_csat[low_agent] < 3.5:
            insights.append(("bad", f"<b>{low_agent}</b> has the lowest CSAT ({agent_csat[low_agent]:.2f}/5). Review recent tickets and consider coaching."))

    open_count = df[df["status"].isin(OPEN_STATUSES)].shape[0]
    if len(df) > 0:
        open_pct = 100 * open_count / len(df)
        if open_pct > 12:
            insights.append(("bad", f"Open backlog is <b>{open_pct:.1f}%</b> of total tickets ({open_count} open). Capacity may be insufficient."))

    if len(prev_df) > 0:
        vol_change = (len(df) - len(prev_df)) / len(prev_df) * 100
        if vol_change > 15:
            insights.append(("warn", f"Ticket volume is up <b>{vol_change:.1f}%</b> vs the prior period — may signal a systemic issue."))
        elif vol_change < -15:
            insights.append(("good", f"Ticket volume is down <b>{abs(vol_change):.1f}%</b> vs the prior period."))

    return insights[:5]


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
        date_input = st.date_input("", value=(min_date, max_date),
                                   min_value=min_date, max_value=max_date,
                                   label_visibility="collapsed")
        d_start, d_end = (date_input if isinstance(date_input, tuple) and len(date_input) == 2
                          else (min_date, max_date))

        st.markdown("### Priority")
        priorities = st.multiselect("", PRIORITY_ORDER, default=[],
                                    label_visibility="collapsed", placeholder="All priorities")

        st.markdown("### Category")
        categories = st.multiselect("", sorted(df_raw["category"].unique()), default=[],
                                    label_visibility="collapsed", placeholder="All categories")

        st.markdown("### Department")
        departments = st.multiselect("", sorted(df_raw["department"].unique()), default=[],
                                     label_visibility="collapsed", placeholder="All departments")

        st.markdown("### Agent")
        agents = st.multiselect("", sorted(df_raw["assigned_agent"].unique()), default=[],
                                label_visibility="collapsed", placeholder="All agents")

        st.markdown("### Status")
        statuses = st.multiselect("", sorted(df_raw["status"].unique()), default=[],
                                  label_visibility="collapsed", placeholder="All statuses")

        st.markdown("---")
        if st.button("Reset Filters", use_container_width=True):
            st.rerun()

        st.markdown("### Export")
        export_placeholder = st.empty()

    df      = apply_filters(df_raw, d_start, d_end, priorities, categories, departments,
                            agents, statuses, search)
    df_prev = get_prior(df_raw, d_start, d_end)

    if len(df) == 0:
        st.warning("No tickets match the current filters.")
        return

    # ── KPIs ─────────────────────────────────────────────────────────────────
    total         = len(df)
    prev_total    = len(df_prev)
    resolved_df   = df[df["status"].isin(CLOSED_STATUSES)]
    prev_resolved = df_prev[df_prev["status"].isin(CLOSED_STATUSES)]
    res_rate      = 100 * len(resolved_df) / total
    prev_res_rate = 100 * len(prev_resolved) / len(df_prev) if len(df_prev) > 0 else 0
    mttr          = df["resolution_hours"].mean()
    prev_mttr     = df_prev["resolution_hours"].mean()
    sla_d         = df["met_sla"].notna().sum()
    sla_pct       = 100 * df["met_sla"].sum() / sla_d if sla_d > 0 else 0
    prev_sla_d    = df_prev["met_sla"].notna().sum()
    prev_sla_pct  = 100 * df_prev["met_sla"].sum() / prev_sla_d if prev_sla_d > 0 else 0
    csat          = df["satisfaction_score"].mean()
    prev_csat     = df_prev["satisfaction_score"].mean()
    open_count    = df[df["status"].isin(OPEN_STATUSES)].shape[0]
    prev_open     = df_prev[df_prev["status"].isin(OPEN_STATUSES)].shape[0]

    # ── Sidebar export (needs filtered df, so rendered here) ──────────────────
    csv_bytes = df.drop(columns=["month", "weekday", "hour"], errors="ignore") \
                  .to_csv(index=False).encode()
    export_placeholder.download_button(
        "⬇ Export Filtered CSV", csv_bytes, "filtered_tickets.csv",
        "text/csv", use_container_width=True,
    )

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown("## IT Help Desk Analytics Dashboard")
    st.caption(f"Showing **{total:,}** tickets · {d_start} → {d_end}")
    st.markdown("---")

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    kpi_card(k1, f"{total:,}",       "Total Tickets",
             delta_html(total, prev_total, higher_is_better=False), "#388bfd")
    kpi_card(k2, f"{res_rate:.1f}%", "Resolution Rate",
             delta_html(res_rate, prev_res_rate), "#3fb950")
    kpi_card(k3, f"{mttr:.1f} hrs",  "Avg MTTR",
             delta_html(mttr, prev_mttr, higher_is_better=False), "#f0883e")
    kpi_card(k4, f"{sla_pct:.1f}%",  "SLA Compliance",
             delta_html(sla_pct, prev_sla_pct), "#3fb950" if sla_pct >= 90 else "#f0883e")
    kpi_card(k5, f"{csat:.2f} / 5",  "Avg CSAT",
             delta_html(csat, prev_csat), "#3fb950" if csat >= 4.0 else "#f0883e")
    kpi_card(k6, f"{open_count}",    "Open / Backlog",
             delta_html(open_count, prev_open, higher_is_better=False),
             "#f85149" if open_count > 50 else "#c9d1d9")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Overview", "👤 Agent Performance", "📈 Trends", "🎫 Ticket Explorer", "💡 Insights"
    ])

    # Overview ─────────────────────────────────────────────────────────────────
    with tab1:
        c1, c2 = st.columns([2, 1])
        with c1:
            st.plotly_chart(chart_volume_trend(df), use_container_width=True,
                            config={"displayModeBar": False})
        with c2:
            st.plotly_chart(chart_priority_donut(df), use_container_width=True,
                            config={"displayModeBar": False})

        c3, c4, c5 = st.columns(3)
        with c3:
            st.plotly_chart(chart_sla_by_priority(df), use_container_width=True,
                            config={"displayModeBar": False})
        with c4:
            st.plotly_chart(chart_category_bar(df), use_container_width=True,
                            config={"displayModeBar": False})
        with c5:
            st.plotly_chart(chart_status_donut(df), use_container_width=True,
                            config={"displayModeBar": False})

        st.plotly_chart(chart_resolution_box(df), use_container_width=True,
                        config={"displayModeBar": False})

    # Agent Performance ────────────────────────────────────────────────────────
    with tab2:
        resolved = df[df["status"].isin(CLOSED_STATUSES)]
        agent_agg = resolved.groupby("assigned_agent").agg(
            tickets_handled   =("ticket_id",         "count"),
            avg_resolution_hrs=("resolution_hours",  lambda x: round(x.mean(), 1)),
            avg_csat          =("satisfaction_score", lambda x: round(x.mean(), 2)),
        ).reset_index()

        sla_by_agent = (
            df[df["met_sla"].notna()]
            .groupby("assigned_agent")["met_sla"]
            .apply(lambda x: round(100 * x.sum() / len(x), 1))
            .reset_index()
        )
        sla_by_agent.columns = ["assigned_agent", "sla_compliance_pct"]
        agent_agg = agent_agg.merge(sla_by_agent, on="assigned_agent", how="left")

        p1_by_agent = (
            df[df["priority"] == "P1 - Critical"]
            .groupby("assigned_agent").size()
            .reset_index(name="p1_tickets")
        )
        agent_agg = agent_agg.merge(p1_by_agent, on="assigned_agent", how="left") \
                              .fillna({"p1_tickets": 0})
        agent_agg["p1_tickets"] = agent_agg["p1_tickets"].astype(int)
        agent_agg = agent_agg.sort_values("avg_csat", ascending=False)

        ac1, ac2 = st.columns(2)
        with ac1:
            st.plotly_chart(chart_agent_csat(df), use_container_width=True,
                            config={"displayModeBar": False})
        with ac2:
            fig_scatter = px.scatter(
                agent_agg, x="avg_resolution_hrs", y="avg_csat",
                size="tickets_handled", color="sla_compliance_pct",
                hover_name="assigned_agent",
                color_continuous_scale="RdYlGn",
                labels={"avg_resolution_hrs": "Avg Resolution (hrs)",
                        "avg_csat": "Avg CSAT", "sla_compliance_pct": "SLA %"},
                title="MTTR vs CSAT by Agent", size_max=40,
            )
            st.plotly_chart(fig_base(fig_scatter, height=300), use_container_width=True,
                            config={"displayModeBar": False})

        st.markdown("#### Agent Leaderboard")
        display_df = agent_agg.rename(columns={
            "assigned_agent":    "Agent",
            "tickets_handled":   "Tickets Handled",
            "avg_resolution_hrs":"Avg Resolution (hrs)",
            "avg_csat":          "Avg CSAT",
            "sla_compliance_pct":"SLA Compliance %",
            "p1_tickets":        "P1 Tickets",
        })

        def style_csat(v):
            if not isinstance(v, float): return ""
            if v >= 4.0: return "color: #3fb950; font-weight:600"
            if v >= 3.5: return "color: #f0883e"
            return "color: #f85149; font-weight:600"

        def style_sla(v):
            if not isinstance(v, float): return ""
            if v >= 90: return "color: #3fb950; font-weight:600"
            if v >= 75: return "color: #f0883e"
            return "color: #f85149; font-weight:600"

        st.dataframe(
            display_df.style
                .map(style_csat, subset=["Avg CSAT"])
                .map(style_sla,  subset=["SLA Compliance %"])
                .format({"Avg CSAT": "{:.2f}",
                         "Avg Resolution (hrs)": "{:.1f}",
                         "SLA Compliance %": "{:.1f}%"}),
            use_container_width=True, hide_index=True,
        )

    # Trends ───────────────────────────────────────────────────────────────────
    with tab3:
        tc1, tc2 = st.columns(2)
        with tc1:
            st.plotly_chart(chart_hourly(df), use_container_width=True,
                            config={"displayModeBar": False})
        with tc2:
            st.plotly_chart(chart_heatmap(df), use_container_width=True,
                            config={"displayModeBar": False})

        cat_monthly = df.groupby(["month", "category"]).size().reset_index(name="tickets")
        fig_cat = px.line(cat_monthly, x="month", y="tickets", color="category",
                          title="Category Volume Over Time",
                          labels={"month": "", "tickets": "Tickets", "category": "Category"})
        st.plotly_chart(fig_base(fig_cat, height=340), use_container_width=True,
                        config={"displayModeBar": False})

        dept = df.groupby("department").agg(
            tickets  =("ticket_id", "count"),
            avg_csat =("satisfaction_score", "mean"),
        ).reset_index().sort_values("tickets", ascending=False)
        fig_dept = px.bar(dept, x="department", y="tickets", color="avg_csat",
                          color_continuous_scale="RdYlGn", range_color=[1, 5],
                          title="Tickets by Department (color = Avg CSAT)",
                          labels={"tickets": "Tickets", "department": "", "avg_csat": "CSAT"})
        st.plotly_chart(fig_base(fig_dept, height=300), use_container_width=True,
                        config={"displayModeBar": False})

    # Ticket Explorer ──────────────────────────────────────────────────────────
    with tab4:
        fa, fb, fc, fd = st.columns([2, 1, 1, 1])
        with fa:
            find_query = st.text_input("🔍 Find on page",
                                       placeholder="Search ticket ID, subject, agent, category…")
        with fb:
            sort_col = st.selectbox("Sort by", ["created_at", "resolution_hours",
                                                "satisfaction_score", "priority", "ticket_id"])
        with fc:
            sort_dir = st.radio("Order", ["Descending", "Ascending"], horizontal=True)
        with fd:
            show_n = st.selectbox("Show rows", [25, 50, 100, 250, 500], index=1)

        cols = ["ticket_id", "created_at", "priority", "category", "subject",
                "department", "assigned_agent", "status", "resolution_hours", "satisfaction_score"]
        explore = df[cols].copy().sort_values(sort_col, ascending=(sort_dir == "Ascending"))

        if find_query.strip():
            q = find_query.strip().lower()
            explore = explore[
                explore["ticket_id"].str.lower().str.contains(q, na=False) |
                explore["subject"].str.lower().str.contains(q, na=False) |
                explore["assigned_agent"].str.lower().str.contains(q, na=False) |
                explore["category"].str.lower().str.contains(q, na=False) |
                explore["department"].str.lower().str.contains(q, na=False) |
                explore["status"].str.lower().str.contains(q, na=False) |
                explore["priority"].str.lower().str.contains(q, na=False)
            ]

        matched = len(explore)
        explore = explore.head(show_n)
        explore["created_at"]         = explore["created_at"].dt.strftime("%Y-%m-%d %H:%M")
        explore["resolution_hours"]   = explore["resolution_hours"].apply(
            lambda x: f"{x:.1f} hrs" if pd.notna(x) else "—")
        explore["satisfaction_score"] = explore["satisfaction_score"].apply(
            lambda x: f"{'★' * int(x)}{'☆' * (5 - int(x))}" if pd.notna(x) else "—")
        explore.columns = [c.replace("_", " ").title() for c in explore.columns]

        st.dataframe(explore, use_container_width=True, hide_index=True, height=480)

        if find_query.strip():
            st.caption(f"Found **{matched:,}** matching tickets · showing {len(explore)}")
        else:
            st.caption(f"Showing {len(explore)} of {total:,} filtered tickets")

    # Insights ─────────────────────────────────────────────────────────────────
    with tab5:
        st.markdown("#### Automated Insights")
        st.caption("Generated from the current filtered dataset.")

        for kind, text in generate_insights(df, df_prev):
            css = {"bad": "insight-bad", "warn": "insight-warn", "good": "insight-good"}.get(kind, "")
            st.markdown(f'<div class="insight-card {css}">{text}</div>', unsafe_allow_html=True)

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
            ["ticket_id", "created_at", "priority", "category",
             "subject", "assigned_agent", "resolution_hours"]
        ].copy()
        low_csat["created_at"]       = low_csat["created_at"].dt.strftime("%Y-%m-%d")
        low_csat["resolution_hours"] = low_csat["resolution_hours"].apply(
            lambda x: f"{x:.1f}" if pd.notna(x) else "—")
        low_csat.columns = ["Ticket", "Date", "Priority", "Category", "Subject", "Agent", "Resolution Hrs"]
        st.dataframe(low_csat.head(30), use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
