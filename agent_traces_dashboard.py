import marimo

__generated_with = "0.23.13"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import altair as alt
    import dlt
    import pandas as pd

    return alt, dlt, mo, pd


@app.cell
def _(dlt):
    # dataset_name must match what rest_api_pipeline.py writes ("agent_traces_raw").
    # destination + dataset_name are passed explicitly because the runtime
    # requires it for notebooks — dlt.attach() alone won't resolve there.
    pipeline = dlt.attach(
        "agent_traces", destination="playground", dataset_name="agent_traces_raw"
    )
    dataset = pipeline.dataset()
    return (dataset,)


@app.cell
def _(mo):
    # Theme-aware palette. Both light and dark steps pass the dataviz validator;
    # light aqua+yellow fall under 3:1 vs the surface, so this dashboard ships
    # direct labels + a table view as the required relief.
    try:
        THEME = mo.app_meta().theme
    except Exception:
        THEME = "light"

    _DARK = THEME == "dark"
    SERIES = (
        ["#3987e5", "#d95926", "#199e70", "#c98500"]
        if _DARK
        else ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
    )
    INK = "#ffffff" if _DARK else "#0b0b0b"
    SURFACE = "#1a1a19" if _DARK else "#fcfcfb"

    # List price, USD per million tokens. Sonnet 5 also has promotional pricing
    # of $2/$10 through 2026-08-31; standard list is used here so the numbers
    # don't silently shift when the promo lapses.
    PRICE = {
        "claude-fable-5": (10.00, 50.00),
        "claude-haiku-4-5-20251001": (1.00, 5.00),
        "claude-opus-4-8": (5.00, 25.00),
        "claude-sonnet-5": (3.00, 15.00),
    }
    # Fixed alphabetical model->slot binding: a chart sorted by cost must never
    # repaint a model. Color follows the entity, never its rank.
    MODELS = sorted(PRICE)
    LABEL = {
        "claude-fable-5": "Fable 5",
        "claude-haiku-4-5-20251001": "Haiku 4.5",
        "claude-opus-4-8": "Opus 4.8",
        "claude-sonnet-5": "Sonnet 5",
    }
    MODEL_LABELS = [LABEL[m] for m in MODELS]
    return INK, LABEL, MODEL_LABELS, PRICE, SERIES, SURFACE


@app.cell
def _(mo):
    mo.md("""
    # Agent traces — 20k logged turns

    Loaded from the Claude Code Agent Logs API (`/logs`) by the `agent_traces` dlt pipeline.
    Cost is **derived** from list price — the API reports token counts only — so it goes
    stale if rates change. Unlike local transcripts, this feed has **no cache-token fields**,
    so there is no cache-efficiency view here.
    """)
    return


@app.cell
def _(LABEL, PRICE, dataset):
    df_model = dataset(
        """
        select message__model as model,
               count(*)                        as turns,
               sum(usage__input_tokens)        as input_tokens,
               sum(usage__output_tokens)       as output_tokens
        from logs
        where type = 'assistant'
        group by 1
        """
    ).df()
    df_model["cost"] = [
        r.input_tokens / 1e6 * PRICE[r.model][0]
        + r.output_tokens / 1e6 * PRICE[r.model][1]
        for r in df_model.itertuples()
    ]
    df_model["label"] = df_model.model.map(LABEL)
    df_model["turn_share"] = 100 * df_model.turns / df_model.turns.sum()
    df_model["cost_share"] = 100 * df_model.cost / df_model.cost.sum()
    return (df_model,)


@app.cell
def _(dataset):
    df_scope = dataset(
        """
        select count(*)                          as rows_loaded,
               count(distinct session_id)        as sessions,
               count(distinct cwd)               as projects,
               min(timestamp)                    as first_seen,
               max(timestamp)                    as last_seen
        from logs
        """
    ).df()
    return (df_scope,)


