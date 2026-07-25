"""Seeds 3 demo accounts (analyst/coach/scout) for local/dev testing and the
interview demo, against pitchiq-v2-dev, plus their matching user_roles rows.
Idempotent: safe to re-run, existing users/roles are left alone.

Why this file needs a second, more-privileged credential:
Every other part of this app talks to Supabase using SUPABASE_KEY (the
project's new-style `sb_secret_...` API key), which is sufficient for all
normal table reads/writes through PostgREST. But Supabase Auth's Admin API
(client.auth.admin.*, used here to create users directly with
email_confirm=True so no real email confirmation is required) currently
rejects that key on this project: it tries to verify the bearer token as a
signed JWT, and the new opaque secret key isn't one, failing with a 403
("unrecognized JWT kid"). The legacy `service_role` key (an actual JWT) is
still accepted there. So this script -- and only this script -- reads
SUPABASE_SERVICE_ROLE_JWT from backend/.env, a separate credential used
nowhere else in the app (see app/config.py, which does not expose it). If
Supabase later accepts the new key format for Admin API auth, this
special-case can be dropped in favor of SUPABASE_KEY like everything else.
"""

import os

from dotenv import load_dotenv
from supabase import create_client

from app.config import SUPABASE_URL
from app.db import get_db

load_dotenv()

SUPABASE_SERVICE_ROLE_JWT = os.getenv("SUPABASE_SERVICE_ROLE_JWT")

DEMO_USERS = [
    {"email": "analyst@example.com", "password": "Analyst123!", "role": "analyst"},
    {"email": "coach@example.com", "password": "Coach123!", "role": "coach"},
    {"email": "scout@example.com", "password": "Scout123!", "role": "scout"},
]


def _admin_client():
    if not SUPABASE_SERVICE_ROLE_JWT:
        raise RuntimeError(
            "SUPABASE_SERVICE_ROLE_JWT is not set in backend/.env -- required "
            "for this script's Admin API calls (see module docstring)."
        )
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_JWT)


def _find_existing_user(admin_client, email, per_page=200):
    page = 1
    while True:
        users = admin_client.auth.admin.list_users(page=page, per_page=per_page)
        if not users:
            return None
        for u in users:
            if u.email == email:
                return u
        if len(users) < per_page:
            return None
        page += 1


def ensure_user(admin_client, email, password):
    existing = _find_existing_user(admin_client, email)
    if existing:
        print(f"  user {email} already exists ({existing.id}), skipping create")
        return existing.id

    created = admin_client.auth.admin.create_user({
        "email": email,
        "password": password,
        "email_confirm": True,
    })
    print(f"  created user {email} ({created.user.id})")
    return created.user.id


def ensure_role(db_client, user_id, role):
    db_client.table("user_roles").upsert(
        {"user_id": user_id, "role": role}, on_conflict="user_id"
    ).execute()
    print(f"  role '{role}' set for {user_id}")


def seed():
    admin_client = _admin_client()
    db_client = get_db()

    for account in DEMO_USERS:
        print(f"{account['email']}:")
        user_id = ensure_user(admin_client, account["email"], account["password"])
        ensure_role(db_client, user_id, account["role"])

    print("\nDone. See DEMO_ACCOUNTS.md for credentials.")


if __name__ == "__main__":
    seed()
