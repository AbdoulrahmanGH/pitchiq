import { NavLink } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { useAuth } from '../services/AuthProvider';
import Skeleton from './Skeleton';

const EXPANDED_W = 220;
const COLLAPSED_W = 68;
const EASE = 'cubic-bezier(0.4, 0, 0.2, 1)';

const NAV = [
  { path: '/',          emoji: '🏠', label: 'Dashboard'    },
  { path: '/players',   emoji: '👤', label: 'Players'      },
  { path: '/matches',   emoji: '⚽', label: 'Matches'      },
  { path: '/depth',     emoji: '📊', label: 'Squad Depth'  },
  { path: '/my-notes',  emoji: '📝', label: 'My Notes'     },
  { path: '/assistant', emoji: '💬', label: 'Assistant'    },
  { path: '/pipeline',  emoji: '🛠️', label: 'Refresh Data' },
  { path: '/about',     emoji: '📖', label: 'About'        },
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

// Chevron toggle: the explicit, always-visible collapse/expand control.
// Sits half-off the sidebar's right edge so it reads as a distinct
// affordance rather than blending into the rail.
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
        position: 'absolute', top: 26, right: -12,
        width: 24, height: 24, borderRadius: '50%',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: hov ? 'var(--orange)' : '#181B27',
        border: '1px solid rgba(255,255,255,0.10)',
        color: hov ? '#fff' : 'var(--text-secondary)',
        cursor: 'pointer', zIndex: 5, padding: 0,
        boxShadow: '0 6px 16px rgba(0,0,0,0.45)',
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

// Brand mark: an orange square containing three bars that morph into an X
// when the sidebar is collapsed -- an animated hamburger glyph rather than
// a static icon, doubling as the sidebar's brand identity. Clickable when a
// toggle handler is supplied (top logo row); purely decorative in the
// footer (smaller, non-interactive, echoes the brand instead of acting as
// a second control).
function BrandMark({ size = 28, open = true, onClick }) {
  const barW = size * 0.5;
  const barH = Math.max(1.4, size * 0.07);
  const gap = size * 0.16;
  const stackH = barH * 3 + gap * 2;
  const Tag = onClick ? 'button' : 'div';
  return (
    <Tag
      onClick={onClick}
      title={onClick ? (open ? 'Collapse sidebar' : 'Expand sidebar') : undefined}
      aria-label={onClick ? (open ? 'Collapse sidebar' : 'Expand sidebar') : undefined}
      style={{
        width: size, height: size, borderRadius: size * 0.25, flexShrink: 0,
        background: 'linear-gradient(135deg, #FF6B35, #c94a1a)',
        border: 'none', padding: 0, cursor: onClick ? 'pointer' : 'default',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
    >
      <span style={{ position: 'relative', width: barW, height: stackH, display: 'block' }}>
        {[0, 1, 2].map(i => {
          const mid = stackH / 2 - barH / 2;
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
                background: '#fff', transformOrigin: 'center',
                transition: `transform 0.32s ${EASE}, opacity 0.24s ease, top 0.32s ${EASE}`,
                ...s,
              }}
            />
          );
        })}
      </span>
    </Tag>
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

        {/* Brand signature -- mark + wordmark, same identity as the top
            logo row, restated in the footer per the redesign spec. */}
        <div style={{
          display: 'flex', alignItems: 'center',
          justifyContent: collapsed ? 'center' : 'flex-start',
          gap: 8, marginBottom: 14,
        }}>
          <BrandMark size={20} open />
          {!collapsed && (
            <span style={{ fontFamily: 'Space Grotesk', fontWeight: 700, fontSize: 13, color: 'var(--orange)', letterSpacing: '0.03em' }}>
              PitchIQ
            </span>
          )}
        </div>

        <div style={{
          display: 'flex', alignItems: 'center',
          justifyContent: collapsed ? 'center' : 'flex-start',
          gap: 9, marginBottom: 10,
        }}
        title={collapsed ? `${roleInfo.label} · ${session.user.email}` : undefined}
        >
          {collapsed ? (
            <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--orange)', flexShrink: 0 }} />
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
          <BrandMark
            size={28}
            open={!collapsed}
            onClick={isMobile ? undefined : () => setManualCollapsed(c => !c)}
          />
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
        {roleLoading
          ? <NavSkeleton collapsed={collapsed} />
          : nav.map(n => <NavItem key={n.path} {...n} collapsed={collapsed} />)
        }
      </div>

      <SidebarFooter collapsed={collapsed} />
    </div>
  );
}
