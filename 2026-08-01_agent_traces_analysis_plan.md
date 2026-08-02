# Analysis plan — agent_traces

## Connection

- **Pipeline:** `agent_traces` (dlt, `dlt.attach("agent_traces")`)
- **Destination:** duckdb — `.dlt/data/dev/agent_traces.duckdb`, dataset `agent_traces_raw`
- **Source:** Claude Code Agent Logs API — `GET /logs`, offset/limit pagination, 20,000 rows loaded

## Profile Summary

| Table | Rows | Used for |
|---|---|---|
| `logs` | 20,000 | cost, model, session, project, time |
| `logs__message__content` | 19,668 | tool-call frequency (`type='tool_use'` → `name`) |

Columns: `index` (pk), `uuid`, `parent_uuid`, `session_id`, `type`, `timestamp`, `cwd`,
`git_branch`, `version`, `message__model`, `message__role`, `message__stop_reason`,
`message__content` (string, user turns), `usage__input_tokens`, `usage__output_tokens`.

**Shape**

- 20,000 rows: 13,024 `assistant`, 6,976 `user`. Only assistant rows carry `usage`.
- 2,476 sessions · 5 projects (`cwd`) · 4 branches · 1 version · span 2026-01-01 → 2026-01-02 (~39h).
- **4 models**, near-uniform turn counts (23.9%–26.0%) but a ~10× price spread. This is the report's spine.
- **No cache fields** — unlike the local-transcript dataset, this API reports only `input_tokens`
  and `output_tokens`, so there is no cache-efficiency angle. Cost-by-model replaces it.
- `message__content` is a plain string on user turns; assistant content blocks are in the child table.

**Anomalies / PII**

- `cwd` holds paths like `/home/dev/projects/checkout-service` — synthetic API fixture data, not
  the user's machine. Safe as a dimension here; would not be if it were real.
- Single `version` value → no version dimension worth charting.

## Pricing (USD per million tokens, list price)

| Model | Input | Output |
|---|---|---|
| `claude-fable-5` | $10.00 | $50.00 |
| `claude-opus-4-8` | $5.00 | $25.00 |
| `claude-sonnet-5` | $3.00 | $15.00 |
| `claude-haiku-4-5-20251001` | $1.00 | $5.00 |

Sonnet 5 has promotional pricing of $2/$10 through 2026-08-31; the report uses **standard list
price** so the figures don't silently change on 2026-09-01. Noted in the notebook.

## Palette

Reference categorical slots 1–4, validated in both modes (light `#2a78d6,#eb6834,#1baf7a,#eda100`;
dark `#3987e5,#d95926,#199e70,#c98500`). Models are bound to slots in **fixed alphabetical order**,
so a chart sorted by cost never repaints a model — color follows the entity, never its rank.
Light aqua+yellow are sub-3:1 → relief via direct labels + table view.

## Questions

- [x] What did 20k logged turns cost, and which model dominates the bill?
- [x] Does the share of *work* match the share of *spend*?
- [x] How does spend accumulate over time, by model?
- [x] Which tools does the fleet reach for?
- [x] Which projects generate the traffic?
- [x] How long is a typical session?

## Data Gaps

- No cache-token fields → no cache-efficiency chart (the local `claude_logs` report's Chart 3 has
  no counterpart here).
- No per-request latency or error field → no reliability view.
- Cost is derived from the table above, not reported by the API.

---

## Chart 1 — Cost over time by model

**Type:** stacked bar, hourly buckets, 4 model series.
**X:** `date_trunc('hour', timestamp)` (`:T`) · **Y:** `sum(cost)` (`:Q`) · **Color:** model

```sql
select date_trunc('hour', timestamp) as bucket, message__model as model,
       sum(usage__input_tokens)/1e6*<in_rate> + sum(usage__output_tokens)/1e6*<out_rate> as cost
from logs where type = 'assistant' group by 1, 2 order by 1
```

Rates joined in pandas from the PRICE dict so the SQL stays rate-agnostic. 2px surface stroke
between stacked segments; tooltip per segment.

## Chart 2 — Share of work vs share of spend

**Question:** does the share of turns match the share of cost?
**Type:** grouped horizontal bar, 2 series (`Share of turns`, `Share of cost`), models on the axis.
The single most informative chart here: turn share is nearly flat across models while cost share
spans 5.5%→53.5%. **Note:** in this chart color encodes the *metric*, not the model — models are
positional. Every other chart binds color to model.

## Chart 3 — Total cost by model

**Type:** horizontal bar, sorted by cost, direct `$` labels (the contrast relief).

## Chart 4 — Tool calls by tool

```sql
select name, count(*) as calls from logs__message__content
where type = 'tool_use' and name is not null group by 1 order by 2 desc
```

Single series (slot 1), direct value labels.

## Chart 5 — Traffic by project

```sql
select cwd as project, count(*) as records, count(distinct session_id) as sessions
from logs group by 1 order by 2 desc
```

Single series on records, sessions in the tooltip.

## Chart 6 — Session length distribution

**Type:** histogram of turns per session (2,476 sessions) — a distribution question, so a
histogram rather than the per-turn sequence used in the `claude_logs` report (which had 2 sessions).

```sql
select session_id, count(*) as turns from logs group by 1
```

## Non-chart elements

- **Stat tiles:** total cost, rows loaded, sessions, assistant turns, total tokens, cost per session.
- **Table view:** per-model cost/turns/tokens — contrast relief and the color-free alternative.
