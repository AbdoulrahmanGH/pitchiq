import { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../services/AuthProvider';
import { getPipelineStatus, triggerPipelineRefresh } from '../services/api';
import Skeleton from '../components/Skeleton';

const ACC = '#FF5A1F';

const STATUS_STYLE = {
  succeeded: { label: 'SUCCEEDED', color: 'var(--green)', bg: 'var(--green-dim)', border: 'rgba(63,185,80,0.2)' },
  failed:    { label: 'FAILED',    color: 'var(--red)',   bg: 'var(--red-dim)',   border: 'rgba(248,81,73,0.2)' },
  running:   { label: 'RUNNING',   color: ACC,             bg: 'var(--orange-dim)', border: 'rgba(255,90,31,0.25)' },
  pending:   { label: 'PENDING',   color: 'var(--text-muted)', bg: 'rgba(255,255,255,0.05)', border: 'rgba(255,255,255,0.08)' },
};

function timeAgo(iso) {
  if (!iso) return null;
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins} min${mins === 1 ? '' : 's'} ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'} ago`;
  const days = Math.round(hours / 24);
  return `${days} day${days === 1 ? '' : 's'} ago`;
}

function formatAbs(iso) {
  if (!iso) return 'No data yet';
  return new Date(iso).toLocaleString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}

