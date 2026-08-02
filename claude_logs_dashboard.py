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
    pipeline = dlt.attach("claude_logs")
    dataset = pipeline.dataset()
    return (dataset,)


@app.cell
def _(mo):
    # Theme-aware palette. Both light and dark steps are validated with the
    # dataviz validator (all checks PASS; light aqua+yellow fall under 3:1 vs
    # the surface, so this dashboard ships direct labels + a table view).
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
    INK_MUTED = "#898781"
    SURFACE = "#1a1a19" if _DARK else "#fcfcfb"

    # Opus 5 list price, USD per million tokens.
    PRICE = {
        "Input": 5.00,
        "Output": 25.00,
        "Cache write 1h": 10.00,
        "Cache write 5m": 6.25,
        "Cache read": 0.50,
    }
    KINDS = ["Input", "Output", "Cache write", "Cache read"]
    return INK, KINDS, PRICE, SERIES, SURFACE


@app.cell
def _(mo):
    mo.md("""
    # Claude Code usage

    Session transcripts from `~/.claude/projects`, loaded by the `claude_logs` dlt
    pipeline. Cost is **derived** from Opus 5 list price — it is not recorded in the
    logs, so it goes stale if rates change.
    """)
    return


@app.cell
def _(dataset):
    df_totals = dataset(
        """
        select
            count(*)                                                  as turns,
            count(distinct session_id)                                as sessions,
            min(timestamp)                                            as first_seen,
            max(timestamp)                                            as last_seen,
            sum(message__usage__input_tokens)                         as input_tokens,
            sum(message__usage__output_tokens)                        as output_tokens,
            sum(message__usage__cache_creation__ephemeral_1h_input_tokens) as cw_1h,
            sum(message__usage__cache_creation__ephemeral_5m_input_tokens) as cw_5m,
            sum(message__usage__cache_read_input_tokens)              as cache_read_tokens
        from session_events
        where type = 'assistant'
        """
    ).df()
    return (df_totals,)


@app.cell
def _(PRICE, df_totals, mo):
    _t = df_totals.iloc[0]
    _cost = (
        _t.input_tokens / 1e6 * PRICE["Input"]
        + _t.output_tokens / 1e6 * PRICE["Output"]
        + _t.cw_1h / 1e6 * PRICE["Cache write 1h"]
        + _t.cw_5m / 1e6 * PRICE["Cache write 5m"]
        + _t.cache_read_tokens / 1e6 * PRICE["Cache read"]
    )
    _all_tokens = (
        _t.input_tokens
        + _t.output_tokens
        + _t.cw_1h
        + _t.cw_5m
        + _t.cache_read_tokens
    )
    _cache_share = 100.0 * _t.cache_read_tokens / _all_tokens

    mo.hstack(
        [
            mo.stat(f"${_cost:,.2f}", label="Estimated cost", caption="Opus 5 list price"),
            mo.stat(f"{_all_tokens/1e6:,.2f}M", label="Total tokens"),
            mo.stat(f"{_cache_share:.0f}%", label="Served from cache"),
            mo.stat(f"{int(_t.turns):,}", label="Assistant turns"),
            mo.stat(f"{int(_t.sessions):,}", label="Sessions"),
        ],
        justify="start",
        gap=2,
    )
    return


@app.cell
def _(mo):
    mo.md("""
    ## Where the money goes

    Cache reads outnumber output tokens roughly 70:1 but cost a fiftieth as much per
    token. Charting **cost** puts both on one honest axis; charting raw tokens would
    make output invisible.
    """)
    return


@app.cell
def _(dataset):
    df_chart1 = dataset(
        """
        select to_timestamp(floor(epoch(timestamp) / 300) * 300) as bucket,
               sum(message__usage__input_tokens)  / 1e6 * 5.00  as "Input",
               sum(message__usage__output_tokens) / 1e6 * 25.00 as "Output",
               sum(message__usage__cache_creation__ephemeral_1h_input_tokens) / 1e6 * 10.00
                 + sum(message__usage__cache_creation__ephemeral_5m_input_tokens) / 1e6 * 6.25
                                                                 as "Cache write",
               sum(message__usage__cache_read_input_tokens) / 1e6 * 0.50 as "Cache read"
        from session_events
        where type = 'assistant'
        group by 1
        order by 1
        """
    ).df()
    return (df_chart1,)


