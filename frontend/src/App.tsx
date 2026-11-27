
import { useEffect, useState } from 'react'
import './App.css'
import Login from './Login'
import { apiRequest, apiPostRequest } from './api'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend as ChartLegend,
  ResponsiveContainer,
} from 'recharts'
interface Agent {
  id: number
  agent_uid: string
  name: string
  hostname: string
  os: string
  version: string
  status: string
  last_heartbeat: string | null
}

interface DashboardProcess {
  pid: number
  name: string
  status: string
  cpu_percent: number
  memory_rss: number
  create_time: number | null
  health_status: string
  health_reasons: string[]
}

interface DashboardOverview {
  agent: Agent
  metrics: {
    cpu_usage: number | null
    memory_usage: number | null
    disk_usage: number | null
    memory_total: number | null
    memory_available: number | null
    disk_total: number | null
    disk_free: number | null
    uptime_seconds: number | null
    recorded_at: string | null
  } | null
  processes: DashboardProcess[]
  process_count: number
}

interface ActivityLog {
  id: number
  agent_id: number
  event_type: string
  message: string
  created_at: string
}

interface ResourceMetric {
  id: number
  agent_id: number
  cpu_usage: number
  memory_usage: number
  memory_total: number
  memory_available: number
  disk_usage: number
  disk_total: number
  disk_free: number
  uptime_seconds: number
  recorded_at: string
}
interface WebsiteMonitorSession {
  id: number
  session_uid: string
  name: string
  agent_type: string
  status: string
  created_at: string
}

interface WebsiteMonitorCheck {
  id: number
  session_id: number
  url: string
  is_available: boolean
  status_code: number | null
  response_time_ms: number | null
  error_message: string | null
  checked_at: string
  created_at: string
}

function normalizeHealth(status: string): string {
  const normalized = status.toLowerCase()

  if (normalized === 'healthy' || normalized === 'warning' || normalized === 'critical') {
    return normalized
  }

  return 'unknown'
}

function formatBytesToGB(bytes: number): string {
  return `${(bytes / 1024 ** 3).toFixed(1)} GB`
}

