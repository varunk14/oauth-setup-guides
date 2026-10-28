import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockApi, renderAt, sampleGuide } from '../test-utils'

afterEach(() => vi.unstubAllGlobals())

describe('GuidePage', () => {
  it('renders the guide with evidence labels, checks and sources', async () => {
    mockApi({ '/api/guides/example-app': { body: sampleGuide } })
    renderAt('/guides/example-app')
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Example App' }),
    ).toBeInTheDocument()
    expect(screen.getByText('10-20 min')).toBeInTheDocument()
    expect(screen.getAllByText('TESTED').length).toBeGreaterThan(0)
    expect(screen.getAllByText('SOURCED').length).toBeGreaterThan(0)
    expect(screen.getByRole('heading', { name: 'What we could not verify' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Automated checks we ran' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Example OAuth docs' })).toHaveAttribute(
      'href',
      'https://example.com/docs/oauth',
    )
    expect(screen.getAllByText('You').length).toBeGreaterThan(0)
  })

  it('copies the guide as Markdown', async () => {
    const user = userEvent.setup()
    mockApi({
      '/api/guides/example-app': { body: sampleGuide },
      '/api/guides/example-app/markdown': { body: '# OAuth app setup guide: Example App\n' },
    })
    const writeText = vi.spyOn(navigator.clipboard, 'writeText').mockResolvedValue()
    renderAt('/guides/example-app')
    await user.click(await screen.findByRole('button', { name: 'Copy as Markdown' }))
    expect(writeText).toHaveBeenCalledWith('# OAuth app setup guide: Example App\n')
    expect(await screen.findByText('Markdown copied.')).toBeInTheDocument()
  })

  it('shows a helpful page for an unknown app', async () => {
    mockApi({ '/api/guides/nope': { status: 404, body: { detail: "No guide found for 'nope'." } } })
    renderAt('/guides/nope')
    expect(await screen.findByRole('heading', { name: /No guide for/ })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Browse the guide library' })).toBeInTheDocument()
  })
})
