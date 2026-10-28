import { expect, test } from '@playwright/test'

test('browse the library, open a guide and copy it as Markdown', async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write'])
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1 })).toContainText('OAuth app approved')
  await page.getByRole('searchbox').fill('github')
  await page.getByRole('link', { name: 'GitHub' }).click()
  await expect(page).toHaveURL(/\/guides\/github$/)
  await expect(page.getByRole('heading', { level: 1, name: 'GitHub' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Steps' })).toBeVisible()
  await page.getByRole('button', { name: 'Copy as Markdown' }).click()
  await expect(page.getByText('Markdown copied.')).toBeVisible()
  const copied = await page.evaluate(() => navigator.clipboard.readText())
  expect(copied).toContain('# OAuth app setup guide: GitHub')
})

test('a shared guide link opens directly', async ({ page }) => {
  await page.goto('/guides/google-gmail')
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Gmail')
})