function App() {
  const [activeNav, setActiveNav] = useState('Overview')
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('All')
  const [selectedProcess, setSelectedProcess] =
    useState<DashboardProcess | null>(null)

  const [agents, setAgents] = useState<Agent[]>([])
  const [selectedAgentId, setSelectedAgentId] = useState<number | null>(null)
  const [dashboard, setDashboard] = useState<DashboardOverview | null>(null)
  const [metricsHistory, setMetricsHistory] = useState<ResourceMetric[]>([])
  const [loadingMetricsHistory, setLoadingMetricsHistory] = useState(false)
  const [metricsHistoryError, setMetricsHistoryError] = useState('')
  const [activities, setActivities] = useState<ActivityLog[]>([])
  const [loadingActivity, setLoadingActivity] = useState(false)
  const [activityError, setActivityError] = useState('')
  const [monitorSessions, setMonitorSessions] =
  useState<WebsiteMonitorSession[]>([])
  const [selectedMonitorUid, setSelectedMonitorUid] = useState('')
  const [monitorHistory, setMonitorHistory] =
    useState<WebsiteMonitorCheck[]>([])
  const [loadingMonitor, setLoadingMonitor] = useState(false)
  const [monitorError, setMonitorError] = useState('')
  const [monitorActionLoading, setMonitorActionLoading] = useState(false)
  const [monitorActionError, setMonitorActionError] = useState('')
  const [monitorFormOpen, setMonitorFormOpen] = useState(false)
  const [monitorName, setMonitorName] = useState('')
  const [monitorUrl, setMonitorUrl] = useState('')
  const [monitorInterval, setMonitorInterval] = useState('60')
  const [creatingMonitor, setCreatingMonitor] = useState(false)
  const [createMonitorError, setCreateMonitorError] = useState('')
  const [monitorRefreshKey, setMonitorRefreshKey] = useState(0)
  const [loadingAgents, setLoadingAgents] = useState(false)
  const [loadingDashboard, setLoadingDashboard] = useState(false)
  const [dashboardError, setDashboardError] = useState('')

  const [refreshKey, setRefreshKey] = useState(0)

  const [token, setToken] = useState(
    () => sessionStorage.getItem('access_token') || '',
  )

  function handleLogin(accessToken: string) {
    sessionStorage.setItem('access_token', accessToken)
    setToken(accessToken)
  }

  function handleLogout() {
    sessionStorage.removeItem('access_token')
    setToken('')
    setAgents([])
    setSelectedAgentId(null)
    setDashboard(null)
  }

  async function handleCreateMonitor() {
    if (!token) return

    setCreateMonitorError('')

    const trimmedName = monitorName.trim()
    const trimmedUrl = monitorUrl.trim()
    const interval = Number(monitorInterval)

    if (!trimmedName) {
      setCreateMonitorError('Please enter a monitor name.')
      return
    }

    if (!/^https?:\/\/.+/i.test(trimmedUrl)) {
      setCreateMonitorError('Enter a valid URL starting with http:// or https://')
      return
    }

    if (!Number.isInteger(interval) || interval < 5 || interval > 3600) {
      setCreateMonitorError('Interval must be between 5 and 3600 seconds.')
      return
    }

    setCreatingMonitor(true)

    try {
      const createdSession = await apiPostRequest<WebsiteMonitorSession>(
        '/sessions',
        token,
        {
          name: trimmedName,
          agent_type: 'website_monitor',
          task_config: {
            url: trimmedUrl,
            interval_seconds: interval,
          },
        },
      )

      const startedSession = await apiPostRequest<WebsiteMonitorSession>(
        `/sessions/${createdSession.session_uid}/start`,
        token,
        {},
      )

      setMonitorSessions((current) => [
        startedSession,
        ...current.filter(
          (session) => session.session_uid !== startedSession.session_uid,
        ),
      ])
      setSelectedMonitorUid(startedSession.session_uid)
      setMonitorName('')
      setMonitorUrl('')
      setMonitorInterval('60')
      setMonitorFormOpen(false)
      setMonitorRefreshKey((current) => current + 1)
    } catch (error) {
      setCreateMonitorError(
        error instanceof Error ? error.message : 'Failed to create monitor.',
      )
    } finally {
      setCreatingMonitor(false)
    }
  }

  async function handleStopProcess() {
    if (
      !selectedProcess ||
      selectedAgentId === null ||
      selectedProcess.create_time === null
    ) {
      return
    }

    const confirmed = window.confirm(
      `Are you sure you want to stop "${selectedProcess.name}" (PID ${selectedProcess.pid})?`,
    )

    if (!confirmed) return

    try {
      const result = await apiPostRequest<{ command_uid: string }>(
        `/agents/${selectedAgentId}/commands/stop-process`,
        token,
        {
          pid: selectedProcess.pid,
          create_time: selectedProcess.create_time,
          process_name: selectedProcess.name,
        },
      )

      window.alert(
        `Stop request queued successfully.\nCommand ID: ${result.command_uid}`,
      )

      setRefreshKey((current) => current + 1)
    } catch (error) {
      window.alert(
        error instanceof Error
          ? error.message
          : 'Failed to queue stop request',
      )
    }
  }

  async function handleMonitorAction(action: 'start' | 'stop') {
    if (!token || !selectedMonitorUid) return

    setMonitorActionError('')
    setMonitorActionLoading(true)

    try {
      const updatedSession = await apiPostRequest<WebsiteMonitorSession>(
        `/sessions/${selectedMonitorUid}/${action}`,
        token,
        {},
      )

      setMonitorSessions((current) =>
        current.map((session) =>
          session.session_uid === updatedSession.session_uid
            ? updatedSession
            : session,
        ),
      )

      setMonitorRefreshKey((current) => current + 1)
    } catch (error) {
      setMonitorActionError(
        error instanceof Error
          ? error.message
          : `Failed to ${action} monitor.`,
      )
    } finally {
      setMonitorActionLoading(false)
    }
  }

  // Load agents belonging to the logged-in user.
  useEffect(() => {
    if (!token) {
      setAgents([])
      setSelectedAgentId(null)
      return
    }

    let cancelled = false

    async function loadAgents() {
      setLoadingAgents(true)

      try {
        const result = await apiRequest<Agent[]>('/dashboard/agents', token)

        if (!cancelled) {
          setAgents(result)
        }
      } catch (error) {
        if (!cancelled) {
          console.error('Failed to load agents:', error)
          setAgents([])
          setDashboardError(
            error instanceof Error ? error.message : 'Failed to load agents',
          )
        }
      } finally {
        if (!cancelled) {
          setLoadingAgents(false)
        }
      }
    }

    loadAgents()

    return () => {
      cancelled = true
    }
  }, [token])

  // Select the first agent automatically when agents are loaded.
  useEffect(() => {
    if (agents.length === 0) {
      setSelectedAgentId(null)
      return
    }

    setSelectedAgentId((current) => {
      const currentAgentExists = agents.some((agent) => agent.id === current)

      return currentAgentExists ? current : agents[0].id
    })
  }, [agents])

  // Load the selected agent's metrics and latest process snapshot.
  useEffect(() => {
    if (!token || selectedAgentId === null) {
      setDashboard(null)
      return
    }

    let cancelled = false

    async function loadDashboard() {
      setLoadingDashboard(true)
      setDashboardError('')
      setDashboard(null)

      try {
        const result = await apiRequest<DashboardOverview>(
          `/dashboard/overview/${selectedAgentId}`,
          token,
        )

        if (!cancelled) {
          setDashboard(result)
        }
      } catch (error) {
        if (!cancelled) {
          console.error('Failed to load dashboard overview:', error)
          setDashboardError(
            error instanceof Error
              ? error.message
              : 'Failed to load dashboard overview',
          )
        }
      } finally {
        if (!cancelled) {
          setLoadingDashboard(false)
        }
      }
    }

    loadDashboard()

    return () => {
      cancelled = true
    }
  }, [token, selectedAgentId, refreshKey])

  // Load resource metrics history for the selected agent.
  useEffect(() => {
    if (!token || selectedAgentId === null) {
      setMetricsHistory([])
      return
    }

    let cancelled = false

    async function loadMetricsHistory() {
      setLoadingMetricsHistory(true)
      setMetricsHistoryError('')

      try {
        const result = await apiRequest<ResourceMetric[]>(
          `/dashboard/metrics-history/${selectedAgentId}?limit=100`,
          token,
        )

        if (!cancelled) {
          // API returns newest first; chart should display oldest first.
          setMetricsHistory([...result].reverse())
        }
      } catch (error) {
        if (!cancelled) {
          setMetricsHistoryError(
            error instanceof Error
              ? error.message
              : 'Failed to load metrics history',
          )
          setMetricsHistory([])
        }
      } finally {
        if (!cancelled) {
          setLoadingMetricsHistory(false)
        }
      }
    }

    loadMetricsHistory()

    return () => {
      cancelled = true
    }
  }, [token, selectedAgentId, refreshKey])


  // Load recent activity for the selected agent.
  useEffect(() => {
    if (!token || selectedAgentId === null) {
      setActivities([])
      return
    }

    let cancelled = false

    async function loadActivity() {
      setLoadingActivity(true)
      setActivityError('')

      try {
        const result = await apiRequest<ActivityLog[]>(
          `/dashboard/activity/${selectedAgentId}?limit=${activeNav === 'Activity Logs' ? 100 : 10}`,
          token,
        )

        if (!cancelled) {
          setActivities(result)
        }
      } catch (error) {
        if (!cancelled) {
          console.error('Failed to load activity:', error)
          setActivityError(
            error instanceof Error
              ? error.message
              : 'Failed to load activity',
          )
          setActivities([])
        }
      } finally {
        if (!cancelled) {
          setLoadingActivity(false)
        }
      }
    }

    loadActivity()

    return () => {
      cancelled = true
    }
  }, [token, selectedAgentId, refreshKey, activeNav])

    // Load website-monitor sessions belonging to the logged-in user.
  useEffect(() => {
    if (!token) {
      setMonitorSessions([])
      setSelectedMonitorUid('')
      setMonitorHistory([])
      return
    }

    let cancelled = false

    async function loadMonitorSessions() {
      setLoadingMonitor(true)
      setMonitorError('')

      try {
        const result = await apiRequest<WebsiteMonitorSession[]>(
          '/sessions',
          token,
        )

        if (!cancelled) {
          const websiteSessions = result.filter(
            (session) => session.agent_type === 'website_monitor',
          )

          setMonitorSessions(websiteSessions)

          setSelectedMonitorUid((current) => {
            const currentExists = websiteSessions.some(
              (session) => session.session_uid === current,
            )

            return currentExists
              ? current
              : websiteSessions[0]?.session_uid ?? ''
          })
        }
      } catch (error) {
        if (!cancelled) {
          setMonitorError(
            error instanceof Error
              ? error.message
              : 'Failed to load website-monitor sessions',
          )
          setMonitorSessions([])
        }
      } finally {
        if (!cancelled) {
          setLoadingMonitor(false)
        }
      }
    }

    loadMonitorSessions()

    return () => {
      cancelled = true
    }
  }, [token])

  // Load history for the selected website-monitor session.
  useEffect(() => {
    if (!token || !selectedMonitorUid) {
      setMonitorHistory([])
      return
    }

    let cancelled = false

    async function loadMonitorHistory() {
      setLoadingMonitor(true)
      setMonitorError('')

      try {
        const result = await apiRequest<WebsiteMonitorCheck[]>(
          `/sessions/${selectedMonitorUid}/history`,
          token,
        )

        if (!cancelled) {
          setMonitorHistory(result)
        }
      } catch (error) {
        if (!cancelled) {
          setMonitorError(
            error instanceof Error
              ? error.message
              : 'Failed to load website-monitor history',
          )
          setMonitorHistory([])
        }
      } finally {
        if (!cancelled) {
          setLoadingMonitor(false)
        }
      }
    }

    loadMonitorHistory()

    return () => {
      cancelled = true
    }
  }, [token, selectedMonitorUid, monitorRefreshKey])
  const processes = dashboard?.processes ?? []

  const filteredProcesses = processes.filter((process) => {
    const matchesSearch = process.name
      .toLowerCase()
      .includes(search.toLowerCase())

    const health = normalizeHealth(process.health_status)
    const matchesFilter = filter === 'All' || health === filter.toLowerCase()

    return matchesSearch && matchesFilter
  })

  const healthyCount = processes.filter(
    (process) => normalizeHealth(process.health_status) === 'healthy',
  ).length

  const warningCount = processes.filter(
    (process) => normalizeHealth(process.health_status) === 'warning',
  ).length

  const criticalCount = processes.filter(
    (process) => normalizeHealth(process.health_status) === 'critical',
  ).length

  const alertCount = warningCount + criticalCount

  const selectedAgent = agents.find(
    (agent) => agent.id === selectedAgentId,
  )

  if (!token) {
    return <Login onLogin={handleLogin} />
  }

  return (
    <div className="dashboard">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">✦</div>
          <div>
            <strong>Orbit</strong>
            <span>Desktop Agent</span>
          </div>
        </div>

        <div className="workspace-label">WORKSPACE</div>

        <nav className="navigation">
          {[
            ['Overview', '◫'],
            ['Processes', '▤'],
            ['Health Monitor', '♡'],
            ['Activity Logs', '◷'],
            ['Website Monitor', '◎'],
            ['Reports', '▥'],
          ].map(([label, icon]) => (
            <button
              key={label}
              className={`nav-item ${activeNav === label ? 'active' : ''}`}
              onClick={() => setActiveNav(label)}
            >
              <span className="nav-icon">{icon}</span>
              {label}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="agent-mini">
            <span className="online-dot" />
            <div>
              <strong>{selectedAgent?.name ?? 'Desktop Agent'}</strong>
              <small>
                {selectedAgent?.status ?? 'No agent selected'}
              </small>
            </div>
          </div>

          <button className="nav-item" onClick={handleLogout}>
            <span className="nav-icon">↪</span>
            Sign out
          </button>

          <div className="profile">
            <div className="avatar">A</div>
            <div>
              <strong>Workspace</strong>
              <small>Authenticated user</small>
            </div>
            <span className="profile-menu">•••</span>
          </div>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace <span>/</span> <strong>{activeNav}</strong>
          </div>

          <div className="topbar-actions">
            <span className="demo-label">
              {dashboard?.metrics ? 'AGENT DATA' : 'NO METRICS'}
            </span>
            <button className="icon-button" aria-label="Notifications">
              ♧
            </button>
            <div className="avatar small">A</div>
          </div>
        </header>

        <div className="page-content">
          <section className="page-heading">
            <div>
              <p className="eyebrow">MONITORING CENTER</p>
              <h1>{activeNav}</h1>
              <p className="subtitle">
                {activeNav === 'Website Monitor'
                  ? 'View website monitoring sessions and their check history.'
                  : activeNav === 'Activity Logs'
                    ? 'Review event history from your connected desktop agent.'
                    : activeNav === 'Processes'
                      ? 'View and manage processes running on your desktop agent.'
                      : activeNav === 'Reports'
                        ? 'Review system activity and monitoring reports.'
                        : activeNav === 'Health Monitor'
                          ? 'Monitor system health and resource usage.'
                          : 'Monitor your desktop environment and application health.'}
              </p>
            </div>

            <div className="page-heading-actions">
              {agents.length > 0 && (
                <select
                  aria-label="Select desktop agent"
                  value={selectedAgentId ?? ''}
                  onChange={(event) =>
                    setSelectedAgentId(
                      event.target.value ? Number(event.target.value) : null,
                    )
                  }
                >
                  {agents.map((agent) => (
                    <option key={agent.id} value={agent.id}>
                      {agent.name} — {agent.hostname}
                    </option>
                  ))}
                </select>
              )}

              <button
                className="primary-button"
                onClick={() => {
                  if (activeNav === 'Website Monitor') {
                    setMonitorRefreshKey((current) => current + 1)
                  } else {
                    setRefreshKey((current) => current + 1)
                  }
                }}
                disabled={loadingDashboard}
              >
                ↻ {loadingDashboard
                  ? 'Refreshing...'
                  : activeNav === 'Website Monitor'
                    ? 'Refresh history'
                    : activeNav === 'Activity Logs'
                      ? 'Refresh activity'
                      : activeNav === 'Processes'
                        ? 'Refresh processes'
                        : activeNav === 'Health Monitor'
                          ? 'Refresh health'
                          : activeNav === 'Reports'
                            ? 'Refresh reports'
                            : 'Refresh overview'}
              </button>
            </div>
          </section>

          {activeNav === 'Website Monitor' && (
            <section className="panel">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">WEBSITE MONITOR</p>
                  <h2>Monitoring history</h2>
                  {monitorActionError && (
                    <div className="login-error">{monitorActionError}</div>
                  )}

                  <div className="page-heading-actions">
                    <button
                      className="primary-button"
                      type="button"
                      onClick={() => handleMonitorAction('start')}
                      disabled={
                        !selectedMonitorUid ||
                        monitorActionLoading ||
                        monitorSessions.find(
                          (session) => session.session_uid === selectedMonitorUid,
                        )?.status === 'running'
                      }
                    >
                      {monitorActionLoading
                        ? 'Please wait...'
                        : monitorSessions.find(
                            (session) => session.session_uid === selectedMonitorUid,
                          )?.status === 'failed'
                          ? 'Restart Monitor'
                          : 'Start Monitor'}
                    </button>

                    <button
                      className="text-button"
                      type="button"
                      onClick={() => handleMonitorAction('stop')}
                      disabled={
                        !selectedMonitorUid ||
                        monitorActionLoading ||
                        monitorSessions.find(
                          (session) => session.session_uid === selectedMonitorUid,
                        )?.status !== 'running'
                      }
                    >
                      Stop Monitor
                    </button>
                  </div>
                </div>
                <button
                  className="primary-button"
                  type="button"
                  onClick={() => {
                    setMonitorFormOpen((current) => !current)
                    setCreateMonitorError('')
                  }}
                >
                  + Create Monitor
                </button>
                <select
                  aria-label="Select website monitoring session"
                  value={selectedMonitorUid}
                  onChange={(event) =>
                    setSelectedMonitorUid(event.target.value)
                  }
                >
                  <option value="">Select a monitoring session</option>
                  {monitorSessions.map((session) => (
                    <option
                      key={session.session_uid}
                      value={session.session_uid}
                    >
                      {session.name} — {session.status}
                    </option>
                  ))}
                </select>
              </div>
              {monitorFormOpen && (
                <form
                  className="monitor-create-form"
                  onSubmit={(event) => {
                    event.preventDefault()
                    handleCreateMonitor()
                  }}
                >
                  <h3>Create Website Monitor</h3>

                  <label>
                    Monitor name
                    <input
                      type="text"
                      value={monitorName}
                      onChange={(event) => setMonitorName(event.target.value)}
                      placeholder="My Website Monitor"
                      maxLength={150}
                      required
                    />
                  </label>

                  <label>
                    Website URL
                    <input
                      type="url"
                      value={monitorUrl}
                      onChange={(event) => setMonitorUrl(event.target.value)}
                      placeholder="https://example.com"
                      required
                    />
                  </label>

                  <label>
                    Check interval (seconds)
                    <input
                      type="number"
                      value={monitorInterval}
                      onChange={(event) => setMonitorInterval(event.target.value)}
                      min={5}
                      max={3600}
                      step={1}
                      required
                    />
                  </label>

                  {createMonitorError && (
                    <div className="login-error">{createMonitorError}</div>
                  )}

                  <div className="page-heading-actions">
                    <button
                      className="primary-button"
                      type="submit"
                      disabled={creatingMonitor}
                    >
                      {creatingMonitor ? 'Creating...' : 'Create Monitor'}
                    </button>

                    <button
                      className="text-button"
                      type="button"
                      onClick={() => setMonitorFormOpen(false)}
                      disabled={creatingMonitor}
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              )}
              {loadingMonitor && (
                <p className="subtitle">Loading monitoring history...</p>
              )}

              {monitorError && (
                <div className="login-error">{monitorError}</div>
              )}

              {!loadingMonitor &&
                !monitorError &&
                monitorSessions.length === 0 && (
                  <p className="subtitle">
                    No website monitoring sessions found.
                  </p>
                )}

              {!loadingMonitor &&
                !monitorError &&
                selectedMonitorUid &&
                monitorHistory.length === 0 && (
                  <p className="subtitle">
                    No website checks have been recorded for this session yet.
                  </p>
                )}

              {monitorHistory.length > 0 && (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Website</th>
                        <th>Result</th>
                        <th>HTTP</th>
                        <th>Response time</th>
                        <th>Checked at</th>
                      </tr>
                    </thead>

                    <tbody>
                      {monitorHistory.map((check) => (
                        <tr key={check.id}>
                          <td>{check.url}</td>
                          <td>
                            {check.is_available ? 'Available' : 'Unavailable'}
                          </td>
                          <td>{check.status_code ?? '—'}</td>
                          <td>
                            {check.response_time_ms != null
                              ? `${check.response_time_ms} ms`
                              : '—'}
                          </td>
                          <td>
                            {new Date(check.checked_at).toLocaleString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          )}
        {activeNav === 'Activity Logs' && (
          <section className="panel activity-panel">
            <div className="panel-header">
              <div>
                <h2>Activity Logs</h2>
                <p>Latest 100 events for the selected agent</p>
              </div>

              <button
                className="text-button"
                onClick={() => setRefreshKey((current) => current + 1)}
              >
                Refresh
              </button>
            </div>

            <div className="activity-list">
              {loadingActivity ? (
                <p className="subtitle">Loading activity...</p>
              ) : activityError ? (
                <p className="subtitle">{activityError}</p>
              ) : activities.length === 0 ? (
                <p className="subtitle">No activity recorded yet.</p>
              ) : (
                activities.map((activity) => (
                  <div className="activity-item" key={activity.id}>
                    <div className="activity-item-content">
                      <strong>{activity.event_type}</strong>
                      <p>{activity.message}</p>
                      <small>
                        {new Date(activity.created_at).toLocaleString()}
                      </small>
                    </div>
                  </div>
                ))
              )}
            </div>
          </section>
        )}
        {activeNav !== 'Website Monitor' && activeNav !== 'Activity Logs' && (
          <>
          {dashboardError && (
            <div className="login-error">
              {dashboardError}
            </div>
          )}

          {loadingAgents && (
            <p className="subtitle">Loading registered agents...</p>
          )}

          {!loadingAgents && agents.length === 0 && (
            <div className="panel">
              <div className="panel-header">
                <div>
                  <h2>No agents registered</h2>
                  <p>
                    Register and connect a desktop agent to view its metrics
                    and process information here.
                  </p>
                </div>
              </div>
            </div>
          )}

          <section className="metric-grid">
            <MetricCard
              title="CPU Usage"
              value={
                dashboard?.metrics?.cpu_usage != null
                  ? `${dashboard.metrics.cpu_usage.toFixed(1)}%`
                  : '—'
              }
              change="From selected agent"
              icon="◉"
              color="purple"
            />

            <MetricCard
              title="Memory Usage"
              value={
                dashboard?.metrics?.memory_usage != null
                  ? `${dashboard.metrics.memory_usage.toFixed(1)}%`
                  : '—'
              }
              change={
                dashboard?.metrics?.memory_total != null &&
                dashboard.metrics.memory_available != null
                  ? `${formatBytesToGB(
                      dashboard.metrics.memory_total -
                        dashboard.metrics.memory_available,
                    )} of ${formatBytesToGB(
                      dashboard.metrics.memory_total,
                    )}`
                  : 'From selected agent'
              }
              icon="▥"
              color="blue"
            />

            <MetricCard
              title="Active Processes"
              value={
                dashboard ? String(dashboard.process_count) : '—'
              }
              change="Latest process snapshot"
              icon="▤"
              color="green"
            />

            <MetricCard
              title="Health Alerts"
              value={dashboard ? String(alertCount) : '—'}
              change="Warnings and critical processes"
              icon="△"
              color="orange"
            />
          </section>

          <section className="panel resource-history-panel">
            <div className="panel-header">
              <div>
                <h2>Resource Usage History</h2>
                <p>CPU, memory and disk usage over the latest 100 samples</p>
              </div>

              <button
                className="text-button"
                onClick={() => setRefreshKey((current) => current + 1)}
              >
                Refresh
              </button>
            </div>

            {loadingMetricsHistory ? (
              <p className="subtitle">Loading resource history...</p>
            ) : metricsHistoryError ? (
              <p className="subtitle">{metricsHistoryError}</p>
            ) : metricsHistory.length === 0 ? (
              <p className="subtitle">
                No resource history recorded yet.
              </p>
            ) : (
              <div style={{ width: '100%', height: 320 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={metricsHistory}>
                    <CartesianGrid strokeDasharray="3 3" />

                    <XAxis
                      dataKey="recorded_at"
                      tickFormatter={(value) =>
                        new Date(value).toLocaleTimeString([], {
                          hour: '2-digit',
                          minute: '2-digit',
                        })
                      }
                    />

                    <YAxis domain={[0, 100]} unit="%" />

                    <Tooltip
                      labelFormatter={(value) =>
                        new Date(String(value)).toLocaleString()
                      }
                      formatter={(value) => [
                        `${Number(value).toFixed(1)}%`,
                      ]}
                    />

                    <ChartLegend />

                    <Line
                      type="monotone"
                      dataKey="cpu_usage"
                      name="CPU"
                      stroke="#8b5cf6"
                      dot={false}
                    />

                    <Line
                      type="monotone"
                      dataKey="memory_usage"
                      name="Memory"
                      stroke="#3b82f6"
                      dot={false}
                    />

                    <Line
                      type="monotone"
                      dataKey="disk_usage"
                      name="Disk"
                      stroke="#f59e0b"
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </section>

          <section className="content-grid">
            <div className="panel process-panel">
              <div className="panel-header">
                <div>
                  <h2>Process Monitor</h2>
                  <p>Processes from the selected agent's latest snapshot</p>
                </div>

                <button
                  className="text-button"
                  onClick={() => setActiveNav('Processes')}
                >
                  View all <span>→</span>
                </button>
              </div>

              <div className="process-toolbar">
                <input
                  className="search-input"
                  placeholder="Search processes..."
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                />

                <select
                  value={filter}
                  onChange={(event) => setFilter(event.target.value)}
                >
                  <option value="All">All</option>
                  <option value="Healthy">Healthy</option>
                  <option value="Warning">Warning</option>
                  <option value="Critical">Critical</option>
                </select>
              </div>

              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>PROCESS</th>
                      <th>PID</th>
                      <th>CPU</th>
                      <th>MEMORY</th>
                      <th>HEALTH</th>
                    </tr>
                  </thead>

                  <tbody>
                    {filteredProcesses.map((process) => {
                      const health = normalizeHealth(process.health_status)
                      const healthLabel =
                        health === 'unknown'
                          ? 'Unknown'
                          : health.charAt(0).toUpperCase() + health.slice(1)

                      const detail =
                        process.health_reasons.length > 0
                          ? process.health_reasons.join(' · ')
                          : process.status || 'No health details reported'

                      return (
                        <tr
                          key={`${process.pid}-${process.name}`}
                          className="clickable-process-row"
                          onClick={() => setSelectedProcess(process)}
                        >
                          <td>
                            <div className="process-name">
                              <span className="process-symbol">▣</span>
                              <div>
                                <strong>{process.name}</strong>
                                <small>{detail}</small>
                              </div>
                            </div>
                          </td>

                          <td className="muted-cell">{process.pid}</td>
                          <td>{process.cpu_percent.toFixed(1)}%</td>
                          <td>
                            {(process.memory_rss / 1024 ** 2).toFixed(1)} MB
                          </td>
                          <td>
                            <HealthBadge status={healthLabel} />
                          </td>
                        </tr>
                      )
                    })}

                    {filteredProcesses.length === 0 && (
                      <tr>
                        <td colSpan={5} className="empty-state">
                          {loadingDashboard
                            ? 'Loading process data...'
                            : dashboard
                              ? 'No matching processes found.'
                              : 'No process snapshot available for this agent.'}
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
              {selectedProcess && (
                <div className="process-details">
                  <div className="panel-header">
                    <div>
                      <h2>Process Details</h2>
                      <p>{selectedProcess.name}</p>
                    </div>

                    <button
                      className="text-button"
                      onClick={() => setSelectedProcess(null)}
                    >
                      Close
                    </button>
                  </div>

                  <div className="process-details-grid">
                    <div>
                      <span>Process ID</span>
                      <strong>{selectedProcess.pid}</strong>
                    </div>

                    <div>
                      <span>CPU Usage</span>
                      <strong>
                        {selectedProcess.cpu_percent.toFixed(1)}%
                      </strong>
                    </div>

                    <div>
                      <span>Memory Usage</span>
                      <strong>
                        {(selectedProcess.memory_rss / 1024 ** 2).toFixed(1)} MB
                      </strong>
                    </div>

                    <div>
                      <span>Status</span>
                      <strong>{selectedProcess.status || 'Unknown'}</strong>
                    </div>

                    <div>
                      <span>Started</span>
                      <strong>
                        {selectedProcess.create_time
                          ? new Date(
                              selectedProcess.create_time * 1000,
                            ).toLocaleString()
                          : 'Unknown'}
                      </strong>
                    </div>

                    <div>
                      <span>Health</span>
                      <strong>
                        {selectedProcess.health_status || 'Unknown'}
                      </strong>
                    </div>
                  </div>

                  <div className="process-health-reasons">
                    <strong>Health Details</strong>
                    <p>
                      {selectedProcess.health_reasons.length > 0
                        ? selectedProcess.health_reasons.join(' · ')
                        : 'No health issues reported.'}
                    </p>
                  </div>
                  <div className="process-actions">
                    <button
                      className="text-button"
                      onClick={handleStopProcess}
                      disabled={selectedProcess.create_time === null}
                    >
                      Stop Process
                    </button>
                  </div>
                </div>
              )}
            </div>

            <div className="side-panels">
              <div className="panel health-panel">
                <div className="panel-header">
                  <div>
                    <h2>Health Overview</h2>
                    <p>Health status of reported processes</p>
                  </div>
                </div>

                <div className="health-summary">
                  <div className="health-ring">
                    <strong>{healthyCount}</strong>
                    <span>healthy</span>
                  </div>

                  <div className="health-legend">
                    <Legend
                      color="green"
                      label="Healthy"
                      value={String(healthyCount)}
                    />
                    <Legend
                      color="orange"
                      label="Warning"
                      value={String(warningCount)}
                    />
                    <Legend
                      color="red"
                      label="Critical"
                      value={String(criticalCount)}
                    />
                  </div>
                </div>
              </div>

              <div className="panel activity-panel">
                <div className="panel-header">
                  <div>
                    <h2>Recent Activity</h2>
                    <p>Agent event history</p>
                  </div>

                  <button
                    className="text-button"
                    onClick={() => setActiveNav('Activity Logs')}
                  >
                    View all
                  </button>
                </div>

                <div className="activity-list">
                  {loadingActivity ? (
                    <p className="subtitle">Loading activity...</p>
                  ) : activityError ? (
                    <p className="subtitle">{activityError}</p>
                  ) : activities.length === 0 ? (
                    <p className="subtitle">No activity recorded yet.</p>
                  ) : (
                    activities.map((activity) => (
                      <div className="activity-item" key={activity.id}>
                        <div className="activity-item-content">
                          <strong>{activity.event_type}</strong>
                          <p>{activity.message}</p>
                          <small>
                            {new Date(activity.created_at).toLocaleString()}
                          </small>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </section>

          <footer className="dashboard-footer">
            <span>
              <span className="online-dot" />
              Agent status: {selectedAgent?.status ?? 'Not connected'}
            </span>
            <span>
              {dashboard?.metrics?.recorded_at
                ? `Metrics recorded: ${new Date(
                    dashboard.metrics.recorded_at,
                  ).toLocaleString()}`
                : 'Waiting for agent metrics'}
            </span>
          </footer>
          </>
        )}
        </div>
      </main>
    </div>
  )
}

function MetricCard({
  title,
  value,
  change,
  icon,
  color,
}: {
  title: string
  value: string
  change: string
  icon: string
  color: string
}) {
  return (
    <div className="metric-card">
      <div className={`metric-icon ${color}`}>{icon}</div>
      <p>{title}</p>
      <div className="metric-value">{value}</div>
      <span className="metric-change">{change}</span>
    </div>
  )
}

function HealthBadge({ status }: { status: string }) {
  return (
    <span className={`health-badge ${status.toLowerCase()}`}>
      <span />
      {status}
    </span>
  )
}

function Legend({
  color,
  label,
  value,
}: {
  color: string
  label: string
  value: string
}) {
  return (
    <div className="legend-item">
      <span className={`legend-dot ${color}`} />
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

export default App
