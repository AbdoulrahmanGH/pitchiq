const ACC = '#FF6B35';

const ARCH_STEPS = [
  { label: 'Raw JSON', sub: 'StatsBomb-inspired format' },
  { label: 'pipeline.py', sub: 'extract → transform → load' },
  { label: 'PostgreSQL / Supabase', sub: 'club-owned storage' },
  { label: 'FastAPI on GCP Cloud Run', sub: 'API layer' },
  { label: 'React on Netlify', sub: 'dashboard' },
  { label: 'BigQuery', sub: 'analytical warehouse' },
];

const TECH_CHOICES = [
  { name: 'pandas', reason: 'for transformation — straightforward for tabular data reshaping, and the skill most data engineers on football club teams actually use' },
  { name: 'Supabase', reason: 'over a self-managed Postgres, faster to set up without sacrificing SQL access or ownership' },
  { name: 'FastAPI', reason: 'over Django/Flask — async by default, automatic OpenAPI docs, Pydantic validation out of the box' },
  { name: 'GCP Cloud Run', reason: 'over a VM — no server management, scales to zero when idle' },
  { name: 'BigQuery', reason: 'for the analytical layer columnar storage makes window function queries across large datasets significantly faster than running them on the transactional database' },
];

const LIMITATIONS = [
  'Player data is simulated. The pipeline architecture is provider-agnostic but the extract layer currently reads from a local JSON file, not a live API',
  'No authentication on any endpoint. This is an MVP adding auth would be the first production requirement',
  'The fatigue risk thresholds (400 minutes, 40 avg sprints) are hardcoded. In production these would be configurable per club',
  'BigQuery load is manual. A scheduled Cloud Function or Airflow DAG would automate this in a real setup',
];

const BQ_QUERIES = [
  {
    src: '/bigquery-query1.png',
    title: 'Player Distance Rankings & Season Totals by Match',
    caption: '— RANK() and SUM() OVER to rank players by distance within each match and calculate season-wide totals',
  },
  {
    src: '/bigquery-query2.png',
    title: 'Player Fatigue & Performance Trend Analysis',
    caption: '— Rolling 3-match averages using ROWS BETWEEN 2 PRECEDING AND CURRENT ROW to track distance, sprint, and xG trends per player over time',
  },
];

const LINKS = [
  { label: 'API', href: 'https://pitchiq-backend-787059661234.europe-west1.run.app' },
  { label: 'API Docs', href: 'https://pitchiq-backend-787059661234.europe-west1.run.app/docs' },
  { label: 'GitHub', href: 'https://github.com/AbdoulrahmanGH/pitchiq/' },
];

function Section({ title, children }) {
  return (
    <div style={{ marginBottom: 32 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 18 }}>
        <div style={{ width: 3, height: 20, background: ACC, borderRadius: 2, flexShrink: 0 }} />
        <h2 style={{ fontFamily: 'Space Grotesk', fontSize: 16, fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>{title}</h2>
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
      padding: '24px 28px',
      boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
      ...style,
    }}>
      {children}
    </div>
  );
}