@app.cell
def _(KINDS, SERIES, SURFACE, alt, df_chart1):
    _long = df_chart1.melt(
        id_vars="bucket", value_vars=KINDS, var_name="kind", value_name="cost"
    )
    _long = _long[_long.cost > 0]

    _chart = (
        alt.Chart(_long)
        .mark_bar(stroke=SURFACE, strokeWidth=2, cornerRadiusEnd=4)
        .encode(
            x=alt.X("bucket:T", title="5-minute bucket"),
            y=alt.Y("cost:Q", title="Cost (USD)", stack=True),
            color=alt.Color(
                "kind:N",
                title=None,
                scale=alt.Scale(domain=KINDS, range=SERIES),
                sort=KINDS,
            ),
            order=alt.Order("kind:N", sort="ascending"),
            tooltip=[
                alt.Tooltip("bucket:T", title="Time"),
                alt.Tooltip("kind:N", title="Token type"),
                alt.Tooltip("cost:Q", title="Cost (USD)", format="$.4f"),
            ],
        )
        .properties(title="Cost over time, by token type", height=300)
    )
    _chart
    return


@app.cell
def _(INK, KINDS, SERIES, alt, df_chart1, pd):
    _by_kind = pd.DataFrame(
        {"kind": KINDS, "cost": [df_chart1[k].sum() for k in KINDS]}
    ).sort_values("cost", ascending=False)

    _bars = (
        alt.Chart(_by_kind)
        .mark_bar(cornerRadiusEnd=4, height=18)
        .encode(
            y=alt.Y("kind:N", title=None, sort="-x"),
            x=alt.X("cost:Q", title="Total cost (USD)"),
            color=alt.Color(
                "kind:N", scale=alt.Scale(domain=KINDS, range=SERIES), legend=None
            ),
            tooltip=[
                alt.Tooltip("kind:N", title="Token type"),
                alt.Tooltip("cost:Q", title="Cost (USD)", format="$.4f"),
            ],
        )
    )
    # Direct labels in text ink — the relief the contrast WARN obligates.
    _labels = _bars.mark_text(align="left", dx=6, color=INK).encode(
        text=alt.Text("cost:Q", format="$.3f")
    )
    _chart = (_bars + _labels).properties(
        title="Total cost by token type", height=140
    )
    _chart
    return


@app.cell
def _(mo):
    mo.md("""
    **Table view** — the same numbers, no color required.
    """)
    return


