import { expect, test } from '@playwright/test'

test('home page loads and reaches the backend', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'OAuth App Setup Guides' })).toBeVisible()
  await expect(page.getByRole('status')).toHaveText('Backend: ok')
})
