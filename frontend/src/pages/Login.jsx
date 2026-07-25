import { useState } from 'react';
import { supabase } from '../services/supabaseClient';
import { getWhoAmI } from '../services/api';

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
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [whoami, setWhoami] = useState(null);
  const [session, setSession] = useState(null);

  async function signIn(loginEmail, loginPassword) {
    setLoading(true);
    setError(null);
    setWhoami(null);
    try {
      const { data, error: authError } = await supabase.auth.signInWithPassword({
        email: loginEmail,
        password: loginPassword,
      });
      if (authError) throw authError;

      setSession(data.session);
      const token = data.session.access_token;
      const who = await getWhoAmI(token);
      setWhoami(who);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function signOut() {
    await supabase.auth.signOut();
    setSession(null);
    setWhoami(null);
  }

  function handleSubmit(e) {
    e.preventDefault();
    signIn(email, password);
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

      {session && whoami && (
        <div style={{ marginTop: 20, padding: 12, background: 'var(--surface2)', borderRadius: 8 }}>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Logged in as</p>
          <p style={{ fontSize: 14 }}>{session.user.email}</p>
          <pre style={{ fontSize: 12, marginTop: 8, color: 'var(--green)' }}>
            {JSON.stringify(whoami, null, 2)}
          </pre>
          <button style={{ ...demoButtonStyle, marginTop: 8 }} onClick={signOut}>
            Log out
          </button>
        </div>
      )}
    </div>
    </div>
  );
}
