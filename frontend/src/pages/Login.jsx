import { useState } from 'react';
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
  { label: 'Demo: Analyst', email: 'analyst@example.com', password: 'Analyst123!' },
  { label: 'Demo: Coach', email: 'coach@example.com', password: 'Coach123!' },
  { label: 'Demo: Scout', email: 'scout@example.com', password: 'Scout123!' },
];

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

export default function Login() {
  const navigate = useNavigate();
  const { session, role, signOut } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function signIn(loginEmail, loginPassword) {
    setLoading(true);
    setError(null);
    try {
      const { data, error: authError } = await supabase.auth.signInWithPassword({
        email: loginEmail,
        password: loginPassword,
      });
      if (authError) throw authError;

      const who = await getWhoAmI(data.session.access_token);
      navigate(landingRouteForRole(who.role), { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(e) {
    e.preventDefault();
    signIn(email, password);
  }

  if (session) {
    return (
      <div style={pageStyle}>
        <div style={cardStyle}>
          <h2 style={{ marginBottom: 20 }}>Logged in</h2>
          <p style={{ fontSize: 14, color: 'var(--text-secondary)' }}>Signed in as</p>
          <p style={{ fontSize: 15, marginBottom: 4 }}>{session.user.email}</p>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 16 }}>
            role: {role ?? 'unknown'}
          </p>
          <button style={buttonStyle} onClick={signOut}>Log out</button>
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
            onClick={() => signIn(acct.email, acct.password)}
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
