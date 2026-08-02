# Analysis plan — claude_logs

## Connection

- **Pipeline:** `claude_logs` (dlt, `dlt.attach("claude_logs")`)
- **Destination:** duckdb — `.dlt/data/dev/claude_logs.duckdb`
- **Dataset:** resolved at runtime via `pipeline.dataset()` (dev_mode mints a new timestamped dataset per run — never hardcode the name)
- **Source:** `~/.claude/projects/**/*.jsonl` Claude Code session transcripts

## Profile Summary

| Table | Rows | Used for |
|---|---|---|
| `session_events` | 228 | all token/cost/event charts (106 cols) |
| `session_events__message__content` | 137 | tool-call frequency (`type='tool_use'` → `name`) |

Key columns: `type`, `timestamp`, `session_id`, `message__model`, `message__usage__input_tokens`,
`__output_tokens`, `__cache_creation_input_tokens`, `__cache_read_input_tokens`,
`__cache_creation__ephemeral_1h_input_tokens` / `__5m_...`.

**Anomalies / notes**

- Span is a single day (2026-08-01), 2 sessions, one model (`claude-opus-5`). No multi-day trend is possible — time charts use 5-minute buckets, and the two sessions are ~16h apart so the axis has a real gap.
- The live session file grows while the pipeline runs, so counts are a snapshot, not a final total.
- Cache writes are **100% 1h TTL** (`ephemeral_5m` = 0), so cache-write cost uses the flat 2× rate.
- 8 rows have NULL `session_id` (`mode` / `permission-mode` records legitimately carry none).
- **PII:** `cwd`, `git_branch`, and `tool_use_result__*` contain local paths and file contents. Not used as chart dimensions.

## Pricing (Opus 5, per million tokens)

| Token type | Rate | Basis |
|---|---|---|
| Input | $5.00 | base |
| Output | $25.00 | base |
| Cache write (1h) | $10.00 | 2× input |
| Cache write (5m) | $6.25 | 1.25× input |
| Cache read | $0.50 | 0.1× input |

## Palette

Reference categorical slots 1–4, validated in both modes with `validate_palette.js`:
light `#2a78d6,#eb6834,#1baf7a,#eda100` (all checks PASS, contrast WARN on aqua+yellow →
relief via direct labels + table view); dark `#3987e5,#d95926,#199e70,#c98500` (all PASS).
Single-series charts use slot 1 only and carry no legend.

## Questions

- [x] What does a session actually cost, and where does the money go?
- [x] How is token spend distributed across input / output / cache?
- [x] How effective is prompt caching, turn over turn?
- [x] How long are the responses?
- [x] Which tools get used most?
- [x] What is the event mix in a session transcript?

## Data Gaps

None for the charted questions. Cost is *derived* (no cost field in the logs) — it depends on the
pricing table above, so a rate change makes the cost charts stale.

---

## Chart 1 — Cost over time

**Question:** Where does the money go over the course of a session?
**Type:** stacked bar (temporal). Cost is the great equalizer here — cache reads outnumber output
tokens ~70:1 but cost less per token, so plotting *cost* puts them on one honest axis. Plotting raw
tokens would make output invisible. One axis, never dual.
**X:** 5-minute bucket of `timestamp` (`:T`) · **Y:** `sum(cost_usd)` (`:Q`) · **Color:** token type (4 series)

```sql
select to_timestamp(floor(epoch(timestamp)/300)*300) as bucket,
       sum(message__usage__input_tokens)/1e6*5.00              as "Input",
       sum(message__usage__output_tokens)/1e6*25.00            as "Output",
       sum(message__usage__cache_creation__ephemeral_1h_input_tokens)/1e6*10.00
         + sum(message__usage__cache_creation__ephemeral_5m_input_tokens)/1e6*6.25 as "Cache write",
       sum(message__usage__cache_read_input_tokens)/1e6*0.50   as "Cache read"
from session_events where type = 'assistant' group by 1 order by 1
```

Melted to long form, then `mark_bar` with `x=bucket:T`, `y=cost:Q`, `color=kind:N` (explicit
4-hue range, fixed order), 2px surface gap between stacked segments, tooltip on every segment.

## Chart 2 — Token volume by type

**Question:** How is raw token spend distributed?
**Type:** horizontal bar, single series (magnitude comparison across 4 unordered categories).
Deliberately paired with Chart 1: this one shows cache reads dwarfing everything, Chart 1 shows
that dominance mostly evaporating once priced. Direct value labels on each bar.

```sql
select sum(message__usage__input_tokens) as "Input",
       sum(message__usage__output_tokens) as "Output",
       sum(message__usage__cache_creation_input_tokens) as "Cache write",
       sum(message__usage__cache_read_input_tokens) as "Cache read"
from session_events where type = 'assistant'
```

## Chart 3 — Cache efficiency per turn

**Question:** How much of each request's context is served from cache?
**Type:** line (change over turn sequence), single series, 2px stroke, ≥8px markers, crosshair tooltip.
**X:** turn index within session (`:O`) · **Y:** cache-read share of total input tokens, 0–100%

```sql
select row_number() over (partition by session_id order by timestamp) as turn,
       session_id,
       100.0 * message__usage__cache_read_input_tokens
         / nullif(message__usage__cache_read_input_tokens
                  + message__usage__cache_creation_input_tokens
                  + message__usage__input_tokens, 0) as cache_pct
from session_events where type = 'assistant'
```

Faceted by session (2 small multiples) rather than 2 colored series — the sessions are sequential,
not comparable categories.

## Chart 4 — Response size per turn

**Question:** How long are the model's responses, and do they grow through a session?
**Type:** bar over turn index (`:O`), single series. Bar rather than histogram — with ~90 turns the
sequence carries more information than the distribution, and it shares Chart 3's x-axis for reading across.
**Y:** `message__usage__output_tokens`

## Chart 5 — Tool call frequency

**Question:** Which tools does the agent actually reach for?
**Type:** horizontal bar, single series, sorted descending, direct value labels.

```sql
select name, count(*) as calls
from session_events__message__content
where type = 'tool_use' and name is not null
group by 1 order by 2 desc
```

## Chart 6 — Event type mix

**Question:** What is a session transcript actually made of?
**Type:** horizontal bar, single series, sorted descending, direct value labels.

```sql
select type, count(*) as n from session_events group by 1 order by 2 desc
```

## Non-chart elements

- **Stat tiles** (hero numbers, no plot — magnitude with no comparison needed): total cost, total
  tokens, assistant turns, sessions, overall cache-read share.
- **Table view** — per-bucket cost table. Required relief for the light-mode contrast WARN on the
  aqua and yellow slots, and the accessible alternative to color-only identity.
