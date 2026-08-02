"""Agent traces — ingest Claude Code agent logs from the Agent Logs API into DuckDB.

Deployment manifest — import the pipelines and notebooks you want to deploy and list them in __all__.
"""

from rest_api_pipeline import load_agent_traces

# Module import (not `from ... import app`): the manifest generator auto-detects
# the module-level marimo.App and registers it as an interactive job. Importing
# the App object instead registers it under the `__deployment__` section and
# drops the pipeline job from the manifest.
import agent_traces_dashboard

from dlt.hub.run import trigger

@run.pipeline("agent_traces", trigger=trigger.schedule("0 12 * * *"))
def ingest_agent_logs(): ...

__all__: list[str] = ["load_agent_traces", "agent_traces_dashboard"]
