import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { streamInvestigation, type AgentEvent } from '../sse'

const STEPS: [string, string][] = [
  ['research', 'Research the official docs'],
  ['probes', 'Run safe checks on the OAuth endpoints'],
  ['sources', 'Check every cited page exists'],
  ['write', 'Write the guide and label every claim'],
  ['validate', 'Enforce evidence rules and validate'],
]

type Phase = 'idle' | 'running' | 'finished'

interface StepState {
  status: 'pending' | 'running' | 'done' | 'failed'
  message: string
}

/** When a run ends, no step may keep spinning: it either finished or failed. */
function settleRunning(
  steps: Record<string, StepState>,
  status: 'done' | 'failed',
): Record<string, StepState> {
  return Object.fromEntries(
    Object.entries(steps).map(([id, state]) => [
      id,
      state.status !== 'running'
        ? state
        : { status, message: status === 'failed' ? 'Stopped at this step.' : state.message },
    ]),
  )
}

export default function GeneratePage() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [phase, setPhase] = useState<Phase>('idle')
  const [steps, setSteps] = useState<Record<string, StepState>>({})
  const [probes, setProbes] = useState<Extract<AgentEvent, { type: 'probe' }>[]>([])
  const [notices, setNotices] = useState<string[]>([])
  const [result, setResult] = useState<AgentEvent | null>(null)
  const controller = useRef<AbortController | null>(null)

  useEffect(() => {
    document.title = 'Investigate an app: OAuth App Setup Guides'
    return () => controller.current?.abort()
  }, [])

  function handle(event: AgentEvent) {
    if (event.type === 'step') {
      setSteps((prev) => ({
        ...prev,
        [event.step]: { status: event.status, message: event.message },
      }))
    } else if (event.type === 'probe') {
      setProbes((prev) => [...prev, event])
    } else if (event.type === 'notice') {
      setNotices((prev) => [...prev, event.message])
    } else {
      setSteps((prev) => settleRunning(prev, event.type === 'error' ? 'failed' : 'done'))
      setResult(event)
      if (event.type === 'done' && event.cached) {
        navigate(`/guides/${event.slug}`)
      }
    }
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    const q = query.trim()
    if (!q || phase === 'running') return
    controller.current?.abort()
    controller.current = new AbortController()
    setPhase('running')
    setSteps({})
    setProbes([])
    setNotices([])
    setResult(null)
    try {
      await streamInvestigation(q, handle, controller.current.signal)
    } catch (error: unknown) {
      if (controller.current.signal.aborted) return
      const message = error instanceof Error ? error.message : 'Unknown error.'
      setSteps((prev) => settleRunning(prev, 'failed'))
      setResult({
        type: 'error',
        code: 'network',
        message: `Could not reach the server. ${message}`,
      })
    } finally {
      setPhase('finished')
    }
  }

  const started = phase !== 'idle'

  return (
    <>
      <section className="intro">
        <h1>Investigate any app</h1>
        <p className="lead">
          Type an app name or website. An agent researches the provider&rsquo;s official docs, our
          code runs safe checks on its OAuth endpoints, and you get a guide in the same format as
          the library, with a shareable link. It usually takes one to three minutes.
        </p>
      </section>

      <form className="generate-form" onSubmit={(e) => void submit(e)}>
        <label className="search">
          <span className="visually-hidden">App name or website</span>
          <input
            type="text"
            placeholder="e.g. Zoom, Xero or calendly.com"
            value={query}
            maxLength={100}
            onChange={(e) => setQuery(e.target.value)}
            disabled={phase === 'running'}
          />
        </label>
        <button
          type="submit"
          className="button primary"
          disabled={phase === 'running' || !query.trim()}
        >
          {phase === 'running' ? 'Investigating...' : 'Investigate'}
        </button>
      </form>
      <p className="muted small">
        The agent never signs in, creates accounts or submits forms. Apps already in the{' '}
        <Link to="/">library</Link> open straight away.
      </p>

      {started && (
        <section className="panel progress" aria-label="Progress" aria-live="polite">
          <ol className="progress-steps">
            {STEPS.map(([id, label]) => {
              const state = steps[id]
              const status = state?.status ?? 'pending'
              return (
                <li key={id} className={`progress-step is-${status}`}>
                  <span className="progress-dot" aria-hidden="true" />
                  <div>
                    <strong>{label}</strong>
                    <span className="visually-hidden"> ({status})</span>
                    {state?.message ? <p>{state.message}</p> : null}
                    {id === 'probes' && probes.length > 0 && (
                      <ul className="probe-list">
                        {probes.map((p) => (
                          <li key={p.id}>
                            <span className={`outcome outcome-${p.outcome}`}>
                              {p.outcome.replace('_', ' ')}
                            </span>{' '}
                            <span className="break">{p.target}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </li>
              )
            })}
          </ol>
          {notices.map((n) => (
            <p key={n} className="notice small">
              {n}
            </p>
          ))}
        </section>
      )}

      {result?.type === 'done' && !result.cached && (
        <section className="panel ready" role="status">
          <div>
            <h2>Your guide is ready</h2>
            <p>It has its own link you can share.</p>
          </div>
          <Link className="button primary" to={`/guides/${result.slug}`}>
            Open the guide <span aria-hidden="true">&rarr;</span>
          </Link>
        </section>
      )}
      {result?.type === 'no_oauth' && (
        <section className="panel panel-warm" role="status">
          <h2>No OAuth app needed</h2>
          <p>{result.message}</p>
        </section>
      )}
      {result?.type === 'error' && (
        <section className="panel panel-warm" role="alert">
          <h2>We could not finish this investigation</h2>
          <p>{result.message}</p>
          <p>
            <Link to="/">Browse the guide library</Link>
          </p>
        </section>
      )}
    </>
  )
}
