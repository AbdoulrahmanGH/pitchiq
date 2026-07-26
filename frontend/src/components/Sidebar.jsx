import { NavLink } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { useAuth } from '../services/AuthProvider';

const EXPANDED_W = 200;
const COLLAPSED_W = 68;
const EASE = 'cubic-bezier(0.4, 0, 0.2, 1)';

const NAV = [
  { path: '/',         emoji: '🏠', label: 'Dashboard'   },
  { path: '/players',  emoji: '👤', label: 'Players'     },
  { path: '/matches',  emoji: '⚽', label: 'Matches'     },
  { path: '/depth',    emoji: '📊', label: 'Squad Depth' },
  { path: '/my-notes', emoji: '📝', label: 'My Notes'    },
  { path: '/pipeline', emoji: '🛠️', label: 'Pipeline'    },
  { path: '/about',    emoji: '📖', label: 'About'       },
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
  analyst: ['/', '/players', '/matches', '/depth', '/pipeline', '/about'],
  coach:   ['/', '/players', '/matches', '/depth'],
  scout:   ['/players', '/matches', '/depth', '/my-notes'],
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
            transition: `background 0.18s ease, color 0.18s ease, justify-content 0.28s ${EASE}, gap 0.28s ${EASE}, padding 0.28s ${EASE}`,
            fontSize: 13.5,
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
          <span style={{ fontSize: collapsed ? 18 : 14, transition: `font-size 0.2s ${EASE}`, flexShrink: 0 }}>{emoji}</span>
          <span style={{
            opacity: collapsed ? 0 : 1,
            maxWidth: collapsed ? 0 : 140,
            overflow: 'hidden', whiteSpace: 'nowrap',
            transition: `opacity 0.18s ${collapsed ? '0s' : '0.12s'} ease, max-width 0.28s ${EASE}`,
          }}>
            {label}
          </span>
        </div>
      )}
    </NavLink>
  );
}

function CollapseToggle({ collapsed, onClick }) {
  const [hov, setHov] = useState(false);
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      style={{
        position: 'absolute', top: 22, right: -11,
        width: 22, height: 22, borderRadius: '50%',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: hov ? 'var(--orange)' : '#1C2333',
        border: '1px solid rgba(255,255,255,0.1)',
        color: hov ? '#fff' : 'var(--text-secondary)',
        cursor: 'pointer', zIndex: 5, padding: 0,
        boxShadow: '0 2px 6px rgba(0,0,0,0.35)',
        transition: `background 0.15s ease, color 0.15s ease`,
      }}
    >
      <svg
        width="11" height="11" viewBox="0 0 11 11" fill="none"
        style={{ transform: collapsed ? 'rotate(180deg)' : 'none', transition: `transform 0.28s ${EASE}` }}
      >
        <path d="M7 2L3.5 5.5L7 9" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </button>
  );
}

function LogoutIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
      <path d="M4.5 1.5H2.25A0.75 0.75 0 0 0 1.5 2.25v7.5c0 .414.336.75.75.75H4.5" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M7.5 8.5L10.5 6L7.5 3.5" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M10.25 6H4.5" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function SidebarFooter({ collapsed }) {
  const { session, role, signOut } = useAuth();

  if (!session) {
    return (
      <div style={{ marginTop: 'auto', padding: collapsed ? '16px 0 20px' : '20px 6px 24px' }}>
        <div style={{
          borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: 14,
          display: 'flex', justifyContent: collapsed ? 'center' : 'flex-start',
        }}>
          <NavLink
            to="/login"
            title={collapsed ? 'Log in' : undefined}
            style={{ fontSize: 12, fontWeight: 600, color: 'var(--orange)', textDecoration: 'none' }}
          >
            {collapsed ? '⏻' : 'Log in'}
          </NavLink>
        </div>
      </div>
    );
  }

  const roleInfo = ROLE_LABELS[role] || { label: role || 'Signed in', sub: '' };
  const initial = roleInfo.label.charAt(0).toUpperCase();

  return (
    <div style={{ marginTop: 'auto', padding: collapsed ? '16px 0 20px' : '20px 6px 24px' }}>
      <div style={{ borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: 14 }}>
        <div style={{
          display: 'flex', alignItems: 'center',
          justifyContent: collapsed ? 'center' : 'flex-start',
          gap: 9, marginBottom: collapsed ? 10 : 10,
        }}>
          <div
            title={collapsed ? `${roleInfo.label} · ${session.user.email}` : undefined}
            style={{
              width: 28, height: 28, borderRadius: 8, flexShrink: 0,
              background: 'linear-gradient(135deg, #FF6B35, #c94a1a)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 11, fontWeight: 700, color: '#fff', fontFamily: 'Space Grotesk',
            }}
          >
            {initial}
          </div>
          {!collapsed && (
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 11.5, fontWeight: 500, color: 'var(--text-secondary)' }}>{roleInfo.label}</div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={session.user.email}>
                {session.user.email}
              </div>
            </div>
          )}
        </div>
        <button
          onClick={signOut}
          title={collapsed ? 'Log out' : undefined}
          style={{
            width: '100%', display: 'flex', alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'flex-start', gap: 6,
            textAlign: 'left', background: 'none', border: 'none',
            color: 'var(--orange)', fontSize: 11, fontWeight: 600,
            cursor: 'pointer', padding: 0,
          }}
        >
          <LogoutIcon />
          {!collapsed && 'Log out'}
        </button>
      </div>
    </div>
  );
}

