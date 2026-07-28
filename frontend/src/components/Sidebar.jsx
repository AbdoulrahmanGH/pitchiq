import { NavLink } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { useAuth } from '../services/AuthProvider';
import Skeleton from './Skeleton';

const EXPANDED_W = 220;
const COLLAPSED_W = 68;
const EASE = 'cubic-bezier(0.4, 0, 0.2, 1)';

// Single-color outline icon set replacing the old per-item emoji -- same
// stroke language as the sidebar logo mark (thin strokes, rounded caps,
// currentColor so NavItem's active/hover color logic keeps working
// unchanged). Each is a bare <svg>; NavItem sizes and colors it.
const NAV_ICONS = {
  '/': (
    <svg viewBox="0 0 20 20" width="100%" height="100%" fill="none">
      <path d="M3 9.5L10 3.5L17 9.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M5 8V16.5H15V8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M8 16.5V12H12V16.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  '/players': (
    <svg viewBox="0 0 20 20" width="100%" height="100%" fill="none">
      <circle cx="10" cy="6.5" r="3.25" stroke="currentColor" strokeWidth="1.5" />
      <path d="M3.5 17C3.5 13.4101 6.41015 10.5 10 10.5C13.5899 10.5 16.5 13.4101 16.5 17" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  ),
  '/matches': (
    <svg viewBox="0 0 20 20" width="100%" height="100%" fill="none">
      <rect x="2.5" y="4" width="15" height="12" rx="2" stroke="currentColor" strokeWidth="1.5" />
      <path d="M10 4V16" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="10" cy="10" r="2.4" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  ),
  '/depth': (
    <svg viewBox="0 0 20 20" width="100%" height="100%" fill="none">
      <path d="M4 16.5V11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M10 16.5V6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M16 16.5V3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  ),
  '/my-notes': (
    <svg viewBox="0 0 20 20" width="100%" height="100%" fill="none">
      <path d="M5 3.5H12.5L15 6V16.5H5V3.5Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M7.5 9H12.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M7.5 12.5H12.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  ),
  '/assistant': (
    <svg viewBox="0 0 20 20" width="100%" height="100%" fill="none">
      <path d="M3 5.5C3 4.39543 3.89543 3.5 5 3.5H15C16.1046 3.5 17 4.39543 17 5.5V11.5C17 12.6046 16.1046 13.5 15 13.5H9L5.5 16.5V13.5H5C3.89543 13.5 3 12.6046 3 11.5V5.5Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  ),
  '/pipeline': (
    <svg viewBox="0 0 20 20" width="100%" height="100%" fill="none">
      <path d="M16 8.5C15.6 5.6 13.1 3.5 10 3.5C7.2 3.5 4.9 5.3 4.2 7.8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M4 3.5V7.8H8.3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M4 11.5C4.4 14.4 6.9 16.5 10 16.5C12.8 16.5 15.1 14.7 15.8 12.2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M16 16.5V12.2H11.7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  '/about': (
    <svg viewBox="0 0 20 20" width="100%" height="100%" fill="none">
      <circle cx="10" cy="10" r="6.75" stroke="currentColor" strokeWidth="1.5" />
      <path d="M10 9V14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="10" cy="6.4" r="0.9" fill="currentColor" />
    </svg>
  ),
};

const NAV = [
  { path: '/',          label: 'Dashboard'    },
  { path: '/players',   label: 'Players'      },
  { path: '/matches',   label: 'Matches'      },
  { path: '/depth',     label: 'Squad Depth'  },
  { path: '/my-notes',  label: 'My Notes'     },
  { path: '/assistant', label: 'Assistant'    },
  { path: '/pipeline',  label: 'Refresh Data' },
  { path: '/about',     label: 'About'        },
];

// sub matches v1's own framing of each role as a department, not a job
// title -- "Performance Staff" was v1's original label for analyst; coach
// gets the analogous "Performance & Medical" framing here. Purely display
// text -- the underlying role value driving routing/permissions is untouched.
const ROLE_LABELS = {
  analyst: { label: 'Analyst', sub: 'Performance Staff'   },
  coach:   { label: 'Coach',   sub: 'Performance & Medical' },
  scout:   { label: 'Scout',   sub: 'Recruitment'          },
};

// Nav visibility by role -- kept here rather than per-page route guards,
// since this step is only about which links show, not blocking direct
// navigation to a route.
const NAV_PATHS_BY_ROLE = {
  analyst: ['/', '/players', '/matches', '/depth', '/assistant', '/pipeline', '/about'],
  coach:   ['/', '/players', '/matches', '/depth', '/assistant'],
  scout:   ['/players', '/matches', '/depth', '/my-notes', '/assistant'],
};

function navForRole(role) {
  const allowedPaths = NAV_PATHS_BY_ROLE[role];
  // Unrecognized/unresolved role -- callers only reach here once roleLoading
  // is false, so this is a genuinely unknown role (fetch failed, logged
  // out, etc.), not "still figuring it out". Show nothing rather than
  // guess: an empty nav is safe, an unfiltered one leaks links a role
  // shouldn't see.
  return allowedPaths ? NAV.filter(n => allowedPaths.includes(n.path)) : [];
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

function NavItem({ path, label, collapsed }) {
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
            // Muted highlight: active state reads as a neutral, elevated
            // surface (bg-surface + a hairline border), not a glowing
            // orange fill -- the small left accent bar below is the only
            // place the brand orange still appears here.
            color: isActive ? 'var(--text-primary)' : hov ? 'var(--text-primary)' : 'var(--text-secondary)',
            background: isActive ? 'var(--bg-surface)' : hov ? 'rgba(255,255,255,0.04)' : 'transparent',
            border: `1px solid ${isActive ? 'var(--border-color)' : 'transparent'}`,
            transition: `background 0.18s ease, color 0.18s ease, border-color 0.18s ease, justify-content 0.28s ${EASE}, gap 0.28s ${EASE}, padding 0.28s ${EASE}`,
            fontSize: 13.5,
            fontWeight: isActive ? 600 : 400, position: 'relative',
          }}
        >
          {isActive && (
            <div style={{
              position: 'absolute', left: -1, top: '50%',
              transform: 'translateY(-50%)',
              width: 3, height: 18,
              background: 'var(--accent-orange)', borderRadius: '0 3px 3px 0',
            }} />
          )}
          <span style={{
            width: collapsed ? 18 : 14, height: collapsed ? 18 : 14,
            transition: `width 0.2s ${EASE}, height 0.2s ${EASE}`, flexShrink: 0,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            {NAV_ICONS[path]}
          </span>
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

// Skeleton stand-in for the nav list while role is still resolving --
// previously this window rendered the full, unfiltered NAV (every role's
// links) for a frame or two on every load/login, since role starts null
// and navForRole(null) used to fall back to "show everything". Never show
// the wrong nav, even briefly -- show a placeholder instead.
function NavSkeleton({ collapsed }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, padding: collapsed ? '4px 0' : '4px 14px' }}>
      {[0, 1, 2, 3, 4].map(i => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: collapsed ? 'center' : 'flex-start', gap: 11, padding: '9px 0' }}>
          <Skeleton width={collapsed ? 18 : 16} height={16} radius={4} />
          {!collapsed && <Skeleton width={90 - i * 8} height={12} />}
        </div>
      ))}
    </div>
  );
}

