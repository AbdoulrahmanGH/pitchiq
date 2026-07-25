import { NavLink } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { useAuth } from '../services/AuthProvider';

const NAV = [
  { path: '/',        emoji: '🏠', label: 'Dashboard'   },
  { path: '/players', emoji: '👤', label: 'Players'     },
  { path: '/matches', emoji: '⚽', label: 'Matches'     },
  { path: '/depth',   emoji: '📊', label: 'Squad Depth' },
  { path: '/about',   emoji: '📖', label: 'About'       },
];

const ROLE_LABELS = {
  analyst: { label: 'Analyst', sub: 'Performance Staff' },
  coach:   { label: 'Coach',   sub: 'Coaching Staff'    },
  scout:   { label: 'Scout',   sub: 'Recruitment'       },
};

// Nav visibility by role -- kept here rather than per-page route guards,
// since this step is only about which links show, not blocking direct
// navigation to a route.
const NAV_PATHS_BY_ROLE = {
  analyst: ['/', '/players', '/matches', '/depth', '/about'],
  coach:   ['/', '/players', '/matches', '/depth'],
  scout:   ['/players', '/matches', '/depth'],
};

function navForRole(role) {
  const allowedPaths = NAV_PATHS_BY_ROLE[role];
  // Role not resolved yet (e.g. right after sign-in, before /whoami
  // returns) -- show everything rather than guessing.
  return allowedPaths ? NAV.filter(n => allowedPaths.includes(n.path)) : NAV;
}

function useMobile() {
  const [mobile, setMobile] = useState(() => window.innerWidth < 768);
  useEffect(() => {
    const fn = () => setMobile(window.innerWidth < 768);
    window.addEventListener('resize', fn);
    return () => window.removeEventListener('resize', fn);
  }, []);
  return mobile;
}

function NavItem({ path, emoji, label, collapsed }) {
  const [hov, setHov] = useState(false);
  return (
    <NavLink to={path} end style={{ textDecoration: 'none' }} title={collapsed ? label : undefined}>
      {({ isActive }) => (
        <div
          onMouseEnter={() => setHov(true)}
          onMouseLeave={() => setHov(false)}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'flex-start',
            gap: collapsed ? 0 : 11,
            padding: collapsed ? '12px 0' : '10px 14px',
            borderRadius: 9, cursor: 'pointer',
            color: isActive ? 'var(--orange)' : hov ? 'var(--text-primary)' : 'var(--text-secondary)',
            background: isActive ? 'rgba(255,107,53,0.1)' : hov ? 'rgba(255,255,255,0.04)' : 'transparent',
            transition: 'all 0.18s ease', fontSize: 13.5,
            fontWeight: isActive ? 600 : 400, position: 'relative',
          }}
        >
          {isActive && (
            <div style={{
              position: 'absolute', left: 0, top: '50%',
              transform: 'translateY(-50%)',
              width: 3, height: 18,
              background: 'var(--orange)', borderRadius: '0 3px 3px 0',
            }} />
          )}
          <span style={{ fontSize: collapsed ? 18 : 14 }}>{emoji}</span>
          {!collapsed && label}
        </div>
      )}
    </NavLink>
  );
}

function SidebarFooter() {
  const { session, role, signOut } = useAuth();

  if (!session) {
    return (
      <div style={{ marginTop: 'auto', padding: '20px 6px 24px' }}>
        <div style={{ borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: 14 }}>
          <NavLink to="/login" style={{ fontSize: 12, fontWeight: 600, color: 'var(--orange)', textDecoration: 'none' }}>
            Log in
          </NavLink>
        </div>
      </div>
    );
  }

  const roleInfo = ROLE_LABELS[role] || { label: role || 'Signed in', sub: '' };

  return (
    <div style={{ marginTop: 'auto', padding: '20px 6px 24px' }}>
      <div style={{ borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 10 }}>
          <div style={{ width: 28, height: 28, borderRadius: 8, background: 'rgba(255,255,255,0.05)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <circle cx="6" cy="4.5" r="2.5" fill="var(--text-muted)" />
              <path d="M1 11c0-2.761 2.239-4 5-4s5 1.239 5 4" stroke="var(--text-muted)" strokeWidth="1.2" strokeLinecap="round" />
            </svg>
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 11.5, fontWeight: 500, color: 'var(--text-secondary)' }}>{roleInfo.label}</div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={session.user.email}>
              {session.user.email}
            </div>
          </div>
        </div>
        <button
          onClick={signOut}
          style={{ width: '100%', textAlign: 'left', background: 'none', border: 'none', color: 'var(--orange)', fontSize: 11, fontWeight: 600, cursor: 'pointer', padding: 0 }}
        >
          Log out
        </button>
      </div>
    </div>
  );
}

export default function Sidebar() {
  const isMobile = useMobile();
  const w = isMobile ? 60 : 200;
  const { role } = useAuth();
  const nav = navForRole(role);

  return (
    <div style={{
      width: w, flexShrink: 0,
      background: 'linear-gradient(180deg, #131920 0%, #111519 100%)',
      borderRight: '1px solid rgba(255,255,255,0.06)',
      display: 'flex', flexDirection: 'column',
      padding: isMobile ? '0 6px' : '0 12px',
      transition: 'width 0.2s ease',
      overflow: 'hidden',
    }}>
      <div style={{
        padding: isMobile ? '18px 0' : '24px 6px 28px',
        borderBottom: '1px solid rgba(255,255,255,0.05)',
        marginBottom: 12,
        display: 'flex', justifyContent: 'center',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: isMobile ? 0 : 8 }}>
          <div style={{
            width: 28, height: 28, borderRadius: 7,
            background: 'linear-gradient(135deg, #FF6B35, #c94a1a)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
          }}>
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <ellipse cx="7" cy="7" rx="5.5" ry="5.5" stroke="white" strokeWidth="1.2" opacity=".8" />
              <line x1="7" y1="1.5" x2="7" y2="12.5" stroke="white" strokeWidth="1" opacity=".6" />
              <line x1="1.5" y1="7" x2="12.5" y2="7" stroke="white" strokeWidth="1" opacity=".6" />
            </svg>
          </div>
          {!isMobile && (
            <div>
              <div style={{ fontFamily: 'Space Grotesk', fontWeight: 700, fontSize: 17, color: 'var(--orange)', letterSpacing: '0.04em' }}>PitchIQ</div>
              <div style={{ fontSize: 9.5, color: 'var(--text-muted)', letterSpacing: '0.08em', marginTop: -1 }}></div>
            </div>
          )}
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        {!isMobile && (
          <div style={{ fontSize: 9.5, fontWeight: 700, letterSpacing: '0.14em', color: 'var(--text-muted)', padding: '4px 14px 8px', textTransform: 'uppercase' }}>
            Analytics
          </div>
        )}
        {nav.map(n => <NavItem key={n.path} {...n} collapsed={isMobile} />)}
      </div>

      {!isMobile && <SidebarFooter />}
    </div>
  );
}