function formatDuration(seconds) {
  if (seconds == null) return '—';
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function Section({ title, children, right }) {
  return (
    <div style={{ marginBottom: 28 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
        <div style={{ width: 3, height: 18, background: ACC, borderRadius: 2, flexShrink: 0 }} />
        <div style={{ fontFamily: 'Space Grotesk', fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>{title}</div>
        {right && <div style={{ marginLeft: 'auto' }}>{right}</div>}
      </div>
      {children}
    </div>
  );
}

function Card({ children, style }) {
  return (
    <div style={{
      background: 'linear-gradient(145deg, #1C2333 0%, #161B22 100%)',
      border: '1px solid rgba(255,255,255,0.07)',
      borderRadius: 16,
      boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
      ...style,
    }}>
      {children}
    </div>
  );
}

function FreshnessCard({ label, iso }) {
  const fresh = iso && (Date.now() - new Date(iso).getTime()) < 60 * 60 * 1000;
  return (
    <Card style={{ flex: 1, padding: '22px 26px', position: 'relative', overflow: 'hidden' }}>
      <div style={{ position: 'absolute', top: -30, right: -30, width: 80, height: 80, background: `radial-gradient(circle, ${ACC}18 0%, transparent 70%)`, pointerEvents: 'none' }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <div style={{
          width: 7, height: 7, borderRadius: '50%',
          background: fresh ? 'var(--green)' : 'var(--text-muted)',
          boxShadow: fresh ? '0 0 6px var(--green)' : 'none',
        }} />
        <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-secondary)' }}>
          {label}
        </div>
      </div>
      <div style={{ fontFamily: 'Space Grotesk', fontSize: 26, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.5px' }}>
        {iso ? timeAgo(iso) : 'No data yet'}
      </div>
      <div style={{ fontSize: 11.5, color: 'var(--text-muted)', marginTop: 6, fontVariantNumeric: 'tabular-nums' }}>
        {formatAbs(iso)}
      </div>
    </Card>
  );
}

function RefreshButton({ onClick, refreshing }) {
  return (
    <button
      onClick={onClick}
      disabled={refreshing}
      style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '9px 18px', borderRadius: 9, border: 'none',
        background: refreshing ? 'rgba(255,90,31,0.25)' : ACC,
        color: refreshing ? 'var(--text-secondary)' : '#1a0f08',
        fontSize: 12.5, fontWeight: 700, letterSpacing: '0.02em',
        cursor: refreshing ? 'default' : 'pointer',
        transition: 'background 0.15s',
      }}
    >
      {refreshing ? (
        <>
          <span style={{
            width: 12, height: 12, borderRadius: '50%',
            border: '2px solid rgba(255,255,255,0.25)', borderTopColor: 'var(--text-primary)',
            animation: 'pipeline-spin 0.8s linear infinite',
          }} />
          Running pipeline…
        </>
      ) : (
        <>⟳ Refresh Data Now</>
      )}
    </button>
  );
}

function RunHistory({ runs }) {
  if (!runs || runs.length === 0) {
    return <div style={{ fontSize: 13, color: 'var(--text-muted)', padding: '20px 0' }}>No pipeline runs recorded yet.</div>;
  }
  return (
    <Card style={{ overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', padding: '10px 20px', borderBottom: '1px solid rgba(255,255,255,0.06)', background: 'rgba(0,0,0,0.15)' }}>
        <div style={{ width: 180, fontSize: 10, fontWeight: 700, letterSpacing: '0.1em', color: '#8B949E' }}>EXECUTION</div>
        <div style={{ width: 170, fontSize: 10, fontWeight: 700, letterSpacing: '0.1em', color: '#8B949E' }}>STARTED</div>
        <div style={{ width: 90, fontSize: 10, fontWeight: 700, letterSpacing: '0.1em', color: '#8B949E' }}>DURATION</div>
        <div style={{ width: 100, fontSize: 10, fontWeight: 700, letterSpacing: '0.1em', color: '#8B949E' }}>STATUS</div>
      </div>
      {runs.map((run, i) => {
        const st = STATUS_STYLE[run.status] || STATUS_STYLE.pending;
        return (
          <div key={run.id} style={{ display: 'flex', alignItems: 'center', padding: '12px 20px', borderBottom: i < runs.length - 1 ? '1px solid rgba(255,255,255,0.04)' : 'none' }}>
            <div style={{ width: 180, fontSize: 12, fontFamily: 'Space Grotesk', color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={run.id}>
              {run.id}
            </div>
            <div style={{ width: 170, fontSize: 11.5, color: 'var(--text-secondary)' }}>
              {run.start_time ? formatAbs(run.start_time) : (run.create_time ? formatAbs(run.create_time) : '—')}
            </div>
            <div style={{ width: 90, fontSize: 12, fontFamily: 'Space Grotesk', color: 'var(--text-secondary)', fontVariantNumeric: 'tabular-nums' }}>
              {formatDuration(run.duration_seconds)}
            </div>
            <div style={{ width: 100 }}>
              <span style={{
                fontSize: 9, fontWeight: 700, letterSpacing: '0.08em', padding: '3px 8px', borderRadius: 5,
                background: st.bg, color: st.color, border: `1px solid ${st.border}`,
                animation: run.status === 'running' ? 'pipeline-pulse 1.4s ease-in-out infinite' : 'none',
              }}>
                {st.label}
              </span>
            </div>
          </div>
        );
      })}
    </Card>
  );
}

const POLL_INTERVAL_MS = 4000;
const POLL_TIMEOUT_MS = 5 * 60 * 1000;

export default function Pipeline() {
  const { role } = useAuth();
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const pollRef = useRef(null);
  const knownRunIdRef = useRef(null);

  const load = useCallback(() => {
    return getPipelineStatus()
      .then(data => { setStatus(data); setError(null); return data; })
      .catch(e => setError(e.status === 403 ? 'forbidden' : 'Failed to load pipeline status.'));
  }, []);

  useEffect(() => {
    setLoading(true);
    load().finally(() => setLoading(false));
    return () => clearInterval(pollRef.current);
  }, [load]);

  const stopPolling = () => {
    clearInterval(pollRef.current);
    pollRef.current = null;
    setRefreshing(false);
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    knownRunIdRef.current = status?.recent_runs?.[0]?.id ?? null;
    const startedAt = Date.now();
    try {
      await triggerPipelineRefresh();
    } catch {
      setRefreshing(false);
      return;
    }

    pollRef.current = setInterval(async () => {
      if (Date.now() - startedAt > POLL_TIMEOUT_MS) {
        stopPolling();
        return;
      }
      const data = await load();
      if (!data) return;
      const latest = data.recent_runs?.[0];
      const isNewRun = latest && latest.id !== knownRunIdRef.current;
      if (isNewRun && (latest.status === 'succeeded' || latest.status === 'failed')) {
        stopPolling();
      }
    }, POLL_INTERVAL_MS);
  };

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <style>{`
        @keyframes pipeline-spin { to { transform: rotate(360deg); } }
        @keyframes pipeline-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
      `}</style>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 20px', minHeight: 60, borderBottom: '1px solid rgba(255,255,255,0.05)', background: 'rgba(13,17,23,0.7)', backdropFilter: 'blur(12px)', flexShrink: 0, gap: 8 }}>
        <div>
          <div style={{ fontFamily: 'Space Grotesk', fontSize: 18, fontWeight: 600 }}>Pipeline Visibility</div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>A behind-the-scenes look at how up to date your squad data is</div>
        </div>
        {role === 'analyst' && status && !error && (
          <RefreshButton onClick={handleRefresh} refreshing={refreshing} />
        )}
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '24px 20px 60px' }}>
        <div style={{ maxWidth: 900, margin: '0 auto' }}>

          {loading && (
            <div style={{ display: 'flex', gap: 18, marginBottom: 28 }}>
              {[0, 1].map(i => (
                <div key={i} style={{ flex: 1, background: 'linear-gradient(145deg, #1C2333 0%, #161B22 100%)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 16, padding: '22px 26px' }}>
                  <Skeleton width={100} height={11} style={{ marginBottom: 14 }} />
                  <Skeleton width={140} height={26} style={{ marginBottom: 8 }} />
                  <Skeleton width={180} height={12} />
                </div>
              ))}
            </div>
          )}

          {!loading && error === 'forbidden' && (
            <div style={{ padding: '20px 24px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 12, color: 'var(--text-secondary)', fontSize: 13.5 }}>
              This page is only available to Analyst accounts.
            </div>
          )}

          {!loading && error && error !== 'forbidden' && (
            <div style={{ padding: '16px 20px', background: 'var(--red-dim)', border: '1px solid rgba(248,81,73,0.2)', borderRadius: 12, color: 'var(--red)', fontSize: 13 }}>
              {error}
            </div>
          )}

          {!loading && !error && status && (
            <>
              <Section title="Data Freshness">
                <div style={{ display: 'flex', gap: 18 }}>
                  <FreshnessCard label="Current Data · Postgres" iso={status.current_data_updated_at} />
                  <FreshnessCard label="Analytics Warehouse · BigQuery" iso={status.analytics_warehouse_updated_at} />
                </div>
              </Section>

              <Section title="Run History">
                <RunHistory runs={status.recent_runs} />
              </Section>
            </>
          )}

        </div>
      </div>
    </div>
  );
}
