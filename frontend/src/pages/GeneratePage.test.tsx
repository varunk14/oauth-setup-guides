import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderAt, sampleGuide } from '../test-utils'

function sse(events: object[]): string {
  return events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join('')
}

function mockGenerate(body: string, extra: Record<string, unknown> = {}) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input.toString()
    if (url === '/api/generate') return new Response(body, { status: 200 })
    if (url in extra) return new Response(JSON.stringify(extra[url]), { status: 200 })
    return new Response(JSON.stringify({ detail: 'not mocked' }), { status: 500 })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => vi.unstubAllGlobals())

describe('GeneratePage', () => {
  it('shows live progress, check results and a link to the finished guide', async () => {
    const user = userEvent.setup()
    const fetchMock = mockGenerate(
      sse([
        { type: 'step', step: 'research', status: 'running', message: 'Searching...' },
        { type: 'step', step: 'research', status: 'done', message: 'Identified Zoom.' },
        { type: 'notice', message: 'openai failed - switched to the backup (gemini+tavily).' },
        {
          type: 'probe',
          id: 'oidc',
          target: 'https://zoom.us/.well-known/openid-configuration',
          outcome: 'confirmed',
          summary: 'ok',
        },
        { type: 'done', slug: 'zoom', cached: false, from: 'generated' },
      ]),
    )
    renderAt('/generate')
    await user.type(screen.getByRole('textbox'), 'Zoom')
    await user.click(screen.getByRole('button', { name: 'Investigate' }))
    expect(await screen.findByText('Identified Zoom.')).toBeInTheDocument()
    expect(screen.getByText(/switched to the backup/)).toBeInTheDocument()
    expect(screen.getByText('https://zoom.us/.well-known/openid-configuration')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open the guide' })).toHaveAttribute(
      'href',
      '/guides/zoom',
    )
    const init = fetchMock.mock.calls[0]?.[1] ?? {}
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body as string)).toEqual({ query: 'Zoom' })
  })

  it('shows a clear message when a limit is hit', async () => {
    const user = userEvent.setup()
    mockGenerate(
      sse([
        { type: 'error', code: 'rate_limited', message: 'Try again later, or browse the library.' },
      ]),
    )
    renderAt('/generate')
    await user.type(screen.getByRole('textbox'), 'Zoom')
    await user.click(screen.getByRole('button', { name: 'Investigate' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Try again later, or browse the library.',
    )
  })

  it('says so when the app does not use OAuth', async () => {
    const user = userEvent.setup()
    mockGenerate(sse([{ type: 'no_oauth', message: 'It uses API keys.' }]))
    renderAt('/generate')
    await user.type(screen.getByRole('textbox'), 'Some API')
    await user.click(screen.getByRole('button', { name: 'Investigate' }))
    expect(await screen.findByText('No OAuth app needed')).toBeInTheDocument()
  })

  it('opens a cached guide straight away', async () => {
    const user = userEvent.setup()
    mockGenerate(sse([{ type: 'done', slug: 'example-app', cached: true, from: 'library' }]), {
      '/api/guides/example-app': sampleGuide,
    })
    renderAt('/generate')
    await user.type(screen.getByRole('textbox'), 'Example App')
    await user.click(screen.getByRole('button', { name: 'Investigate' }))
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Example App' }),
    ).toBeInTheDocument()
  })
})