// The explicit, always-visible collapse/expand control. Sits half-off the
// sidebar's right edge so it reads as a distinct affordance rather than
// blending into the rail. Its icon is an animated hamburger <-> X: three
// bars while expanded (click to collapse to the icon rail), morphing into
// an X once collapsed (click to expand back).
function CollapseToggle({ collapsed, onClick }) {
  const [hov, setHov] = useState(false);
  const barW = 12, barH = 1.6, gap = 3.4;
  const stackH = barH * 3 + gap * 2;
  const mid = stackH / 2 - barH / 2;
  const open = !collapsed;
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      style={{
        position: 'absolute', top: 26, right: -12,
        width: 24, height: 24, borderRadius: '50%',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: hov ? 'var(--accent-orange)' : '#181B27',
        border: '1px solid rgba(255,255,255,0.10)',
        color: hov ? '#fff' : 'var(--text-secondary)',
        cursor: 'pointer', zIndex: 5, padding: 0,
        boxShadow: '0 6px 16px rgba(0,0,0,0.45)',
        transition: `background 0.15s ease, color 0.15s ease`,
      }}
    >
      <span style={{ position: 'relative', width: barW, height: stackH, display: 'block' }}>
        {[0, 1, 2].map(i => {
          const closedStyle = i === 1
            ? { top: mid, opacity: 0, transform: 'scaleX(0)' }
            : { top: mid, transform: `rotate(${i === 0 ? 45 : -45}deg)` };
          const openStyle = { top: i * (barH + gap), transform: 'none', opacity: 1 };
          const s = open ? openStyle : closedStyle;
          return (
            <span
              key={i}
              style={{
                position: 'absolute', left: 0, width: barW, height: barH, borderRadius: barH / 2,
                background: 'currentColor', transformOrigin: 'center',
                transition: `transform 0.32s ${EASE}, opacity 0.24s ease, top 0.32s ${EASE}`,
                ...s,
              }}
            />
          );
        })}
      </span>
    </button>
  );
}

