import styles from './Sidebar.module.css'

const TOOLS = ['Python', 'SQL', 'Tableau', 'Power BI', 'R', 'Excel', 'Looker', 'dbt', 'Spark', 'BigQuery', 'Snowflake', 'Airflow']
const LOCATIONS = ['', 'Nairobi', 'Kenya', 'Africa', 'London', 'New York', 'Remote']

export default function Sidebar({ filters, sources, stats, onChange }) {
  return (
    <aside className={styles.sidebar}>
      {/* Sources */}
      <section className={styles.section}>
        <div className={styles.sectionTitle}>Sources</div>
        <div className={styles.sourceList}>
          <button
            className={`${styles.sourceItem} ${filters.source === '' ? styles.activeSource : ''}`}
            onClick={() => onChange('source', '')}
          >
            <span>All sources</span>
            <span className={styles.count}>{stats?.total_jobs ?? ''}</span>
          </button>
          {sources.map(s => (
            <button
              key={s.source}
              className={`${styles.sourceItem} ${filters.source === s.source.toLowerCase() ? styles.activeSource : ''}`}
              onClick={() => onChange('source', filters.source === s.source.toLowerCase() ? '' : s.source.toLowerCase())}
            >
              <span>{s.source}</span>
              <span className={styles.count}>{s.count}</span>
            </button>
          ))}
        </div>
      </section>

      {/* Location */}
      <section className={styles.section}>
        <div className={styles.sectionTitle}>Location</div>
        <div className={styles.locationList}>
          {LOCATIONS.map(loc => (
            <button
              key={loc || 'all'}
              className={`${styles.locBtn} ${filters.location === loc ? styles.activeSource : ''}`}
              onClick={() => onChange('location', filters.location === loc ? '' : loc)}
            >
              {loc || 'Anywhere'}
            </button>
          ))}
        </div>
      </section>

      {/* Tools */}
      <section className={styles.section}>
        <div className={styles.sectionTitle}>Tool / Skill</div>
        <div className={styles.toolGrid}>
          {TOOLS.map(t => (
            <button
              key={t}
              className={`${styles.toolBtn} ${filters.tool === t ? styles.activeSource : ''}`}
              onClick={() => onChange('tool', filters.tool === t ? '' : t)}
            >
              {t}
            </button>
          ))}
        </div>
      </section>

      {/* Date range */}
      <section className={styles.section}>
        <div className={styles.sectionTitle}>Posted within</div>
        {[7, 14, 30, 90].map(d => (
          <button
            key={d}
            className={`${styles.locBtn} ${filters.days === d ? styles.activeSource : ''}`}
            onClick={() => onChange('days', d)}
          >
            {d} days
          </button>
        ))}
      </section>

      {/* Top tools from stats */}
      {stats?.top_tools?.length > 0 && (
        <section className={styles.section}>
          <div className={styles.sectionTitle}>Trending skills</div>
          {stats.top_tools.slice(0, 8).map(t => (
            <div key={t.tool} className={styles.trendRow}>
              <span className={styles.trendTool}>{t.tool}</span>
              <div className={styles.trendBar}>
                <div
                  className={styles.trendFill}
                  style={{ width: `${Math.min(100, (t.count / (stats.top_tools[0]?.count || 1)) * 100)}%` }}
                />
              </div>
              <span className={styles.trendCount}>{t.count}</span>
            </div>
          ))}
        </section>
      )}
    </aside>
  )
}
