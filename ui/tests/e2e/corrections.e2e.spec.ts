import { test, expect } from '@playwright/test'
import { minimalLabResult, healthyResponse, correctionsMap, isCorrectionsPostArray } from './fixtures'

// Utility to set up common routes required by the Review Editor
async function setupCommonRoutes(page: any, id = 'e2e-corr-id') {
  // Health
  await page.route('**/api/health', async route => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(healthyResponse) })
  })

  // Result
  await page.route(new RegExp(`/api/results/${id.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}$`), async route => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(minimalLabResult) })
  })
}

test.describe('Corrections Flow (E2E)', () => {
  test('1) Empty state when no corrections exist', async ({ page }) => {
    const id = 'e2e-empty'

    await setupCommonRoutes(page, id)

    // Corrections GET -> 404 (no file on disk)
    await page.route(new RegExp(`/api/results/${id}/corrections$`), async route => {
      await route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ detail: 'Not Found' }) })
    })

    await page.goto(`/review/${id}.03_compose.debug`)

    // Editor renders sections; empty state copy is visible for sections with no defs or values
    await expect(page.getByText('Review & Edit')).toBeVisible()
    await expect(page.getByText('Nothing to show here yet. You can still add values manually.')).toBeVisible()
  })

  test('2) Add a correction: UI POSTs array; server appends; GET shows new item', async ({ page }) => {
    const id = 'e2e-add'

    await setupCommonRoutes(page, id)

    // Initial corrections GET -> 404
    let getCount = 0
    await page.route(new RegExp(`/api/results/${id}/corrections$`), async route => {
      getCount++
      // First GET: 404 (no file)
      if (getCount === 1) {
        return route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ detail: 'Not Found' }) })
      }
      // Subsequent GETs: include the new correction (server map shape)
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(correctionsMap({ 'vendor.name': 'Acme Labs' })),
      })
    })

    // Capture POST, assert array payload
    let postedBody: unknown = undefined
    await page.route(new RegExp(`/api/results/${id}/corrections$`), async route => {
      if (route.request().method() === 'POST') {
        postedBody = route.request().postDataJSON()
        // Return 200 OK
        return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) })
      }
      // Fallback for GETs on same pattern handled above
      return route.fallback()
    })

    await page.goto(`/review/${id}.03_compose.debug`)

    // Change a known field and save it (press Enter to trigger save)
    const vendorName = page.getByLabel('Lab / Vendor Name')
    await vendorName.click()
    await vendorName.fill('Acme Labs')
    await vendorName.press('Enter')

    // Wait for POST and subsequent GET
    await expect.poll(() => (postedBody ? 'ok' : 'waiting')).toBe('ok')

    // Assert POST body is an array of corrections
    expect(isCorrectionsPostArray(postedBody)).toBeTruthy()

    // UI should reflect saved value (field no longer dirty, no Save button visible)
    await expect(page.getByLabel('Lab / Vendor Name')).toHaveValue('Acme Labs')
    await expect(page.getByTitle('Save field')).toHaveCount(0)
  })

  test('3) Corrupted corrections file -> POST 422; UI shows actionable error', async ({ page }) => {
    const id = 'e2e-corrupted'

    await setupCommonRoutes(page, id)

    // Corrections GET -> existing object (server would later fail on append)
    await page.route(new RegExp(`/api/results/${id}/corrections$`), async route => {
      if (route.request().method() === 'GET') {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          // Simulate legacy/object shape on disk; UI will still render, but POST append should fail
          body: JSON.stringify({ items: [] }),
        })
      }
      return route.fallback()
    })

    // POST returns HTTP 422 with CORRECTIONS_FILE_WRONG_TYPE structure
    await page.route(new RegExp(`/api/results/${id}/corrections$`), async route => {
      if (route.request().method() === 'POST') {
        return route.fulfill({
          status: 422,
          contentType: 'application/json',
          body: JSON.stringify({
            error: 'CORRECTIONS_FILE_WRONG_TYPE',
            message: `Corrections file for result_id='${id}' has wrong format: expected array, found object`,
            expected: 'array',
            found: 'object',
            result_id: id,
            fix: 'Run corrections migration or delete the file to allow recreation as an array',
          }),
        })
      }
      return route.fallback()
    })

    await page.goto(`/review/${id}.03_compose.debug`)

    // Change a field and attempt to save
    const vendorName = page.getByLabel('Lab / Vendor Name')
    await vendorName.click()
    await vendorName.fill('Broken Save')
    await vendorName.press('Enter')

    // Expect an error surfaced to the user with actionable next steps. The UI uses react-hot-toast for error toasts.
    // Look for either the explicit error code message or the fix guidance.
    await expect(
      page.getByText(/Corrections file format error|Run corrections migration or delete the file/i)
    ).toBeVisible()
  })
})