function useCollapsedPref() {
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem('sidebar-collapsed') === 'true';
    } catch {
      return false;
    }
  });
  useEffect(() => {
    try {
      localStorage.setItem('sidebar-collapsed', String(collapsed));
    } catch {
      // localStorage unavailable (private mode, etc.) -- fine, just don't persist.
    }
  }, [collapsed]);
  return [collapsed, setCollapsed];
}

export default function Sidebar() {
  const isMobile = useMobile();
  const [manualCollapsed, setManualCollapsed] = useCollapsedPref();
  // Mobile always collapses to the icon rail regardless of the saved
  // preference -- there's no room to expand into on a narrow viewport.
  const collapsed = isMobile || manualCollapsed;
  const w = collapsed ? COLLAPSED_W : EXPANDED_W;
  const { role } = useAuth();
  const nav = navForRole(role);

  return (
    <div style={{
      width: w, flexShrink: 0, position: 'relative',
      background: 'linear-gradient(180deg, #131920 0%, #111519 100%)',
      borderRight: '1px solid rgba(255,255,255,0.06)',
      display: 'flex', flexDirection: 'column',
      padding: collapsed ? '0 6px' : '0 12px',
      transition: `width 0.28s ${EASE}, padding 0.28s ${EASE}`,
      overflow: 'hidden',
    }}>
      {!isMobile && (
        <CollapseToggle collapsed={collapsed} onClick={() => setManualCollapsed(c => !c)} />
      )}

      <div style={{
        padding: collapsed ? '18px 0' : '24px 6px 28px',
        borderBottom: '1px solid rgba(255,255,255,0.05)',
        marginBottom: 12,
        display: 'flex', justifyContent: 'center',
        transition: `padding 0.28s ${EASE}`,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: collapsed ? 0 : 8, transition: `gap 0.28s ${EASE}` }}>
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
          <div style={{
            opacity: collapsed ? 0 : 1,
            maxWidth: collapsed ? 0 : 140,
            overflow: 'hidden', whiteSpace: 'nowrap',
            transition: `opacity 0.18s ${collapsed ? '0s' : '0.12s'} ease, max-width 0.28s ${EASE}`,
          }}>
            <div style={{ fontFamily: 'Space Grotesk', fontWeight: 700, fontSize: 17, color: 'var(--orange)', letterSpacing: '0.04em' }}>PitchIQ</div>
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <div style={{
          fontSize: 9.5, fontWeight: 700, letterSpacing: '0.14em', color: 'var(--text-muted)',
          padding: '4px 14px 8px', textTransform: 'uppercase',
          opacity: collapsed ? 0 : 1,
          maxHeight: collapsed ? 0 : 20,
          overflow: 'hidden',
          transition: `opacity 0.18s ${collapsed ? '0s' : '0.12s'} ease, max-height 0.28s ${EASE}`,
        }}>
          Analytics
        </div>
        {nav.map(n => <NavItem key={n.path} {...n} collapsed={collapsed} />)}
      </div>

      <SidebarFooter collapsed={collapsed} />
    </div>
  );
}
