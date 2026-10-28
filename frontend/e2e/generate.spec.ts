import { expect, test } from '@playwright/test'

// The live agent endpoint is faked inside the browser: no real model or search calls.
const stream = [
  { type: 'step', step: 'research', status: 'running', message: 'Searching...' },
  {
    type: 'step',
    step: 'research',
    status: 'done',
    message: 'Identified GitHub (https://github.com).',
  },
  {
    type: 'probe',
    id: 'oidc',
    target: 'https://github.com/.well-known/openid-configuration',
    outcome: 'not_found',
    summary: '404',
  },
  { type: 'step', step: 'probes', status: 'done', message: '1 of 1 checks were conclusive.' },
  { type: 'done', slug: 'github', cached: false, from: 'generated' },
]
  .map((e) => `data: ${JSON.stringify(e)}\n\n`)
  .join('')

test('investigate an app, watch progress, open the guide', async ({ page }) => {
  await page.route('**/api/generate', (route) =>
    route.fulfill({ status: 200, contentType: 'text/event-stream', body: stream }),
  )
  await page.goto('/')
  await page.getByRole('link', { name: 'Investigate an app' }).click()
  await page.getByRole('textbox').fill('GitHub')
  await page.getByRole('button', { name: 'Investigate' }).click()
  await expect(page.getByText('Identified GitHub (https://github.com).')).toBeVisible()
  await expect(page.getByText('https://github.com/.well-known/openid-configuration')).toBeVisible()
  await page.getByRole('link', { name: 'Open the guide' }).click()
  await expect(page).toHaveURL(/\/guides\/github$/)
  await expect(page.getByRole('heading', { level: 1, name: 'GitHub' })).toBeVisible()
})
