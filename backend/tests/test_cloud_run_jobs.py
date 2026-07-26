"""Unit tests for the pure logic in app.services.cloud_run_jobs: deriving
status/duration from an execution's raw fields, and shaping/sorting a list
of executions. No real Cloud Run Admin API calls.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services.cloud_run_jobs import (
    JOB_PATH,
    _duration_seconds,
    _execution_status,
    _execution_to_dict,
    list_recent_executions,
)


# ------------------------------- _execution_status --------------------------------

def test_status_running_when_running_count_positive():
    assert _execution_status(succeeded_count=0, failed_count=0, running_count=1) == "running"


def test_status_running_takes_priority_over_stale_failed_count():
    # A retry: the first attempt failed, a second attempt is now running.
    assert _execution_status(succeeded_count=0, failed_count=1, running_count=1) == "running"


def test_status_failed_when_failed_count_positive_and_nothing_running():
    assert _execution_status(succeeded_count=0, failed_count=1, running_count=0) == "failed"


def test_status_succeeded_when_only_succeeded_count_positive():
    assert _execution_status(succeeded_count=1, failed_count=0, running_count=0) == "succeeded"


def test_status_pending_when_all_counts_zero():
    # Just after run_job() returns, before the task has been scheduled.
    assert _execution_status(succeeded_count=0, failed_count=0, running_count=0) == "pending"


# ------------------------------- _duration_seconds ---------------------------------

def test_duration_computed_from_start_and_completion():
    start = datetime(2026, 7, 26, 11, 15, 41, tzinfo=timezone.utc)
    completion = start + timedelta(seconds=121, milliseconds=590)

    assert _duration_seconds(start, completion) == 121.59


def test_duration_none_when_still_running():
    start = datetime(2026, 7, 26, 11, 15, 41, tzinfo=timezone.utc)

    assert _duration_seconds(start, None) is None


def test_duration_none_when_not_yet_started():
    assert _duration_seconds(None, None) is None


# ------------------------------- _execution_to_dict --------------------------------

def _fake_execution(name, create_time=None, start_time=None, completion_time=None,
                    succeeded_count=0, failed_count=0, running_count=0):
    return SimpleNamespace(
        name=name, create_time=create_time, start_time=start_time,
        completion_time=completion_time, succeeded_count=succeeded_count,
        failed_count=failed_count, running_count=running_count,
    )


def test_execution_to_dict_extracts_id_from_full_resource_name():
    execution = _fake_execution(f"{JOB_PATH}/executions/pitchiq-pipeline-v2-6m55l")

    result = _execution_to_dict(execution)

    assert result["id"] == "pitchiq-pipeline-v2-6m55l"


def test_execution_to_dict_reports_succeeded_with_isoformat_timestamps():
    start = datetime(2026, 7, 26, 11, 38, 53, tzinfo=timezone.utc)
    completion = datetime(2026, 7, 26, 11, 40, 46, tzinfo=timezone.utc)
    execution = _fake_execution(
        f"{JOB_PATH}/executions/pitchiq-pipeline-v2-6m55l",
        create_time=start, start_time=start, completion_time=completion,
        succeeded_count=1,
    )

    result = _execution_to_dict(execution)

    assert result["status"] == "succeeded"
    assert result["start_time"] == start.isoformat()
    assert result["completion_time"] == completion.isoformat()
    assert result["duration_seconds"] == 113.0


def test_execution_to_dict_reports_failed():
    execution = _fake_execution("exec-b8x9t", failed_count=1)

    assert _execution_to_dict(execution)["status"] == "failed"


# ------------------------------- list_recent_executions ----------------------------

class FakeExecutionsClient:
    def __init__(self, executions):
        self._executions = executions

    def list_executions(self, request):
        assert request["parent"] == JOB_PATH
        return iter(self._executions)


def test_list_recent_executions_sorts_newest_first():
    old = _fake_execution("e1", create_time=datetime(2026, 7, 25, tzinfo=timezone.utc), succeeded_count=1)
    new = _fake_execution("e2", create_time=datetime(2026, 7, 26, tzinfo=timezone.utc), succeeded_count=1)
    client = FakeExecutionsClient([old, new])

    result = list_recent_executions(client=client)

    assert [r["id"] for r in result] == ["e2", "e1"]


def test_list_recent_executions_respects_limit():
    executions = [
        _fake_execution(f"e{i}", create_time=datetime(2026, 7, 20 + i, tzinfo=timezone.utc),
                       succeeded_count=1)
        for i in range(5)
    ]
    client = FakeExecutionsClient(executions)

    result = list_recent_executions(client=client, limit=2)

    assert len(result) == 2
    assert result[0]["id"] == "e4"
    assert result[1]["id"] == "e3"
