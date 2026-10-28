import type { Evidence } from '../types/guide'
import { EvidenceLabelBadge } from './badges'

interface Props {
  evidence: Evidence
  sourceNumbers: Record<string, number>
}

export default function EvidenceTag({ evidence, sourceNumbers }: Props) {
  const sourceIds = evidence.source_ids ?? []
  const probeIds = evidence.probe_ids ?? []
  return (
    <span className="evidence-tag">
      <EvidenceLabelBadge label={evidence.label} />
      {sourceIds.map((id) => (
        <a
          key={id}
          href={`#source-${id}`}
          className="ref"
          aria-label={`Source ${sourceNumbers[id]}`}
        >
          [{sourceNumbers[id] ?? id}]
        </a>
      ))}
      {probeIds.map((id) => (
        <a key={id} href={`#probe-${id}`} className="ref" aria-label={`Automated check ${id}`}>
          check: {id}
        </a>
      ))}
      {evidence.note ? (
        <details className="evidence-note">
          <summary>why</summary>
          {evidence.note}
        </details>
      ) : null}
    </span>
  )
}
