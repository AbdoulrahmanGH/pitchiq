# Demo Accounts

**Dev/demo credentials only — not real user data.** These accounts exist
solely in the `pitchiq-v2-dev` Supabase project (never production) and are
used for local testing and the interview demo. Seeded by
`backend/app/data/seed_demo_users.py`, which is safe to re-run at any time
(idempotent — it checks for each user before creating one).

| Email | Password | Role |
|---|---|---|
| analyst@example.com | Analyst123! | analyst |
| coach@example.com | Coach123! | coach |
| scout@example.com | Scout123! | scout |

The frontend login page (`/login`) has one-click "Demo: Analyst" /
"Demo: Coach" / "Demo: Scout" buttons that sign in as these accounts
directly — dev-only scaffolding, not present in a real production build.