export default function About() {
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', padding: '0 20px', minHeight: 60, borderBottom: '1px solid rgba(255,255,255,0.05)', background: 'rgba(13,17,23,0.7)', backdropFilter: 'blur(12px)', flexShrink: 0 }}>
        <div>
          <div style={{ fontFamily: 'Space Grotesk', fontSize: 18, fontWeight: 600 }}>About PitchIQ</div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>A football squad analytics platform</div>
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '32px 20px 60px' }}>
        <div style={{ maxWidth: 900, margin: '0 auto' }}>

          <Section title="Why this exists">
            <Card>
              <p style={{ fontSize: 14, lineHeight: 1.75, color: 'var(--text-secondary)', margin: '0 0 16px' }}>
                I started looking into how professional football clubs actually handle performance data, not the glamorous AI stuff, but the infrastructure underneath it. What I found was that most clubs are essentially renting their own data. It lives in vendor tools, gets built by analysts who eventually leave, and the club starts from scratch every season.
              </p>
              <p style={{ fontSize: 14, lineHeight: 1.75, color: 'var(--text-secondary)', margin: 0 }}>
                As a developer, that felt like a solvable problem. So I built PitchIQ to see what a club-owned alternative could look like.
              </p>
            </Card>
          </Section>

          <Section title="What it does">
            <Card>
              <p style={{ fontSize: 14, lineHeight: 1.75, color: 'var(--text-secondary)', margin: 0 }}>
                PitchIQ ingests raw match performance data from external providers (simulated in StatsBomb JSON format), runs it through a Python ETL pipeline, stores it in a PostgreSQL database the club controls, and serves it through a FastAPI analytics layer. The data persists. The queries accumulate. The knowledge stays.
              </p>
            </Card>
          </Section>

          <Section title="Architecture">
            <Card style={{ padding: '28px 32px' }}>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 0 }}>
                {ARCH_STEPS.map((step, i) => (
                  <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', width: '100%' }}>
                    <div style={{
                      display: 'flex', alignItems: 'center', gap: 14,
                      background: 'rgba(255,255,255,0.03)',
                      border: '1px solid rgba(255,255,255,0.07)',
                      borderRadius: 10,
                      padding: '12px 18px',
                      marginLeft: i * 24,
                    }}>
                      <div style={{ width: 8, height: 8, borderRadius: '50%', background: ACC, flexShrink: 0, boxShadow: `0 0 8px ${ACC}88` }} />
                      <div>
                        <div style={{ fontFamily: 'Space Grotesk', fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{step.label}</div>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{step.sub}</div>
                      </div>
                    </div>
                    {i < ARCH_STEPS.length - 1 && (
                      <div style={{ marginLeft: i * 24 + 30, display: 'flex', flexDirection: 'column', alignItems: 'center', width: 2, gap: 0 }}>
                        <div style={{ width: 1, height: 10, background: `linear-gradient(180deg, ${ACC}44, ${ACC})` }} />
                        <div style={{ width: 0, height: 0, borderLeft: '4px solid transparent', borderRight: '4px solid transparent', borderTop: `6px solid ${ACC}` }} />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          </Section>

          <Section title="Why these tech choices">
            <Card>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                {TECH_CHOICES.map(({ name, reason }) => (
                  <div key={name} style={{ display: 'flex', gap: 14, alignItems: 'flex-start' }}>
                    <div style={{ flexShrink: 0, marginTop: 3, width: 6, height: 6, borderRadius: '50%', background: ACC }} />
                    <div style={{ fontSize: 13.5, lineHeight: 1.65, color: 'var(--text-secondary)' }}>
                      <span style={{ fontFamily: 'Space Grotesk', fontWeight: 600, color: 'var(--text-primary)' }}>{name}</span>
                      {' '}{reason}
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </Section>

          <Section title="BigQuery Window Function Queries">
            <Card style={{ marginBottom: 16 }}>
              <p style={{ fontSize: 13.5, lineHeight: 1.7, color: 'var(--text-secondary)', margin: '0 0 24px' }}>
                Match and player data is loaded into BigQuery for long-term analytical queries. Two window function queries are implemented:
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 28 }}>
                {BQ_QUERIES.map(({ src, title, caption }) => (
                  <div key={src}>
                    <img
                      src={src}
                      alt={title}
                      style={{
                        width: '100%',
                        borderRadius: 10,
                        border: '1px solid rgba(255,255,255,0.08)',
                        display: 'block',
                        marginBottom: 10,
                      }}
                    />
                    <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                      <span style={{ fontFamily: 'Space Grotesk', fontWeight: 600, color: 'var(--text-primary)' }}>{title}</span>
                      <br />{caption}
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </Section>

          <Section title="Known limitations">
            <Card>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                {LIMITATIONS.map((item, i) => (
                  <div key={i} style={{ display: 'flex', gap: 14, alignItems: 'flex-start' }}>
                    <div style={{ flexShrink: 0, marginTop: 4, width: 6, height: 6, borderRadius: '50%', background: 'var(--text-muted)' }} />
                    <div style={{ fontSize: 13.5, lineHeight: 1.65, color: 'var(--text-secondary)' }}>{item}</div>
                  </div>
                ))}
              </div>
            </Card>
          </Section>

          <Section title="Links">
            <Card>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {LINKS.map(({ label, href }) => (
                  <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', color: 'var(--text-muted)', minWidth: 72 }}>{label.toUpperCase()}</div>
                    <a
                      href={href}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        fontSize: 13, color: ACC, textDecoration: 'none', fontFamily: 'Space Grotesk',
                        borderBottom: '1px solid transparent',
                        transition: 'border-color 0.15s',
                      }}
                      onMouseEnter={e => e.currentTarget.style.borderBottomColor = ACC}
                      onMouseLeave={e => e.currentTarget.style.borderBottomColor = 'transparent'}
                    >
                      {href}
                    </a>
                  </div>
                ))}
              </div>
            </Card>
          </Section>

        </div>
      </div>
    </div>
  );
}
