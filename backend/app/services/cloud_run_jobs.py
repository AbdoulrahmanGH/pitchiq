"""Wraps the Cloud Run Admin API (google.cloud.run_v2) for the pipeline
Job pitchiq-pipeline-v2: real execution history and triggering a new run.

There is no local pipeline_runs table for this -- Cloud Run's own execution
history is directly queryable via this API and already carries everything
a "recent runs" view needs (start/completion time, status, duration), so
building a redundant table to track the same thing would just be another
place for it to drift out of sync with reality.
"""

from google.cloud import run_v2

PROJECT = "pitchiq-494423"
REGION = "europe-west1"
JOB_NAME = "pitchiq-pipeline-v2"

JOB_PATH = f"projects/{PROJECT}/locations/{REGION}/jobs/{JOB_NAME}"


def _execution_status(succeeded_count, failed_count, running_count):
    """Derived from the execution's own task counters, not by parsing
    condition message text (which is free-form and not meant for parsing).
    """
    if running_count > 0:
        return "running"
    if failed_count > 0:
        return "failed"
    if succeeded_count > 0:
        return "succeeded"
    return "pending"


def _duration_seconds(start_time, completion_time):
    if not start_time or not completion_time:
        return None
    return (completion_time - start_time).total_seconds()


def _execution_to_dict(execution):
    return {
        "id": execution.name.split("/")[-1],
        "create_time": execution.create_time.isoformat() if execution.create_time else None,
        "start_time": execution.start_time.isoformat() if execution.start_time else None,
        "completion_time": execution.completion_time.isoformat() if execution.completion_time else None,
        "status": _execution_status(
            execution.succeeded_count, execution.failed_count, execution.running_count
        ),
        "duration_seconds": _duration_seconds(execution.start_time, execution.completion_time),
    }


def list_recent_executions(client=None, limit=10):
    client = client or run_v2.ExecutionsClient()
    executions = client.list_executions(request={"parent": JOB_PATH})
    rows = [_execution_to_dict(e) for e in executions]
    rows.sort(key=lambda r: r["create_time"] or "", reverse=True)
    return rows[:limit]


def trigger_pipeline_run(client=None):
    """Fires a new execution and returns immediately -- does not wait for
    the job to finish (that takes ~2 minutes). The caller (POST
    /api/pipeline/refresh) returns right away; the frontend watches
    list_recent_executions() to see the new run appear and progress from
    pending -> running -> succeeded/failed.
    """
    client = client or run_v2.JobsClient()
    client.run_job(name=JOB_PATH)
