"""Integration test proving /api/players/performance is not scoped to a
single team -- regression test for the opponent-visibility fix (it used to
filter to team_id=217/Barcelona only). Uses a real token against the real
pitchiq-v2-dev project, skipped if Supabase isn't configured (mirrors
test_role_gating.py).
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

# Same anon/publishable key already used in test_role_gating.py and shipped
# in the frontend -- safe to hardcode, it only grants sign-in.
ANON_KEY = "sb_publishable_QgX_qUdGGp05HNRkgKV9ww_jDz90TdS"

client = TestClient(app)


def test_performance_includes_players_from_more_than_one_team():
    anon = create_client(SUPABASE_URL, ANON_KEY)
    res = anon.auth.sign_in_with_password({"email": "scout@example.com", "password": "Scout123!"})
    token = res.session.access_token

    response = client.get("/api/players/performance", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    team_ids = {p["team_id"] for p in body}
    assert len(team_ids) > 1
    assert len(body) > 25  # more than just Barcelona's squad
