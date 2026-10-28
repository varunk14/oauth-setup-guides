import type { EvidenceLabel, Level } from '../types/guide'

const levelClass: Record<Level, string> = {
  Easy: 'level-easy',
  Medium: 'level-medium',
  Hard: 'level-hard',
  'Very hard': 'level-very-hard',
}

export function DifficultyBadge({ level }: { level: Level }) {
  return <span className={`badge ${levelClass[level]}`}>{level}</span>
}

const evidenceHelp: Record<EvidenceLabel, string> = {
  TESTED: 'Our automated check observed this.',
  SOURCED: 'An official or cited page states this.',
  INFERRED: 'Reasoned from sources or community reports.',
  UNVERIFIED: 'We could not confirm this.',
}

export function EvidenceLabelBadge({ label }: { label: EvidenceLabel }) {
  return (
    <span className={`evidence evidence-${label.toLowerCase()}`} title={evidenceHelp[label]}>
      {label}
    </span>
  )
}

const whoText = { human: 'You', agent: 'Agent', either: 'You or agent' } as const

export function WhoBadge({ who }: { who: keyof typeof whoText }) {
  return <span className={`who who-${who}`}>{whoText[who]}</span>
}
