/* Generated from schema/guide.schema.json by npm run gen:types. Do not edit by hand. */

export type AgentCan = string[]
export type AgentDid = string[]
/**
 * @minItems 1
 */
export type HumanMust = [string, ...string[]]
export type Category = string
export type DeveloperConsoleUrl = string | null
/**
 * @minItems 1
 */
export type DocsUrls = [string, ...string[]]
export type Name = string
export type Slug = string
export type Website = string
export type Blocker1 = string
export type Contact = string | null
export type EvidenceLabel = 'TESTED' | 'SOURCED' | 'INFERRED' | 'UNVERIFIED'
export type Note = string | null
export type ProbeIds = string[]
export type SourceIds = string[]
export type HowToGetPast = string
export type Blockers = Blocker[]
export type Detail = string
export type ManagedOauth = 'yes' | 'no' | 'unknown'
export type SnapshotDate = string
export type Level = 'Easy' | 'Medium' | 'Hard' | 'Very hard'
export type Reason = string
export type GeneratedAt = string
export type GeneratedBy = 'library' | 'live_agent'
export type Model = string | null
export type RunSeconds = number | null
export type SchemaVersion = '1'
export type SourcesCount = number
export type Detail1 = string
export type Topic =
  | 'refresh_tokens'
  | 'token_expiry'
  | 'pkce'
  | 'redirect_uris'
  | 'sandbox_vs_production'
  | 'rate_limits'
  | 'tenancy'
  | 'other'
export type Nuances = Nuance[]
export type HttpStatus = number | null
export type Id = string
export type Kind = 'oidc_discovery' | 'oauth_metadata' | 'authorize_endpoint' | 'url_reachable'
/**
 * confirmed: the thing exists and works; not_found: definitely absent; inconclusive: blocked, timed out or unclear (cannot back a TESTED claim)
 */
export type Outcome = 'confirmed' | 'not_found' | 'inconclusive'
export type RanAt = string
export type Summary = string
export type TargetUrl = string
export type Probes = Probe[]
export type Detail2 = string
export type Name1 = string
export type Required = 'yes' | 'no' | 'conditional'
export type Requirements = Requirement[]
export type CommonRejections = string[]
export type Required1 = 'yes' | 'no' | 'conditional'
export type Trigger = string
export type TypicalWait = string
export type WhatToSubmit = string[]
export type Name2 = string
export type Purpose = string
export type Sensitivity = 'standard' | 'sensitive' | 'restricted'
export type TriggersReview = boolean
export type Scopes = ScopeInfo[]
export type CheckedOn = string
export type Id1 = string
export type Kind1 = 'official' | 'community' | 'other'
export type Title = string
export type Url = string
export type Sources = Source[]
/**
 * @minItems 1
 */
export type Steps = [Step, ...Step[]]
export type Action = string
export type ExpectedResult = string
export type Order = number
export type Title1 = string
export type WhereUrl = string | null
export type Who = 'agent' | 'human' | 'either'
export type Summary1 = string
/**
 * Short label, e.g. 'None' or '2-6 weeks'
 */
export type ApprovalWait = string
export type ApprovalWaitDaysMax = number
export type ApprovalWaitDaysMin = number
/**
 * Plain explanation of the estimate and what changes it
 */
export type Detail3 = string | null
/**
 * Short label for cards, e.g. '30-60 min'
 */
export type HandsOn = string
export type HandsOnMinutesMax = number
export type HandsOnMinutesMin = number
/**
 * What we could not verify, in plain words
 */
export type Unverified = string[]

export interface Guide {
  agent_vs_human: AgentVsHuman
  app: AppInfo
  blockers: Blockers
  composio_note: ComposioNote
  difficulty: Difficulty
  meta: Meta
  nuances: Nuances
  probes: Probes
  requirements: Requirements
  review_process: ReviewProcess
  scopes: Scopes
  sources: Sources
  steps: Steps
  summary: Summary1
  time: TimeEstimate
  unverified?: Unverified
}
export interface AgentVsHuman {
  agent_can?: AgentCan
  agent_did?: AgentDid
  human_must: HumanMust
}
export interface AppInfo {
  category: Category
  developer_console_url?: DeveloperConsoleUrl
  docs_urls: DocsUrls
  name: Name
  slug: Slug
  website: Website
}
export interface Blocker {
  blocker: Blocker1
  contact?: Contact
  evidence: Evidence
  how_to_get_past: HowToGetPast
}
export interface Evidence {
  label: EvidenceLabel
  note?: Note
  probe_ids?: ProbeIds
  source_ids?: SourceIds
}
export interface ComposioNote {
  detail: Detail
  evidence: Evidence
  managed_oauth: ManagedOauth
  snapshot_date: SnapshotDate
}
export interface Difficulty {
  evidence: Evidence
  level: Level
  reason: Reason
}
export interface Meta {
  generated_at: GeneratedAt
  generated_by: GeneratedBy
  model?: Model
  run_seconds?: RunSeconds
  schema_version?: SchemaVersion
  sources_count: SourcesCount
}
export interface Nuance {
  detail: Detail1
  evidence: Evidence
  topic: Topic
}
/**
 * A safe automated check run by our backend code, never by the model.
 */
export interface Probe {
  http_status?: HttpStatus
  id: Id
  kind: Kind
  outcome: Outcome
  ran_at: RanAt
  summary: Summary
  target_url: TargetUrl
}
export interface Requirement {
  detail: Detail2
  evidence: Evidence
  name: Name1
  required: Required
}
export interface ReviewProcess {
  common_rejections?: CommonRejections
  evidence: Evidence
  required: Required1
  trigger: Trigger
  typical_wait: TypicalWait
  what_to_submit?: WhatToSubmit
}
export interface ScopeInfo {
  evidence: Evidence
  name: Name2
  purpose: Purpose
  sensitivity: Sensitivity
  triggers_review: TriggersReview
}
export interface Source {
  checked_on: CheckedOn
  id: Id1
  kind: Kind1
  title: Title
  url: Url
}
export interface Step {
  action: Action
  evidence: Evidence
  expected_result: ExpectedResult
  order: Order
  title: Title1
  where_url?: WhereUrl
  who: Who
}
export interface TimeEstimate {
  approval_wait: ApprovalWait
  approval_wait_days_max: ApprovalWaitDaysMax
  approval_wait_days_min: ApprovalWaitDaysMin
  detail?: Detail3
  evidence: Evidence
  hands_on: HandsOn
  hands_on_minutes_max: HandsOnMinutesMax
  hands_on_minutes_min: HandsOnMinutesMin
}
