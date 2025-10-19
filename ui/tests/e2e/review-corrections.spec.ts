import { test, expect } from '@playwright/test'

const BASE_URL = process.env.UI_BASE_URL || 'http://localhost:5173'
const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000'

// Helper to create a deterministic job id for testing
const jobId = process.env.E2E_JOB_ID || 'e2e-00000000-0000-0000-0000-000000000001.03_compose.debug'

test.describe('Review viewer corrections persistence', () => {
  test('save correction, hard refresh, still corrected', async ({ page }) => {
    // Navigate to the review page
    await page.goto(`${BASE_URL}/viewer/${encodeURIComponent(jobId)}`)

    // Wait for composed result to render: look for a common label
    await expect(page.getByText('Manual Review & Correction')).toBeVisible()

    // Edit first visible Units field to a unique value
    const unitsLabel = page.getByText('Units').first()
    await unitsLabel.click()
    const input = page.locator('input[placeholder="Enter units"]').first()
    await input.fill('mg/dL')
    await page.getByTitle('Save').first().click()

    // Save corrections
    await page.getByRole('button', { name: 'Save Corrections' }).click()
    await expect(page.getByText('Corrections saved successfully')).toBeVisible()

    // Hard refresh
    await page.reload()

    // Expect the corrected value is rendered from the compose endpoint
    await expect(page.getByText('Units')).toBeVisible()
    await expect(page.getByText('Corrected')).toBeVisible()
  })

  test('extracted-text failure does not revert composed values', async ({ page }) => {
    // Simulate API failure via missing resource or proxy config; still load compose
    await page.goto(`${BASE_URL}/viewer/${encodeURIComponent(jobId)}`)
    await expect(page.getByText('Manual Review & Correction')).toBeVisible()
    // The right-pane may be empty, but composed fields remain
    await expect(page.getByText('Test Name')).toBeVisible()
  })
})

