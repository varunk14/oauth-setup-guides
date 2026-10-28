import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { GuideSummary } from '../api'
import { mockApi, renderAt } from '../test-utils'

const base: GuideSummary = {
  slug: 'github',
  name: 'GitHub',
  category: 'Developer tools',
  website: 'https://github.com',
  summary: 'Self-serve.',
  difficulty: 'Easy',
  difficulty_reason: 'Self-serve form, no review.',
  hands_on: '10-20 min',
  approval_wait: 'none',
  approval_wait_days_max: 0,
  review_required: 'no',
  managed_oauth: 'yes',
  generated_by: 'library',
  generated_at: '2026-10-28T12:00:00Z',
}
const gmail: GuideSummary = {
  ...base,
  slug: 'google-gmail',
  name: 'Gmail (Google)',
  category: 'Email',
  difficulty: 'Very hard',
  difficulty_reason: 'Restricted scopes need a security assessment.',
  approval_wait: '4-12 weeks',
}

afterEach(() => vi.unstubAllGlobals())

describe('LibraryPage', () => {
  it('lists guides with difficulty, time and wait', async () => {
    mockApi({ '/api/guides': { body: [base, gmail] } })
    renderAt('/')
    const cards = await screen.findAllByRole('listitem')
    expect(cards).toHaveLength(2)
    const first = within(cards[0]!)
    expect(first.getByRole('link', { name: 'GitHub' })).toHaveAttribute('href', '/guides/github')
    expect(first.getByText('Easy')).toBeInTheDocument()
    expect(first.getByText('10-20 min')).toBeInTheDocument()
    expect(within(cards[1]!).getByText('4-12 weeks')).toBeInTheDocument()
  })

  it('filters by search text and by difficulty', async () => {
    const user = userEvent.setup()
    mockApi({ '/api/guides': { body: [base, gmail] } })
    renderAt('/')
    await screen.findAllByRole('listitem')
    await user.type(screen.getByRole('searchbox'), 'gmail')
    expect(screen.getAllByRole('listitem')).toHaveLength(1)
    await user.clear(screen.getByRole('searchbox'))
    await user.click(screen.getByRole('button', { name: 'Easy' }))
    expect(screen.getAllByRole('listitem')).toHaveLength(1)
    expect(screen.getByText('GitHub')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Medium' }))
    expect(screen.getByText('No guides match your search.')).toBeInTheDocument()
  })

  it('shows an error when the library cannot load', async () => {
    mockApi({ '/api/guides': { status: 503, body: { detail: 'Service unavailable.' } } })
    renderAt('/')
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load the guide library')
  })
})
