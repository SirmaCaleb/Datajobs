import styles from './JobCard.module.css'

export default function JobCard({ job, sourceColor, selected, onClick }) {
  const tools = Array.isArray(job.tools) ? job.tools : []

  return (
    <div
      className={`${styles.card} ${selected ? styles.selected : ''}`}
      onClick={onClick}
    >
      {/* Top row */}
      <div className={styles.top}>
        <div className={styles.titleRow}>
          <h3 className={styles.title}>{job.title}</h3>
          <span
            className={styles.sourceBadge}
            style={{ '--badge-color': sourceColor }}
          >
            {job.source}
          </span>
        </div>
        <div className={styles.company}>
          {job.company || 'Company not listed'}
          {job.location && <span className={styles.sep}>·</span>}
          {job.location && <span className={styles.location}>{job.location}</span>}
        </div>
      </div>

      {/* Meta pills */}
      <div className={styles.meta}>
        {job.experience && <span className={styles.pill + ' ' + styles.pillExp}>{job.experience}</span>}
        {job.remote && <span className={styles.pill + ' ' + styles.pillRemote}>Remote</span>}
        {job.salary && <span className={styles.pill}>{job.salary}</span>}
        {job.urgent && <span className={styles.pill + ' ' + styles.pillUrgent}>Closing soon</span>}
      </div>

      {/* Description — only when selected */}
      {selected && job.description && (
        <p className={styles.description}>{job.description}</p>
      )}

      {/* Tools */}
      {tools.length > 0 && (
        <div className={styles.tools}>
          {tools.slice(0, 8).map(t => (
            <span key={t} className={styles.toolTag}>{t}</span>
          ))}
        </div>
      )}

      {/* Footer */}
      <div className={styles.footer}>
        <div className={styles.footerLeft}>
          <span className={styles.time}>{job.posted_human || 'Recently posted'}</span>
          {job.deadline && (
            <span className={styles.deadline}>· Deadline: {job.deadline}</span>
          )}
        </div>
        {job.url ? (
          <a
            href={job.url}
            target="_blank"
            rel="noopener noreferrer"
            className={styles.applyBtn}
            onClick={e => e.stopPropagation()}
          >
            Apply ↗
          </a>
        ) : (
          <button className={styles.applyBtn} disabled>No link</button>
        )}
      </div>
    </div>
  )
}