@app.cell
def _(df_model, df_scope, mo):
    _s = df_scope.iloc[0]
    _cost = df_model.cost.sum()
    _tokens = df_model.input_tokens.sum() + df_model.output_tokens.sum()
    _hours = (_s.last_seen - _s.first_seen).total_seconds() / 3600

    mo.hstack(
        [
            mo.stat(f"${_cost:,.0f}", label="Estimated cost", caption="list price"),
            mo.stat(f"{int(_s.rows_loaded):,}", label="Rows loaded"),
            mo.stat(f"{_tokens/1e6:,.0f}M", label="Total tokens"),
            mo.stat(f"{int(_s.sessions):,}", label="Sessions"),
            mo.stat(f"${_cost/_s.sessions:,.2f}", label="Cost per session"),
            mo.stat(f"{_hours:,.0f}h", label="Time span"),
        ],
        justify="start",
        gap=2,
    )
    return


@app.cell
def _(mo):
    mo.md("""
    ## Work is spread evenly. Spend is not.

    Every model handles roughly a quarter of the turns, but the bill splits 5% to 54%.
    Same amount of work, ~10× the price.
    """)
    return


@app.cell
def _(INK, MODEL_LABELS, SERIES, alt, df_model, pd):
    _long = pd.concat(
        [
            df_model[["label", "turn_share"]]
            .rename(columns={"turn_share": "pct"})
            .assign(metric="Share of turns"),
            df_model[["label", "cost_share"]]
            .rename(columns={"cost_share": "pct"})
            .assign(metric="Share of cost"),
        ]
    )
    _metrics = ["Share of turns", "Share of cost"]

    _bars = (
        alt.Chart(_long)
        .mark_bar(cornerRadiusEnd=4, height=16)
        .encode(
            y=alt.Y("label:N", title=None, sort=MODEL_LABELS),
            x=alt.X("pct:Q", title="Percent of total (%)"),
            yOffset=alt.YOffset("metric:N", sort=_metrics),
            # Here color encodes the METRIC, not the model — models are positional.
            color=alt.Color(
                "metric:N",
                title=None,
                scale=alt.Scale(domain=_metrics, range=SERIES[:2]),
                sort=_metrics,
            ),
            tooltip=[
                alt.Tooltip("label:N", title="Model"),
                alt.Tooltip("metric:N", title="Metric"),
                alt.Tooltip("pct:Q", title="Percent", format=".1f"),
            ],
        )
    )
    _labels = _bars.mark_text(align="left", dx=5, color=INK, fontSize=10).encode(
        text=alt.Text("pct:Q", format=".1f")
    )
    _chart = (_bars + _labels).properties(
        title="Share of work vs share of spend, by model", height=260
    )
    _chart
    return


@app.cell
def _(INK, MODEL_LABELS, SERIES, alt, df_model):
    _bars = (
        alt.Chart(df_model)
        .mark_bar(cornerRadiusEnd=4, height=20)
        .encode(
            y=alt.Y("label:N", title=None, sort="-x"),
            x=alt.X("cost:Q", title="Cost (USD)"),
            color=alt.Color(
                "label:N",
                scale=alt.Scale(domain=MODEL_LABELS, range=SERIES),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("label:N", title="Model"),
                alt.Tooltip("cost:Q", title="Cost (USD)", format="$,.2f"),
                alt.Tooltip("turns:Q", title="Turns", format=","),
                alt.Tooltip("input_tokens:Q", title="Input tokens", format=","),
                alt.Tooltip("output_tokens:Q", title="Output tokens", format=","),
            ],
        )
    )
    _labels = _bars.mark_text(align="left", dx=6, color=INK).encode(
        text=alt.Text("cost:Q", format="$,.0f")
    )
    _chart = (_bars + _labels).properties(title="Total cost by model", height=160)
    _chart
    return


@app.cell
def _(mo):
    mo.md("""
    **Table view** — the same numbers, no color required.
    """)
    return


@app.cell
def _(df_model, mo):
    mo.ui.table(
        df_model[
            ["label", "turns", "input_tokens", "output_tokens", "cost"]
        ].sort_values("cost", ascending=False).round({"cost": 2}),
        selection=None,
    )
    return


@app.cell
def _(mo):
    mo.md("""
    ## How spend accumulates
    """)
    return


@app.cell
def _(LABEL, PRICE, dataset):
    df_time = dataset(
        """
        select date_trunc('hour', timestamp) as bucket,
               message__model                as model,
               sum(usage__input_tokens)      as input_tokens,
               sum(usage__output_tokens)     as output_tokens
        from logs
        where type = 'assistant'
        group by 1, 2
        order by 1
        """
    ).df()
    df_time["cost"] = [
        r.input_tokens / 1e6 * PRICE[r.model][0]
        + r.output_tokens / 1e6 * PRICE[r.model][1]
        for r in df_time.itertuples()
    ]
    df_time["label"] = df_time.model.map(LABEL)
    return (df_time,)


