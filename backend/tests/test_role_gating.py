"""Integration tests proving the real dashboard endpoints are gated to any
authenticated user (not a specific role -- coach needs fatigue-risk as much
as analyst does). Uses real tokens for the 3 seeded demo accounts against
the real pitchiq-v2-dev project, not fakes -- skipped if Supabase isn't
configured (mirrors test_load_idempotency.py).
"""

import pytest
from fastapi.testclient import TestClient
from supabase import create_client

from app.config import SUPABASE_KEY, SUPABASE_URL
from app.main import app

pytestmark = pytest.mark.skipif(
    not SUPABASE_URL or not SUPABASE_KEY,
    reason="SUPABASE_URL/SUPABASE_KEY not configured",
)

# Safe to hardcode: the anon/publishable key is designed for exactly this
# (a client signing a user in), and is the same key already shipped in the
# frontend (src/services/supabaseClient.js) -- it grants nothing on its own.
ANON_KEY = "sb_publishable_QgX_qUdGGp05HNRkgKV9ww_jDz90TdS"

DEMO_ACCOUNTS = {
    "analyst": ("analyst@example.com", "Analyst123!"),
    "coach": ("coach@example.com", "Coach123!"),
    "scout": ("scout@example.com", "Scout123!"),
}

GATED_ENDPOINTS = [
    "/api/players/performance",
    "/api/players/depth",
    "/api/players/fatigue-risk",
    "/api/matches/summary",
    "/api/team/readiness",
]

client = TestClient(app)


@pytest.fixture(scope="module")
def demo_tokens():
    anon = create_client(SUPABASE_URL, ANON_KEY)
    tokens = {}
    for role, (email, password) in DEMO_ACCOUNTS.items():
        res = anon.auth.sign_in_with_password({"email": email, "password": password})
        tokens[role] = res.session.access_token
    return tokens


@pytest.mark.parametrize("path", GATED_ENDPOINTS)
def test_endpoint_requires_auth(path):
    response = client.get(path)
    assert response.status_code == 401


@pytest.mark.parametrize("path", GATED_ENDPOINTS)
@pytest.mark.parametrize("role", DEMO_ACCOUNTS.keys())
def test_endpoint_succeeds_for_each_demo_role(path, role, demo_tokens):
    token = demo_tokens[role]
    response = client.get(path, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


def test_health_stays_ungated():
    response = client.get("/health")
    assert response.status_code == 200
