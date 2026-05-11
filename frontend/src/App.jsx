import { useState, useEffect, useCallback, useRef } from 'react'
import { fetchJobs, fetchStats, fetchSources, triggerScrape } from './api.js'
import JobCard from './components/JobCard.jsx'
import StatsBar from './components/StatsBar.jsx'
import Sidebar from './components/Sidebar.jsx'
import styles from './App.module.css'

const SOURCE_COLORS = {
  Reddit: '#ff6b35',
  LinkedIn: '#4a8fff',
  Indeed: '#5cb85c',
  Glassdoor: '#00a67e',
  RemoteOK: '#9b7fe8',
  'We Work Remotely': '#f5a623',
  Adzuna: '#e06edc',
  GitHub: '#aaaaaa',
}

export default function App() {
  const [jobs, setJobs] = useState([])
  const [stats, setStats] = useState(null)
  const [sources, setSources] = useState([])
  const [loading, setLoading] = useState(true)
  const [scraping, setScraping] = useState(false)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [selectedJob, setSelectedJob] = useState(null)
  const [error, setError] = useState('')

  const [filters, setFilters] = useState({
    q: '',
    source: '',
    level: '',
    remote: null,
    location: '',
    tool: '',
    days: 30,
  })

  const debounceRef = useRef(null)

  const loadJobs = useCallback(async (f = filters, p = page) => {
    setLoading(true)
    setError('')
    try {
      const data = await fetchJobs({ ...f, page: p, pageSize: 20 })
      setJobs(data.jobs)
      setTotal(data.total)
    } catch (e) {
      setError('Could not connect to API. Is the server running? (uvicorn api.server:app)')
    } finally {
      setLoading(false)
    }
  }, [filters, page])

  const loadMeta = async () => {
    try {
      const [s, src] = await Promise.all([fetchStats(), fetchSources()])
      setStats(s)
      setSources(src)
    } catch (_) {}
  }

  useEffect(() => {
    loadJobs()
    loadMeta()
  }, [])

  const handleFilterChange = (key, value) => {
    const next = { ...filters, [key]: value }
    setFilters(next)
    setPage(1)
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => loadJobs(next, 1), 400)
  }

  const handleScrape = async () => {
    setScraping(true)
    try {
      await triggerScrape()
      setTimeout(() => { loadJobs(); loadMeta(); setScraping(false) }, 3000)
    } catch (e) {
      setScraping(false)
    }
  }

  const handlePageChange = (p) => {
    setPage(p)
    loadJobs(filters, p)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const totalPages = Math.ceil(total / 20)

  return (
    <div className={styles.layout}>
      {/* Header */}
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <div className={styles.brand}>
            <span className={styles.brandMark}>◎</span>
            <div>
              <div className={styles.brandName}>DataJobs</div>
              <div className={styles.brandSub}>// multi-source · real-time · data careers</div>
            </div>
          </div>
          <div className={styles.headerActions}>
            <div className={styles.sourceChips}>
              {Object.entries(SOURCE_COLORS).map(([name, color]) => (
                <span key={name} className={styles.sourceDot} style={{ '--dot': color }} title={name}>
                  <span className={styles.dot} />
                  <span className={styles.dotLabel}>{name}</span>
                </span>
              ))}
            </div>
            <button
              className={`${styles.scrapeBtn} ${scraping ? styles.scrapeBtnBusy : ''}`}
              onClick={handleScrape}
              disabled={scraping}
            >
              {scraping ? '⟳ Scraping...' : '↻ Refresh'}
            </button>
          </div>
        </div>
      </header>

      {/* Stats bar */}
      {stats && <StatsBar stats={stats} />}

      <div className={styles.body}>
        {/* Sidebar / filters */}
        <Sidebar
          filters={filters}
          sources={sources}
          stats={stats}
          onChange={handleFilterChange}
        />

        {/* Main content */}
        <main className={styles.main}>
          {/* Search */}
          <div className={styles.searchRow}>
            <div className={styles.searchWrap}>
              <span className={styles.searchIcon}>⌕</span>
              <input
                className={styles.searchInput}
                type="text"
                placeholder="Search jobs, companies, tools..."
                value={filters.q}
                onChange={e => handleFilterChange('q', e.target.value)}
              />
            </div>
            <div className={styles.resultCount}>
              {loading ? 'Loading...' : `${total.toLocaleString()} jobs`}
            </div>
          </div>

          {/* Quick filters */}
          <div className={styles.quickFilters}>
            {['', 'entry', 'mid', 'senior'].map(lvl => (
              <button
                key={lvl}
                className={`${styles.chip} ${filters.level === lvl ? styles.chipActive : ''}`}
                onClick={() => handleFilterChange('level', lvl)}
              >
                {lvl === '' ? 'All levels' : lvl === 'entry' ? 'Entry' : lvl === 'mid' ? 'Mid' : 'Senior'}
              </button>
            ))}
            <button
              className={`${styles.chip} ${filters.remote === true ? styles.chipActive : ''}`}
              onClick={() => handleFilterChange('remote', filters.remote === true ? null : true)}
            >
              Remote only
            </button>
            <button
              className={`${styles.chip} ${filters.days === 7 ? styles.chipActive : ''}`}
              onClick={() => handleFilterChange('days', filters.days === 7 ? 30 : 7)}
            >
              Last 7 days
            </button>
          </div>

          {/* Error */}
          {error && (
            <div className={styles.error}>
              <strong>⚠ API offline</strong><br />
              {error}
            </div>
          )}

          {/* Job list */}
          {loading ? (
            <div className={styles.loading}>
              {[...Array(5)].map((_, i) => <div key={i} className={styles.skeleton} />)}
            </div>
          ) : jobs.length === 0 ? (
            <div className={styles.empty}>
              <div className={styles.emptyIcon}>◎</div>
              <p>No jobs found. Try different filters or run a scrape.</p>
            </div>
          ) : (
            <>
              <div className={styles.jobList}>
                {jobs.map(job => (
                  <JobCard
                    key={job.id}
                    job={job}
                    sourceColor={SOURCE_COLORS[job.source] || '#888'}
                    selected={selectedJob?.id === job.id}
                    onClick={() => setSelectedJob(selectedJob?.id === job.id ? null : job)}
                  />
                ))}
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className={styles.pagination}>
                  <button
                    className={styles.pageBtn}
                    onClick={() => handlePageChange(page - 1)}
                    disabled={page === 1}
                  >← Prev</button>
                  <span className={styles.pageInfo}>Page {page} of {totalPages}</span>
                  <button
                    className={styles.pageBtn}
                    onClick={() => handlePageChange(page + 1)}
                    disabled={page === totalPages}
                  >Next →</button>
                </div>
              )}
            </>
          )}
        </main>
      </div>
    </div>
  )
}
