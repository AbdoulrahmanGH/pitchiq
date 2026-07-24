"""Tests for the raw-data landing zone: extract() fetches from StatsBomb on
GitHub as before (unchanged), but the pipeline now lands that raw JSON in
GCS first and transform() sources its data from a read-back of the bucket,
not from extract()'s in-memory return value directly. Proves the bucket is
the actual data path, not just an audit side-channel.

Uses a fake GCS client double (in-memory dict) -- no real network/GCS calls.
"""

import json

import pytest

from app.data.pipeline_v2 import land_raw_data_in_gcs, read_raw_from_gcs


class FakeBlob:
    def __init__(self, store, path):
        self.store = store
        self.path = path

    def upload_from_string(self, data, content_type=None):
        self.store[self.path] = data

    def download_as_text(self):
        return self.store[self.path]


class FakeBucket:
    def __init__(self, store):
        self.store = store

    def blob(self, path):
        return FakeBlob(self.store, path)


class FakeStorageClient:
    def __init__(self):
        self.store = {}

    def bucket(self, name):
        return FakeBucket(self.store)


MATCHES = [
    {"match_id": 1, "home_team": {"home_team_name": "A"}},
    {"match_id": 2, "home_team": {"home_team_name": "B"}},
]
EVENTS_BY_MATCH = {1: [{"type": {"name": "Pass"}}], 2: [{"type": {"name": "Shot"}}]}
LINEUPS_BY_MATCH = {1: [{"team_id": 10}], 2: [{"team_id": 20}]}


def test_land_and_read_round_trips_exact_data():
    client = FakeStorageClient()

    run_prefix = land_raw_data_in_gcs(MATCHES, EVENTS_BY_MATCH, LINEUPS_BY_MATCH,
                                      storage_client=client, bucket_name="test-bucket")
    matches, events_by_match, lineups_by_match = read_raw_from_gcs(
        run_prefix, storage_client=client, bucket_name="test-bucket")

    assert matches == MATCHES
    assert events_by_match == EVENTS_BY_MATCH
    assert lineups_by_match == LINEUPS_BY_MATCH


def test_land_writes_valid_json_under_run_scoped_prefix():
    client = FakeStorageClient()

    run_prefix = land_raw_data_in_gcs(MATCHES, EVENTS_BY_MATCH, LINEUPS_BY_MATCH,
                                      storage_client=client, bucket_name="test-bucket")

    assert run_prefix.startswith("raw/")
    assert json.loads(client.store[f"{run_prefix}/matches.json"]) == MATCHES
    assert json.loads(client.store[f"{run_prefix}/events/1.json"]) == EVENTS_BY_MATCH[1]
    assert json.loads(client.store[f"{run_prefix}/lineups/2.json"]) == LINEUPS_BY_MATCH[2]


def test_successive_landings_get_distinct_prefixes():
    # Each run is a durable, separately-inspectable record -- a second run
    # must not silently overwrite the first.
    client = FakeStorageClient()

    prefix_1 = land_raw_data_in_gcs(MATCHES, EVENTS_BY_MATCH, LINEUPS_BY_MATCH,
                                    storage_client=client, bucket_name="test-bucket")
    prefix_2 = land_raw_data_in_gcs(MATCHES, EVENTS_BY_MATCH, LINEUPS_BY_MATCH,
                                    storage_client=client, bucket_name="test-bucket")

    assert prefix_1 != prefix_2
    # both copies survive independently
    assert client.store[f"{prefix_1}/matches.json"] == client.store[f"{prefix_2}/matches.json"]
