"""dlt filesystem pipeline: load local Claude Code session logs into DuckDB.

Reads every ``*.jsonl`` session transcript under ``~/.claude/projects`` and lets
dlt infer the schema — nested objects become flattened columns, arrays become
child tables. One row per JSONL line, all rows in one ``session_events`` table.

``bucket_url`` is read from .dlt/config.toml under [sources.filesystem];
``file_glob`` is set inline so the pattern lives next to the code using it.
"""

import dlt
from dlt.sources.filesystem import filesystem, read_jsonl


def load_session_events() -> None:
    """Load Claude Code session transcripts into DuckDB, replacing previous contents."""
    pipeline = dlt.pipeline(
        pipeline_name="claude_logs",
        destination="duckdb",
        # must differ from pipeline_name: DuckDB treats the db file (claude_logs.duckdb)
        # and the schema as the same namespace and errors on an ambiguous reference
        dataset_name="claude_logs",
        dev_mode=True,  # stable dataset name; `replace` already makes reruns idempotent, needs to be removed since write_disposition is merge.
    )

    reader = (filesystem(incremental=dlt.sources.incremental("modification_date"), file_glob="**/*.jsonl") | read_jsonl()).with_name("session_events")

    load_info = pipeline.run(reader, write_disposition="merge")
    print(load_info)
    print(pipeline.last_trace.last_normalize_info)


if __name__ == "__main__":
    load_session_events()
