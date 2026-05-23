"""Streamlit dashboard for local Cloudflare AI Gateway analytics."""

from __future__ import annotations

import argparse
from datetime import timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from cf_aigw_analyzer.analytics import (
    AnalyticsFilters,
    build_context_buckets,
    build_insights,
    build_model_stats,
    build_recent_events,
    build_summary,
    build_timeseries,
    fetch_rows,
    list_gateway_scopes,
    open_readonly_database,
    resolve_gateway_id,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--db", required=True)
    parser.add_argument("--account-id")
    parser.add_argument("--gateway-id")
    parser.add_argument("--gateway-name")
    return parser.parse_known_args()[0]


def mask_id(value: str | None) -> str:
    if not value:
        return "-"
    text = str(value)
    if len(text) <= 10:
        return text
    return f"{text[:6]}...{text[-4:]}"


def fmt_int(value: Any) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{int(value):,}"


def fmt_float(value: Any, digits: int = 2, suffix: str = "") -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):,.{digits}f}{suffix}"


def fmt_pct(value: Any) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):.1%}"


@st.cache_data(ttl=30, show_spinner=False)
def load_scope_rows(db_path: str, account_id: str | None, gateway_id: str | None) -> list[dict[str, Any]]:
    with open_readonly_database(db_path) as conn:
        return fetch_rows(conn, AnalyticsFilters(account_id=account_id, gateway_id=gateway_id))


@st.cache_data(ttl=30, show_spinner=False)
def load_scopes(db_path: str) -> list[dict[str, Any]]:
    with open_readonly_database(db_path) as conn:
        return list_gateway_scopes(conn)


def pick_scope(scopes: list[dict[str, Any]], args: argparse.Namespace) -> dict[str, Any] | None:
    if not scopes:
        return None
    wanted_gateway = args.gateway_id
    if args.gateway_name and not wanted_gateway:
        with open_readonly_database(args.db) as conn:
            wanted_gateway = resolve_gateway_id(conn, args.account_id, args.gateway_name)
    for scope in scopes:
        if args.account_id and scope["account_id"] != args.account_id:
            continue
        if wanted_gateway and scope["gateway_id"] != wanted_gateway:
            continue
        return scope
    return scopes[0]


def apply_ui_filters(
    rows: list[dict[str, Any]],
    time_range: str,
    model: str,
    provider: str,
    success: str,
) -> list[dict[str, Any]]:
    if not rows:
        return []
    df = pd.DataFrame(rows)
    df["created_dt"] = pd.to_datetime(df["created_at"], errors="coerce", utc=True)
    last_seen = df["created_dt"].max()

    if pd.notna(last_seen) and time_range != "all":
        hours = {"7h": 7, "24h": 24, "7d": 7 * 24}[time_range]
        df = df[df["created_dt"] >= last_seen - timedelta(hours=hours)]
    if model != "__all__":
        df = df[df["model"].fillna("(unknown)") == model]
    if provider != "__all__":
        df = df[df["provider"].fillna("(unknown)") == provider]
    if success == "success":
        df = df[df["success"] == True]  # noqa: E712
    elif success == "failed":
        df = df[df["success"] == False]  # noqa: E712

    return df.drop(columns=["created_dt"]).to_dict("records")


def render_metric_grid(summary: dict[str, Any]) -> None:
    first = st.columns(5)
    first[0].metric("Requests", fmt_int(summary["requests"]))
    first[1].metric("Success", fmt_pct(summary["success_rate"]))
    first[2].metric("Total Tokens", fmt_int(summary["total_tokens"]))
    first[3].metric("Cache Ratio", fmt_pct(summary["cache_ratio"]))
    first[4].metric("Avg TPS", fmt_float(summary["avg_output_tps"]))

    second = st.columns(5)
    second[0].metric("Input Tokens", fmt_int(summary["input_tokens"]))
    second[1].metric("Output Tokens", fmt_int(summary["output_tokens"]))
    second[2].metric("Reasoning", fmt_int(summary["reasoning_tokens"]))
    second[3].metric("Avg Latency", fmt_float(summary["avg_total_ms"], 0, " ms"))
    second[4].metric("P95 Latency", fmt_float(summary["p95_total_ms"], 0, " ms"))


def render_charts(rows: list[dict[str, Any]]) -> None:
    timeseries = pd.DataFrame(build_timeseries(rows))
    if timeseries.empty:
        st.info("No time-series data.")
        return

    left, right = st.columns(2)
    with left:
        fig = px.bar(timeseries, x="hour", y="requests", title="Hourly Requests")
        fig.update_layout(height=320, margin=dict(l=20, r=20, t=50, b=20))
        st.plotly_chart(fig, width="stretch")
    with right:
        fig = px.line(timeseries, x="hour", y=["tpm", "rpm"], title="Throughput per Minute")
        fig.update_layout(height=320, margin=dict(l=20, r=20, t=50, b=20))
        st.plotly_chart(fig, width="stretch")

    left, right = st.columns(2)
    with left:
        fig = px.line(
            timeseries,
            x="hour",
            y=["avg_total_ms", "p95_total_ms", "p99_total_ms"],
            title="Latency by Hour",
        )
        fig.update_layout(height=320, margin=dict(l=20, r=20, t=50, b=20))
        st.plotly_chart(fig, width="stretch")
    with right:
        fig = px.line(
            timeseries,
            x="hour",
            y=["avg_output_tps", "avg_visible_output_tps"],
            title="Output TPS by Hour",
        )
        fig.update_layout(height=320, margin=dict(l=20, r=20, t=50, b=20))
        st.plotly_chart(fig, width="stretch")


