import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'
import App from './App'
import sample from '../../backend/tests/fixtures/sample_guide.json'
import type { Guide } from './types/guide'

export const sampleGuide = sample as unknown as Guide

export function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  )
}

type Routes = Record<string, { status?: number; body: unknown }>

export function mockApi(routes: Routes) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = typeof input === 'string' ? input : input.toString()
    const route = routes[url]
    if (!route) return new Response(JSON.stringify({ detail: 'not mocked' }), { status: 500 })
    const body = typeof route.body === 'string' ? route.body : JSON.stringify(route.body)
    return new Response(body, { status: route.status ?? 200 })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}