@app.cell
def _(KINDS, df_chart1, mo):
    mo.ui.table(df_chart1.round({k: 4 for k in KINDS}), selection=None)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Token volume, unpriced

    The same spend by raw count. Read it against the cost chart above: cache reads
    dominate the volume and almost vanish from the bill.
    """)
    return


@app.cell
def _(dataset):
    df_chart2 = dataset(
        """
        select 'Input' as kind, sum(message__usage__input_tokens) as tokens
        from session_events where type = 'assistant'
        union all
        select 'Output', sum(message__usage__output_tokens)
        from session_events where type = 'assistant'
        union all
        select 'Cache write', sum(message__usage__cache_creation_input_tokens)
        from session_events where type = 'assistant'
        union all
        select 'Cache read', sum(message__usage__cache_read_input_tokens)
        from session_events where type = 'assistant'
        """
    ).df()
    return (df_chart2,)


@app.cell
def _(INK, SERIES, alt, df_chart2):
    _bars = (
        alt.Chart(df_chart2)
        .mark_bar(color=SERIES[0], cornerRadiusEnd=4, height=18)
        .encode(
            y=alt.Y("kind:N", title=None, sort="-x"),
            x=alt.X("tokens:Q", title="Tokens"),
            tooltip=[
                alt.Tooltip("kind:N", title="Token type"),
                alt.Tooltip("tokens:Q", title="Tokens", format=","),
            ],
        )
    )
    _labels = _bars.mark_text(align="left", dx=6, color=INK).encode(
        text=alt.Text("tokens:Q", format=",")
    )
    _chart = (_bars + _labels).properties(
        title="Token volume by type", height=140
    )
    _chart
    return


@app.cell
def _(mo):
    mo.md("""
    ## Turn by turn

    Cache-read share is the fraction of each request's input that was served from
    cache rather than reprocessed. It climbs as a session accumulates a stable prefix.
    """)
    return


@app.cell
def _(dataset):
    df_chart3 = dataset(
        """
        with s as (
            select session_id, min(timestamp) as t0
            from session_events
            where type = 'assistant' and session_id is not null
            group by 1
        ), r as (
            select session_id,
                   'Session ' || cast(dense_rank() over (order by t0) as varchar)
                     as session_label
            from s
        )
        select r.session_label,
               row_number() over (
                   partition by e.session_id order by e.timestamp
               ) as turn,
               e.message__usage__output_tokens as output_tokens,
               100.0 * e.message__usage__cache_read_input_tokens
                 / nullif(e.message__usage__cache_read_input_tokens
                          + e.message__usage__cache_creation_input_tokens
                          + e.message__usage__input_tokens, 0) as cache_pct
        from session_events e
        join r on r.session_id = e.session_id
        where e.type = 'assistant'
        order by r.session_label, turn
        """
    ).df()
    return (df_chart3,)


@app.cell
def _(SERIES, alt, df_chart3):
    _base = alt.Chart(df_chart3).encode(
        x=alt.X("turn:O", title="Assistant turn within session"),
        y=alt.Y(
            "cache_pct:Q",
            title="Input served from cache (%)",
            scale=alt.Scale(domain=[0, 100]),
        ),
        tooltip=[
            alt.Tooltip("session_label:N", title="Session"),
            alt.Tooltip("turn:O", title="Turn"),
            alt.Tooltip("cache_pct:Q", title="Cache share (%)", format=".1f"),
        ],
    )
    _chart = (
        (
            _base.mark_line(color=SERIES[0], strokeWidth=2)
            + _base.mark_point(color=SERIES[0], size=80, filled=True)
        )
        .properties(width=320, height=220)
        .facet(column=alt.Column("session_label:N", title=None))
        .properties(title="Cache efficiency per turn")
    )
    _chart
    return


@app.cell
def _(SERIES, alt, df_chart3):
    _chart = (
        alt.Chart(df_chart3)
        .mark_bar(color=SERIES[0], cornerRadiusEnd=4)
        .encode(
            x=alt.X("turn:O", title="Assistant turn within session"),
            y=alt.Y("output_tokens:Q", title="Output tokens"),
            tooltip=[
                alt.Tooltip("session_label:N", title="Session"),
                alt.Tooltip("turn:O", title="Turn"),
                alt.Tooltip("output_tokens:Q", title="Output tokens", format=","),
            ],
        )
        .properties(width=320, height=220)
        .facet(column=alt.Column("session_label:N", title=None))
        .properties(title="Response size per turn")
    )
    _chart
    return


@app.cell
def _(mo):
    mo.md("""
    ## What the session was made of
    """)
    return


@app.cell
def _(dataset):
    df_chart5 = dataset(
        """
        select name, count(*) as calls
        from session_events__message__content
        where type = 'tool_use' and name is not null
        group by 1
        order by 2 desc
        """
    ).df()
    return (df_chart5,)


@app.cell
def _(INK, SERIES, alt, df_chart5):
    _bars = (
        alt.Chart(df_chart5)
        .mark_bar(color=SERIES[0], cornerRadiusEnd=4, height=18)
        .encode(
            y=alt.Y("name:N", title=None, sort="-x"),
            x=alt.X("calls:Q", title="Calls"),
            tooltip=[
                alt.Tooltip("name:N", title="Tool"),
                alt.Tooltip("calls:Q", title="Calls"),
            ],
        )
    )
    _labels = _bars.mark_text(align="left", dx=6, color=INK).encode(
        text="calls:Q"
    )
    _chart = (_bars + _labels).properties(title="Tool calls by tool", height=200)
    _chart
    return


@app.cell
def _(dataset):
    df_chart6 = dataset(
        """
        select type, count(*) as n
        from session_events
        group by 1
        order by 2 desc
        """
    ).df()
    return (df_chart6,)


@app.cell
def _(INK, SERIES, alt, df_chart6):
    _bars = (
        alt.Chart(df_chart6)
        .mark_bar(color=SERIES[0], cornerRadiusEnd=4, height=18)
        .encode(
            y=alt.Y("type:N", title=None, sort="-x"),
            x=alt.X("n:Q", title="Records"),
            tooltip=[
                alt.Tooltip("type:N", title="Record type"),
                alt.Tooltip("n:Q", title="Records"),
            ],
        )
    )
    _labels = _bars.mark_text(align="left", dx=6, color=INK).encode(text="n:Q")
    _chart = (_bars + _labels).properties(
        title="Transcript record types", height=280
    )
    _chart
    return


if __name__ == "__main__":
    app.run()
