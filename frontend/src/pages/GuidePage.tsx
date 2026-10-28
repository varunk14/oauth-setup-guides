import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError, getGuide, getGuideMarkdown } from '../api'
import { DifficultyBadge, WhoBadge } from '../components/badges'
import EvidenceTag from '../components/EvidenceTag'
import type { Guide } from '../types/guide'

type State =
  | { status: 'loading' }
  | { status: 'not-found'; message: string }
  | { status: 'error'; message: string }
  | { status: 'ready'; guide: Guide }

const managedText = {
  yes: 'You can start on Composio’s managed OAuth app today.',
  no: 'Composio has no managed app here; you need to bring your own OAuth app.',
  unknown: 'We could not tell whether Composio has a managed app here.',
} as const

const managedPill = {
  yes: 'Managed app available',
  no: 'Bring your own app',
  unknown: 'Managed app unknown',
} as const

function formatDate(iso: string): string {
  return new Date(iso).toISOString().slice(0, 16).replace('T', ' ')
}

export default function GuidePage() {
  const { slug = '' } = useParams()
  // Remount per slug so each guide starts from a clean loading state.
  return <GuideView key={slug} slug={slug} />
}

function GuideView({ slug }: { slug: string }) {
  const [state, setState] = useState<State>({ status: 'loading' })
  const [copyStatus, setCopyStatus] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    getGuide(slug, controller.signal)
      .then((guide) => {
        setState({ status: 'ready', guide })
        document.title = `${guide.app.name}: OAuth app setup guide`
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        if (error instanceof ApiError && error.status === 404) {
          setState({ status: 'not-found', message: error.message })
        } else {
          const message = error instanceof Error ? error.message : 'Unknown error.'
          setState({ status: 'error', message })
        }
      })
    return () => controller.abort()
  }, [slug])

  const sourceNumbers = useMemo(() => {
    if (state.status !== 'ready') return {}
    return Object.fromEntries(state.guide.sources.map((s, i) => [s.id, i + 1]))
  }, [state])

  async function copy(kind: 'link' | 'markdown') {
    try {
      const text =
        kind === 'link' ? window.location.href.split('#')[0]! : await getGuideMarkdown(slug)
      await navigator.clipboard.writeText(text)
      setCopyStatus(kind === 'link' ? 'Link copied.' : 'Markdown copied.')
    } catch {
      setCopyStatus(
        'Copy failed. Your browser blocked the clipboard; copy the page address instead.',
      )
    }
  }

  if (state.status === 'loading') {
    return (
      <p role="status" className="message">
        Loading guide...
      </p>
    )
  }
  if (state.status === 'not-found') {
    return (
      <section className="message">
        <h1>No guide for “{slug}” yet</h1>
        <p>{state.message}</p>
        <p>
          <Link to="/">Browse the guide library</Link>
        </p>
      </section>
    )
  }
  if (state.status === 'error') {
    return (
      <p role="alert" className="message error">
        Could not load this guide. {state.message} Please try again in a minute.
      </p>
    )
  }

  const g = state.guide
  const toc: [string, string][] = [
    ['steps', 'Steps'],
    ['review', 'Review'],
    ...(g.requirements.length ? [['requirements', 'Requirements'] as [string, string]] : []),
    ...(g.scopes.length ? [['scopes', 'Scopes'] as [string, string]] : []),
    ...(g.blockers.length ? [['blockers', 'Blockers'] as [string, string]] : []),
    ['agent-human', 'Agent vs you'],
    ...(g.nuances.length ? [['nuances', 'Nuances'] as [string, string]] : []),
    ...((g.unverified ?? []).length ? [['unverified', 'Not verified'] as [string, string]] : []),
    ...(g.probes.length ? [['checks', 'Checks'] as [string, string]] : []),
    ['sources', 'Sources'],
  ]
  const ev = (e: Guide['difficulty']['evidence']) => (
    <EvidenceTag evidence={e} sourceNumbers={sourceNumbers} />
  )

  return (
    <article className="guide">
      <p className="crumbs">
        <Link to="/">&larr; All guides</Link>
      </p>
      <header className="guide-header">
        <h1>{g.app.name}</h1>
        <p className="muted">
          {g.app.category} ·{' '}
          <a href={g.app.website} rel="noreferrer" target="_blank">
            {g.app.website.replace(/^https?:\/\//, '').replace(/\/$/, '')}
          </a>
        </p>
        <div className="actions">
          <button type="button" className="button" onClick={() => void copy('link')}>
            Copy link
          </button>
          <button type="button" className="button" onClick={() => void copy('markdown')}>
            Copy as Markdown
          </button>
          <span role="status" aria-live="polite" className="copy-status">
            {copyStatus}
          </span>
        </div>
      </header>

      <p className="summary">{g.summary}</p>

      <section className="panel glance" aria-label="At a glance">
        <div className="glance-item">
          <h2 className="label">Difficulty</h2>
          <DifficultyBadge level={g.difficulty.level} />
          <p>{g.difficulty.reason}</p>
          {ev(g.difficulty.evidence)}
        </div>
        <div className="glance-item">
          <h2 className="label">Hands-on effort</h2>
          <p className="big">{g.time.hands_on}</p>
        </div>
        <div className="glance-item">
          <h2 className="label">Approval wait</h2>
          <p className="big">{g.time.approval_wait}</p>
          {ev(g.time.evidence)}
        </div>
        {g.time.detail ? <p className="glance-detail">{g.time.detail}</p> : null}
      </section>

      <section className="panel" aria-labelledby="composio">
        <div className="panel-head">
          <h2 id="composio">Do you need your own OAuth app?</h2>
          <span className={`pill pill-${g.composio_note.managed_oauth}`}>
            {managedPill[g.composio_note.managed_oauth]}
          </span>
        </div>
        <p>
          <strong>{managedText[g.composio_note.managed_oauth]}</strong> {g.composio_note.detail}
        </p>
        <p className="muted small">
          Directory snapshot {g.composio_note.snapshot_date}. {ev(g.composio_note.evidence)}
        </p>
      </section>

      <nav className="toc" aria-label="On this page">
        <span className="label">On this page</span>
        {toc.map(([id, text]) => (
          <a key={id} href={`#${id}`}>
            {text}
          </a>
        ))}
      </nav>

      <section aria-labelledby="steps">
        <h2 id="steps">Steps</h2>
        <ol className="steps">
          {g.steps.map((s) => (
            <li key={s.order}>
              <span className="step-num" aria-hidden="true">
                {s.order}
              </span>
              <div className="step-head">
                <strong>{s.title}</strong> <WhoBadge who={s.who} />
              </div>
              <p>{s.action}</p>
              {s.where_url && (
                <p className="small">
                  Where:{' '}
                  <a href={s.where_url} target="_blank" rel="noreferrer">
                    {s.where_url}
                  </a>
                </p>
              )}
              <p className="small muted">Expected: {s.expected_result}</p>
              {ev(s.evidence)}
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="review">
        <h2 id="review">Review and approval</h2>
        <p>
          <strong>Review required: {g.review_process.required}.</strong> {g.review_process.trigger}{' '}
          Typical wait: {g.review_process.typical_wait}.
        </p>
        {ev(g.review_process.evidence)}
        {(g.review_process.what_to_submit ?? []).length > 0 && (
          <>
            <h3>What to submit</h3>
            <ul>
              {(g.review_process.what_to_submit ?? []).map((x) => (
                <li key={x}>{x}</li>
              ))}
            </ul>
          </>
        )}
        {(g.review_process.common_rejections ?? []).length > 0 && (
          <>
            <h3>Common rejection reasons</h3>
            <ul>
              {(g.review_process.common_rejections ?? []).map((x) => (
                <li key={x}>{x}</li>
              ))}
            </ul>
          </>
        )}
      </section>

      {g.requirements.length > 0 && (
        <section aria-labelledby="requirements">
          <h2 id="requirements">Requirements</h2>
          <ul className="claims">
            {g.requirements.map((r) => (
              <li key={r.name}>
                <strong>{r.name}</strong> <span className="muted">(required: {r.required})</span>{' '}
                {r.detail} {ev(r.evidence)}
              </li>
            ))}
          </ul>
        </section>
      )}

      {g.scopes.length > 0 && (
        <section aria-labelledby="scopes">
          <h2 id="scopes">Scopes</h2>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th scope="col">Scope</th>
                  <th scope="col">Purpose</th>
                  <th scope="col">Sensitivity</th>
                  <th scope="col">Triggers review</th>
                  <th scope="col">Evidence</th>
                </tr>
              </thead>
              <tbody>
                {g.scopes.map((s) => (
                  <tr key={s.name}>
                    <td>
                      <code>{s.name}</code>
                    </td>
                    <td>{s.purpose}</td>
                    <td>{s.sensitivity}</td>
                    <td>{s.triggers_review ? 'Yes' : 'No'}</td>
                    <td>{ev(s.evidence)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {g.blockers.length > 0 && (
        <section aria-labelledby="blockers">
          <h2 id="blockers">Blockers and how to get past them</h2>
          <ul className="claims">
            {g.blockers.map((b) => (
              <li key={b.blocker}>
                <strong>{b.blocker}</strong> {b.how_to_get_past}
                {b.contact ? <> Contact: {b.contact}.</> : null} {ev(b.evidence)}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-labelledby="agent-human">
        <h2 id="agent-human">What an agent can do, and what you must do</h2>
        <div className="columns">
          <div>
            <h3>The agent already did</h3>
            <ul>
              {(g.agent_vs_human.agent_did ?? []).map((x) => (
                <li key={x}>{x}</li>
              ))}
            </ul>
          </div>
          <div>
            <h3>An agent can do</h3>
            <ul>
              {(g.agent_vs_human.agent_can ?? []).map((x) => (
                <li key={x}>{x}</li>
              ))}
            </ul>
          </div>
          <div>
            <h3>You must do</h3>
            <ul>
              {g.agent_vs_human.human_must.map((x) => (
                <li key={x}>{x}</li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {g.nuances.length > 0 && (
        <section aria-labelledby="nuances">
          <h2 id="nuances">Nuances</h2>
          <ul className="claims">
            {g.nuances.map((n) => (
              <li key={n.topic + n.detail}>
                <strong>{n.topic.replace(/_/g, ' ')}:</strong> {n.detail} {ev(n.evidence)}
              </li>
            ))}
          </ul>
        </section>
      )}

      {(g.unverified ?? []).length > 0 && (
        <section className="panel panel-warm" aria-labelledby="unverified">
          <h2 id="unverified">What we could not verify</h2>
          <ul>
            {(g.unverified ?? []).map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
        </section>
      )}

      {g.probes.length > 0 && (
        <section aria-labelledby="checks">
          <h2 id="checks">Automated checks we ran</h2>
          <p className="muted small">
            Safe, anonymous requests made by our code. No accounts, no logins, no forms.
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th scope="col">Check</th>
                  <th scope="col">Outcome</th>
                  <th scope="col">Result</th>
                  <th scope="col">When (UTC)</th>
                </tr>
              </thead>
              <tbody>
                {g.probes.map((p) => (
                  <tr key={p.id} id={`probe-${p.id}`}>
                    <td>
                      {p.id}
                      <div className="small muted break">{p.target_url}</div>
                    </td>
                    <td>
                      <span className={`outcome outcome-${p.outcome}`}>
                        {p.outcome.replace('_', ' ')}
                      </span>
                    </td>
                    <td>{p.summary}</td>
                    <td className="nowrap">{formatDate(p.ran_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section aria-labelledby="sources">
        <h2 id="sources">Sources</h2>
        <ol className="sources">
          {g.sources.map((s) => (
            <li key={s.id} id={`source-${s.id}`}>
              <a href={s.url} target="_blank" rel="noreferrer">
                {s.title}
              </a>{' '}
              <span className="muted small">
                ({s.kind}, checked {s.checked_on})
              </span>
            </li>
          ))}
        </ol>
      </section>

      <p className="muted small">
        Generated by {g.meta.generated_by === 'library' ? 'curated library' : 'live agent'} on{' '}
        {g.meta.generated_at.slice(0, 10)}.
      </p>
    </article>
  )
}