// PitchIQ icon mark -- inline SVG per the redesign spec (icon group only;
// the wordmark next to it is real text, not SVG <text>, so it stays crisp
// and lets the font stack's actual loaded font drive its own metrics).
// Sidebar-header-only: no second copy anywhere else in the app.
function PitchIQLogo({ size = 28 }) {
  return (
    <svg viewBox="0 0 36 36" width={size} height={size} fill="none" style={{ flexShrink: 0 }}>
      <defs>
        <linearGradient id="pitchiq-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#FF6B35" />
          <stop offset="100%" stopColor="#FF3E00" />
        </linearGradient>
        <filter id="pitchiq-glow" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="1.5" result="blur" />
          <feComposite in="SourceGraphic" in2="blur" operator="over" />
        </filter>
      </defs>
      <rect x="0" y="0" width="36" height="36" rx="10" fill="#141824" stroke="#23293A" strokeWidth="1.5" />
      <circle cx="18" cy="18" r="10" stroke="#94A3B8" strokeWidth="2" strokeDasharray="24 8" strokeLinecap="round" fill="none" opacity="0.8" />
      <circle cx="18" cy="18" r="3" fill="#94A3B8" opacity="0.5" />
      <path d="M14 22 L19 17 L22 20 L28 12" stroke="url(#pitchiq-gradient)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" filter="url(#pitchiq-glow)" />
      <path d="M25 12 H28 V15" stroke="#FF6B35" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
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
  const { session, role, roleLoading, signOut } = useAuth();

  if (!session) {
    return (
      <div style={{ marginTop: 'auto', padding: collapsed ? '16px 0 20px' : '20px 6px 24px' }}>
        <div style={{
          borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: 14,
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

  return (
    <div style={{ marginTop: 'auto', padding: collapsed ? '16px 0 20px' : '20px 6px 24px' }}>
      <div style={{ borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: 14 }}>

        <div style={{
          display: 'flex', alignItems: 'center',
          justifyContent: collapsed ? 'center' : 'flex-start',
          gap: 9, marginBottom: 10,
        }}
        title={collapsed ? `${roleInfo.label} · ${session.user.email}` : undefined}
        >
          {collapsed ? (
            <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--accent-orange)', flexShrink: 0 }} />
          ) : roleLoading ? (
            <div style={{ flex: 1, minWidth: 0 }}>
              <Skeleton width={70} height={11} style={{ marginBottom: 6 }} />
              <Skeleton width={120} height={10} />
            </div>
          ) : (
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>
                {roleInfo.label}{roleInfo.sub ? <span style={{ color: 'var(--text-secondary)', fontWeight: 400 }}> · {roleInfo.sub}</span> : null}
              </div>
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
  const { role, roleLoading } = useAuth();
  const nav = navForRole(role);

  return (
    <div style={{
      width: w, flexShrink: 0, position: 'relative',
      background: 'linear-gradient(180deg, #12151f 0%, #0d0f17 100%)',
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
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        marginBottom: 12,
        display: 'flex', justifyContent: 'center',
        transition: `padding 0.28s ${EASE}`,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: collapsed ? 0 : 8, transition: `gap 0.28s ${EASE}` }}>
          <PitchIQLogo size={28} />
          <div style={{
            opacity: collapsed ? 0 : 1,
            maxWidth: collapsed ? 0 : 140,
            overflow: 'hidden', whiteSpace: 'nowrap',
            transition: `opacity 0.18s ${collapsed ? '0s' : '0.12s'} ease, max-width 0.28s ${EASE}`,
          }}>
            <div style={{ fontFamily: 'Space Grotesk', fontWeight: 700, fontSize: 17, letterSpacing: '0.02em' }}>
              <span style={{ color: 'var(--text-primary)' }}>Pitch</span><span style={{ color: 'var(--accent-orange)', fontWeight: 800 }}>IQ</span>
            </div>
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
        {roleLoading
          ? <NavSkeleton collapsed={collapsed} />
          : nav.map(n => <NavItem key={n.path} {...n} collapsed={collapsed} />)
        }
      </div>

      <SidebarFooter collapsed={collapsed} />
    </div>
  );
}
