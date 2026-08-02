"""dlt REST API pipeline: load Claude Code agent traces from the Agent Logs API into DuckDB.

Source: https://test-agent-traces-api-xt2e7ottma-ew.a.run.app (Claude Code Agent Logs API)
Endpoint: GET /logs — offset/limit pagination, `logs` array in the response envelope,
1,000,000 rows available, max 1000 rows per request.

No authentication: the API declares no security schemes and serves data unauthenticated,
so there is nothing in secrets.toml for this source.
"""

from typing import Any

import dlt
from dlt.hub import run
from dlt.sources.rest_api import RESTAPIConfig, rest_api_resources

# The API caps `limit` at 1000, so 20k rows costs 20 requests.
PAGE_SIZE = 1000


@dlt.source(name="agent_traces")
def agent_traces_source(
    base_url: str = dlt.config.value,
    max_logs: int = 20_000,
) -> Any:
    """Claude Code agent trace logs.

    Args:
        base_url: API root. Auto-loaded from `[sources.agent_traces] base_url`
            in .dlt/config.toml.
        max_logs: How many log rows to fetch. Becomes the paginator's
            `maximum_offset`, so it is a hard stop, not a suggestion.

    Example:
        pipeline.run(agent_traces_source())                  # 20k rows
        pipeline.run(agent_traces_source(max_logs=1_000))    # smoke test
    """
    config: RESTAPIConfig = {
        "client": {
            "base_url": base_url,
            "paginator": {
                "type": "offset",
                "limit": PAGE_SIZE,
                "offset_param": "offset",
                "limit_param": "limit",
                # maximum_offset is the stop condition — the endpoint reports
                # total=1,000,000, so without it this would page the whole corpus.
                "maximum_offset": max_logs,
                "total_path": None,
                "stop_after_empty_page": True,
            },
        },
        "resource_defaults": {"write_disposition": "merge"},
        "resources": [
            {
                "name": "logs",
                "primary_key": "index",
                "incremental": dlt.sources.incremental("index"),
                "endpoint": {
                    "path": "logs",
                    # Rows live under the `logs` key alongside paging metadata
                    # (total / offset / limit / count / next_offset).
                    "data_selector": "logs",
                },
            },
        ],
    }

    yield from rest_api_resources(config)


@run.pipeline("agent_traces")
def load_agent_traces() -> None:
    """Load agent trace logs into DuckDB.

    `dev_mode` is profile-scoped: `true` in .dlt/dev.config.toml (fresh
    timestamped dataset per local run), `false` in .dlt/prod.config.toml,
    because on the runtime a per-run dataset would pile up copies.
    Read explicitly — `dlt.config.value` only auto-injects into
    @dlt.source/@dlt.resource functions, not a @run.pipeline one.
    """
    dev_mode = bool(dlt.config.get("dev_mode", bool))

    pipeline = dlt.pipeline(
        pipeline_name="agent_traces",
        destination="playground",
        # Must differ from pipeline_name: DuckDB treats the database file
        # (agent_traces.duckdb) and the schema as one namespace and raises
        # "Ambiguous reference to catalog or schema" when they collide. With
        # dev_mode=True the timestamp suffix hides this; with dev_mode=False
        # (prod) the suffix is gone, so the names must differ on their own.
        dataset_name="agent_traces_raw",
        dev_mode=dev_mode, #needs to be removed since write_disposition is merge
    )

    load_info = pipeline.run(agent_traces_source())
    print(load_info)
    print(pipeline.last_trace.last_normalize_info)


if __name__ == "__main__":
    load_agent_traces()
