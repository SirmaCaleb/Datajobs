import styles from './StatsBar.module.css'

export default function StatsBar({ stats }) {
  if (!stats) return null
  return (
    <div className={styles.bar}>
      <div className={styles.inner}>
        <Stat label="Total jobs" value={stats.total_jobs?.toLocaleString()} />
        <Stat label="Remote" value={stats.remote_jobs?.toLocaleString()} accent="green" />
        <Stat label="Sources" value={stats.sources} />
        <Stat label="Added today" value={stats.posted_today?.toLocaleString()} accent="amber" />
        {stats.top_tools?.slice(0, 5).map(t => (
          <div key={t.tool} className={styles.tool}>
            <span className={styles.toolName}>{t.tool}</span>
            <span className={styles.toolCount}>{t.count}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function Stat({ label, value, accent }) {
  return (
    <div className={styles.stat}>
      <span className={`${styles.value} ${accent ? styles[accent] : ''}`}>{value ?? '—'}</span>
      <span className={styles.label}>{label}</span>
    </div>
  )
}
