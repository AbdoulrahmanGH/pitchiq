import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { supabase } from '../services/supabaseClient';
import { getWhoAmI } from '../services/api';
import { useAuth } from '../services/AuthProvider';

// Dev/demo-only quick-login credentials. These accounts are seeded by
// backend/app/data/seed_demo_users.py against the non-production
// pitchiq-v2-dev database (see DEMO_ACCOUNTS.md). This entire block of
// one-click demo buttons exists for fast role-switching while testing and
// for the interview demo -- it must NOT ship in a real production build.
const DEMO_ACCOUNTS = [
  { label: 'Demo: Analyst', roleLabel: 'Analyst', email: 'analyst@example.com', password: 'Analyst123!' },
  { label: 'Demo: Coach',   roleLabel: 'Coach',   email: 'coach@example.com',   password: 'Coach123!' },
  { label: 'Demo: Scout',   roleLabel: 'Scout',   email: 'scout@example.com',   password: 'Scout123!' },
];

const ROLE_DISPLAY = { analyst: 'Analyst', coach: 'Coach', scout: 'Scout' };

// Landing route differs by role -- matches how each role actually uses the
// app (a scout opens the app to look at players, not the team dashboard).
function landingRouteForRole(role) {
  return role === 'scout' ? '/players' : '/';
}

const pageStyle = {
  height: '100%',
  overflow: 'auto',
};

const cardStyle = {
  maxWidth: 420,
  margin: '80px auto',
  padding: 32,
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: 12,
};

const inputStyle = {
  width: '100%',
  padding: '10px 12px',
  marginBottom: 12,
  background: 'var(--surface2)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  color: 'var(--text-primary)',
  fontSize: 14,
};

const buttonStyle = {
  width: '100%',
  padding: '10px 12px',
  marginBottom: 8,
  background: 'var(--orange)',
  border: 'none',
  borderRadius: 8,
  color: '#111',
  fontWeight: 600,
  cursor: 'pointer',
};

const demoButtonStyle = {
  ...buttonStyle,
  background: 'var(--surface3)',
  color: 'var(--text-primary)',
  fontWeight: 500,
};

// Brief pause after the role is known but before navigating -- without it,
// the dynamic "Logging in as X" text would resolve and redirect away in the
// same tick, so it would never actually be visible.
const SETTLE_MS = 550;

function Spinner() {
  return (
    <span style={{
      width: 30, height: 30, borderRadius: '50%', flexShrink: 0,
      border: '3px solid rgba(255,107,53,0.2)', borderTopColor: 'var(--orange)',
      animation: 'login-spin 0.8s linear infinite', display: 'inline-block',
    }} />
  );
}

export default function Login() {
  const navigate = useNavigate();
  const { session, role, roleLoading, signOut } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  // The role label to display in "Logging in as ___" -- known immediately
  // for demo buttons (their own account is always that role), resolved
  // from /whoami for typed credentials.
  const [pendingLabel, setPendingLabel] = useState(null);

  async function signIn(loginEmail, loginPassword, knownLabel) {
    setLoading(true);
    setError(null);
    setPendingLabel(knownLabel || null);
    try {
      const { data, error: authError } = await supabase.auth.signInWithPassword({
        email: loginEmail,
        password: loginPassword,
      });
      if (authError) throw authError;

      const who = await getWhoAmI(data.session.access_token);
      setPendingLabel(knownLabel || ROLE_DISPLAY[who.role] || who.role);
      await new Promise(resolve => setTimeout(resolve, SETTLE_MS));
      navigate(landingRouteForRole(who.role), { replace: true });
    } catch (err) {
      setError(err.message);
      setPendingLabel(null);
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(e) {
    e.preventDefault();
    signIn(email, password);
  }

  // Arriving at /login already authenticated (back button, bookmark, a
  // stale tab) used to render a static "Logged in" card with a logout
  // button. That's a dead end -- there's nothing to log in to here.
  // Show the same spinner + role text and carry the user on to their
  // landing route as soon as the role is known.
  useEffect(() => {
    if (session && !loading && !roleLoading) {
      navigate(landingRouteForRole(role), { replace: true });
    }
  }, [session, loading, roleLoading, role, navigate]);

  if (session || loading) {
    const label = pendingLabel || (session && !roleLoading ? (ROLE_DISPLAY[role] || role) : null);
    return (
      <div style={pageStyle}>
        <style>{`@keyframes login-spin { to { transform: rotate(360deg); } }`}</style>
        <div style={cardStyle}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18, padding: '24px 0' }}>
            <Spinner />
            <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', textAlign: 'center' }}>
              {label ? `Logging in as ${label}` : 'Logging in…'}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={pageStyle}>
    <div style={cardStyle}>
      <h2 style={{ marginBottom: 20 }}>Log in</h2>

      <form onSubmit={handleSubmit}>
        <input
          style={inputStyle}
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <input
          style={inputStyle}
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <button style={buttonStyle} type="submit" disabled={loading}>
          {loading ? 'Signing in...' : 'Log in'}
        </button>
      </form>

      {/* Dev-only quick login -- remove before any real production build. */}
      <div style={{ marginTop: 20, paddingTop: 20, borderTop: '1px solid var(--border)' }}>
        <p style={{ color: 'var(--text-secondary)', fontSize: 12, marginBottom: 10 }}>
          Dev quick login (seeded demo accounts):
        </p>
        {DEMO_ACCOUNTS.map((acct) => (
          <button
            key={acct.email}
            style={demoButtonStyle}
            disabled={loading}
            onClick={() => signIn(acct.email, acct.password, acct.roleLabel)}
          >
            {acct.label}
          </button>
        ))}
      </div>

      {error && (
        <p style={{ color: 'var(--red)', marginTop: 12, fontSize: 13 }}>{error}</p>
      )}
    </div>
    </div>
  );
}