def render_model_and_context(rows: list[dict[str, Any]]) -> None:
    model_stats = pd.DataFrame(build_model_stats(rows))
    context_stats = pd.DataFrame(build_context_buckets(rows))

    left, right = st.columns(2)
    with left:
        if not model_stats.empty:
            top_models = model_stats.head(12)
            fig = px.bar(
                top_models,
                x="model",
                y="requests",
                color="avg_output_tps",
                title="Model Requests and Avg TPS",
            )
            fig.update_layout(height=360, margin=dict(l=20, r=20, t=50, b=20))
            st.plotly_chart(fig, width="stretch")
    with right:
        if not context_stats.empty:
            fig = px.scatter(
                context_stats,
                x="avg_input_tokens",
                y="avg_output_tps",
                size="requests",
                color="context_bucket",
                hover_data=["avg_total_ms", "p95_total_ms", "cache_ratio"],
                title="Context Length vs TPS",
            )
            fig.update_layout(height=360, margin=dict(l=20, r=20, t=50, b=20))
            st.plotly_chart(fig, width="stretch")

    st.subheader("Model Comparison")
    if model_stats.empty:
        st.info("No model data.")
    else:
        columns = [
            "model",
            "provider",
            "requests",
            "success_rate",
            "total_tokens",
            "cache_ratio",
            "avg_total_ms",
            "p95_total_ms",
            "avg_output_tps",
            "avg_visible_output_tps",
        ]
        st.dataframe(model_stats[columns], width="stretch", hide_index=True)

    st.subheader("Context Buckets")
    if context_stats.empty:
        st.info("No context bucket data.")
    else:
        columns = [
            "context_bucket",
            "requests",
            "avg_input_tokens",
            "avg_output_tokens",
            "cache_ratio",
            "avg_total_ms",
            "p95_total_ms",
            "avg_output_tps",
        ]
        st.dataframe(context_stats[columns], width="stretch", hide_index=True)


def render_insights(rows: list[dict[str, Any]]) -> None:
    st.subheader("Data Insights")
    for insight in build_insights(rows):
        level = insight.get("level")
        body = f"**{insight['title']}**  \n{insight['detail']}"
        if level == "warning":
            st.warning(body)
        else:
            st.info(body)


def render_events(rows: list[dict[str, Any]]) -> None:
    st.subheader("Recent Events")
    events = pd.DataFrame(build_recent_events(rows, limit=500))
    if events.empty:
        st.info("No events.")
    else:
        st.dataframe(events, width="stretch", hide_index=True)


def main() -> None:
    args = parse_args()
    db_path = str(Path(args.db).expanduser().resolve())

    st.set_page_config(page_title="Cloudflare AI Gateway Analyzer", layout="wide")
    st.title("Cloudflare AI Gateway Analyzer")

    try:
        scopes = load_scopes(db_path)
    except Exception as exc:
        st.error(f"SQLite open failed: {exc}")
        return

    if not scopes:
        st.warning("No logs found in SQLite.")
        return

    default_scope = pick_scope(scopes, args)
    labels = [
        f"{scope['name']} / {scope['gateway_id']} · {mask_id(scope['account_id'])} · {scope['logs']:,} logs"
        for scope in scopes
    ]
    default_index = scopes.index(default_scope) if default_scope in scopes else 0
    with st.sidebar:
        st.header("Filters")
        st.caption(db_path)
        selected_label = st.selectbox("Gateway", labels, index=default_index)
        selected_scope = scopes[labels.index(selected_label)]
        time_range = st.radio("Time Range", ["all", "7h", "24h", "7d"], index=0, horizontal=True)

    rows = load_scope_rows(db_path, selected_scope["account_id"], selected_scope["gateway_id"])
    models = sorted({str(row.get("model") or "(unknown)") for row in rows})
    providers = sorted({str(row.get("provider") or "(unknown)") for row in rows})
    with st.sidebar:
        model = st.selectbox(
            "Model",
            ["__all__"] + models,
            format_func=lambda value: "All" if value == "__all__" else value,
        )
        provider = st.selectbox(
            "Provider",
            ["__all__"] + providers,
            format_func=lambda value: "All" if value == "__all__" else value,
        )
        success = st.selectbox("Result", ["all", "success", "failed"], format_func=str.title)

    filtered_rows = apply_ui_filters(rows, str(time_range), model, provider, success)
    summary = build_summary(filtered_rows)

    render_metric_grid(summary)
    render_insights(filtered_rows)
    render_charts(filtered_rows)
    render_model_and_context(filtered_rows)
    render_events(filtered_rows)


if __name__ == "__main__":
    main()
