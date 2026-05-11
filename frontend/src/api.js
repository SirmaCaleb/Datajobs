const BASE = '/api'

export async function fetchJobs({
  q = '', source = '', level = '', remote = null,
  location = '', tool = '', days = 30, page = 1, pageSize = 20
} = {}) {
  const params = new URLSearchParams()
  if (q) params.set('q', q)
  if (source) params.set('source', source)
  if (level) params.set('level', level)
  if (remote !== null) params.set('remote', remote)
  if (location) params.set('location', location)
  if (tool) params.set('tool', tool)
  params.set('days', days)
  params.set('page', page)
  params.set('page_size', pageSize)

  const res = await fetch(`${BASE}/jobs?${params}`)
  if (!res.ok) throw new Error(`API error ${res.status}`)
  return res.json()
}

export async function fetchStats() {
  const res = await fetch(`${BASE}/stats`)
  if (!res.ok) throw new Error(`API error ${res.status}`)
  return res.json()
}

export async function fetchSources() {
  const res = await fetch(`${BASE}/sources`)
  if (!res.ok) throw new Error(`API error ${res.status}`)
  return res.json()
}

export async function triggerScrape() {
  const res = await fetch(`${BASE}/scrape`, { method: 'POST' })
  if (!res.ok) throw new Error(`API error ${res.status}`)
  return res.json()
}