@app.cell
def _(MODEL_LABELS, SERIES, SURFACE, alt, df_time):
    _chart = (
        alt.Chart(df_time)
        .mark_bar(stroke=SURFACE, strokeWidth=2, cornerRadiusEnd=4)
        .encode(
            x=alt.X("bucket:T", title="Hour"),
            y=alt.Y("cost:Q", title="Cost (USD)", stack=True),
            color=alt.Color(
                "label:N",
                title=None,
                scale=alt.Scale(domain=MODEL_LABELS, range=SERIES),
                sort=MODEL_LABELS,
            ),
            order=alt.Order("label:N", sort="ascending"),
            tooltip=[
                alt.Tooltip("bucket:T", title="Hour"),
                alt.Tooltip("label:N", title="Model"),
                alt.Tooltip("cost:Q", title="Cost (USD)", format="$,.2f"),
            ],
        )
        .properties(title="Hourly cost by model", height=300)
    )
    _chart
    return


@app.cell
def _(mo):
    mo.md("""
    ## Fleet behaviour
    """)
    return


@app.cell
def _(dataset):
    df_tools = dataset(
        """
        select name, count(*) as calls
        from logs__message__content
        where type = 'tool_use' and name is not null
        group by 1
        order by 2 desc
        """
    ).df()
    return (df_tools,)


@app.cell
def _(INK, SERIES, alt, df_tools):
    _bars = (
        alt.Chart(df_tools)
        .mark_bar(color=SERIES[0], cornerRadiusEnd=4, height=18)
        .encode(
            y=alt.Y("name:N", title=None, sort="-x"),
            x=alt.X("calls:Q", title="Calls"),
            tooltip=[
                alt.Tooltip("name:N", title="Tool"),
                alt.Tooltip("calls:Q", title="Calls", format=","),
            ],
        )
    )
    _labels = _bars.mark_text(align="left", dx=6, color=INK).encode(text="calls:Q")
    _chart = (_bars + _labels).properties(title="Tool calls by tool", height=240)
    _chart
    return


@app.cell
def _(dataset):
    df_projects = dataset(
        """
        select cwd                       as project,
               count(*)                  as records,
               count(distinct session_id) as sessions
        from logs
        group by 1
        order by 2 desc
        """
    ).df()
    return (df_projects,)


@app.cell
def _(INK, SERIES, alt, df_projects):
    _bars = (
        alt.Chart(df_projects)
        .mark_bar(color=SERIES[0], cornerRadiusEnd=4, height=18)
        .encode(
            y=alt.Y("project:N", title=None, sort="-x"),
            x=alt.X("records:Q", title="Log records"),
            tooltip=[
                alt.Tooltip("project:N", title="Project"),
                alt.Tooltip("records:Q", title="Records", format=","),
                alt.Tooltip("sessions:Q", title="Sessions", format=","),
            ],
        )
    )
    _labels = _bars.mark_text(align="left", dx=6, color=INK).encode(
        text=alt.Text("records:Q", format=",")
    )
    _chart = (_bars + _labels).properties(title="Traffic by project", height=180)
    _chart
    return


@app.cell
def _(dataset):
    df_sessions = dataset(
        """
        select session_id, count(*) as turns
        from logs
        group by 1
        """
    ).df()
    return (df_sessions,)


@app.cell
def _(SERIES, alt, df_sessions):
    _chart = (
        alt.Chart(df_sessions)
        .mark_bar(color=SERIES[0], cornerRadiusEnd=4)
        .encode(
            x=alt.X("turns:Q", bin=alt.Bin(maxbins=25), title="Records per session"),
            y=alt.Y("count():Q", title="Sessions"),
            tooltip=[
                alt.Tooltip("turns:Q", bin=alt.Bin(maxbins=25), title="Records"),
                alt.Tooltip("count():Q", title="Sessions"),
            ],
        )
        .properties(title="Session length distribution", height=260)
    )
    _chart
    return


if __name__ == "__main__":
    app.run()
