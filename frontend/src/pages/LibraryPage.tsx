import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { listGuides, type GuideSummary } from '../api'
import { DifficultyBadge } from '../components/badges'
import type { Level } from '../types/guide'

const LEVELS: Level[] = ['Easy', 'Medium', 'Hard', 'Very hard']

type State =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; guides: GuideSummary[] }

export default function LibraryPage() {
  const [state, setState] = useState<State>({ status: 'loading' })
  const [query, setQuery] = useState('')
  const [level, setLevel] = useState<Level | 'All'>('All')

  useEffect(() => {
    document.title = 'OAuth App Setup Guides'
    const controller = new AbortController()
    listGuides(controller.signal)
      .then((guides) => setState({ status: 'ready', guides }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        const message = error instanceof Error ? error.message : 'Unknown error.'
        setState({ status: 'error', message })
      })
    return () => controller.abort()
  }, [])

  const visible = useMemo(() => {
    if (state.status !== 'ready') return []
    const q = query.trim().toLowerCase()
    return state.guides.filter(
      (g) =>
        (level === 'All' || g.difficulty === level) &&
        (!q || `${g.name} ${g.category} ${g.website}`.toLowerCase().includes(q)),
    )
  }, [state, query, level])

  return (
    <>
      <section className="intro">
        <h1>How hard is it to get an OAuth app approved?</h1>
        <p className="lead">
          Before your users can connect an app to your agent, you may need your own OAuth app with
          the provider, and sometimes weeks of review. Each guide shows the difficulty, the hands-on
          time, the approval wait, the steps, and what you must do yourself.
        </p>
      </section>

      <section aria-label="Find a guide" className="filters">
        <label className="search">
          <span className="visually-hidden">Search apps</span>
          <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true">
            <circle cx="7" cy="7" r="4.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
            <path
              d="M10.5 10.5L14 14"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          </svg>
          <input
            type="search"
            placeholder="Search apps, e.g. Slack"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <div className="chips" role="group" aria-label="Filter by difficulty">
          {(['All', ...LEVELS] as const).map((l) => (
            <button
              key={l}
              type="button"
              className="chip"
              aria-pressed={level === l}
              onClick={() => setLevel(l)}
            >
              {l}
            </button>
          ))}
        </div>
      </section>

      {state.status === 'loading' && (
        <p role="status" className="message">
          Loading guides...
        </p>
      )}
      {state.status === 'error' && (
        <p role="alert" className="message error">
          Could not load the guide library. {state.message} Please try again in a minute.
        </p>
      )}
      {state.status === 'ready' && visible.length === 0 && (
        <p role="status" className="message">
          No guides match your search.{' '}
          <Link to="/generate">
            Investigate {query.trim() ? `"${query.trim()}"` : 'an app'} live
          </Link>
        </p>
      )}

      {state.status === 'ready' && visible.length > 0 && (
        <p className="count">
          {visible.length} of {state.guides.length} guides
        </p>
      )}

      {visible.length > 0 && (
        <ul className="cards" aria-label="Guides">
          {visible.map((g) => (
            <li key={g.slug} className="card">
              <div className="card-top">
                <h2>
                  <Link className="card-link" to={`/guides/${g.slug}`}>
                    {g.name}
                  </Link>
                </h2>
                <DifficultyBadge level={g.difficulty} />
              </div>
              <p className="muted card-meta">
                <span>{g.category}</span>
                {g.generated_by === 'live_agent' && <span className="pill live">Live agent</span>}
              </p>
              <dl className="facts">
                <div>
                  <dt>Hands-on</dt>
                  <dd>{g.hands_on}</dd>
                </div>
                <div>
                  <dt>Approval wait</dt>
                  <dd>{g.approval_wait}</dd>
                </div>
              </dl>
              <p className="card-reason">{g.difficulty_reason}</p>
              {g.managed_oauth === 'yes' && (
                <p className="managed">
                  <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
                    <path
                      d="M3.5 8.5l3 3 6-7"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.8"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                  Composio managed app available to start
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </>
  )
}
