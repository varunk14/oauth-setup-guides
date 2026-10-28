import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('App', () => {
  it('shows the backend as ok when the health check passes', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify({ status: 'ok', schema_version: '1' }), { status: 200 }),
        ),
    )
    render(<App />)
    expect(screen.getByRole('heading', { name: 'OAuth App Setup Guides' })).toBeInTheDocument()
    expect(await screen.findByText('Backend: ok')).toBeInTheDocument()
  })

  it('shows a clear error when the backend is down', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status: 503 })))
    render(<App />)
    expect(await screen.findByText(/Backend: unreachable/)).toBeInTheDocument()
  })
})
