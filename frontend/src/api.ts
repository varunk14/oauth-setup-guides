import type { Guide, Level } from './types/guide'

export interface GuideSummary {
  slug: string
  name: string
  category: string
  website: string
  summary: string
  difficulty: Level
  difficulty_reason: string
  hands_on: string
  approval_wait: string
  approval_wait_days_max: number
  review_required: 'yes' | 'no' | 'conditional'
  managed_oauth: 'yes' | 'no' | 'unknown'
  generated_by: 'library' | 'live_agent'
  generated_at: string
}

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request(path: string, signal?: AbortSignal): Promise<Response> {
  const response = await fetch(path, { signal })
  if (!response.ok) {
    let message = `Request failed (HTTP ${response.status}).`
    try {
      const body = (await response.json()) as { detail?: unknown }
      if (typeof body.detail === 'string') message = body.detail
    } catch {
      // Body was not JSON; keep the generic message.
    }
    throw new ApiError(response.status, message)
  }
  return response
}

export async function listGuides(signal?: AbortSignal): Promise<GuideSummary[]> {
  return (await (await request('/api/guides', signal)).json()) as GuideSummary[]
}

export async function getGuide(slug: string, signal?: AbortSignal): Promise<Guide> {
  return (await (await request(`/api/guides/${encodeURIComponent(slug)}`, signal)).json()) as Guide
}

export async function getGuideMarkdown(slug: string): Promise<string> {
  return (await request(`/api/guides/${encodeURIComponent(slug)}/markdown`)).text()
}
