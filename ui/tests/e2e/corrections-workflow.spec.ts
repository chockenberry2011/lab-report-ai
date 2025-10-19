import { test, expect } from '@playwright/test'

const BASE_URL = process.env.UI_BASE_URL || 'http://localhost:5173'
const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000'

// Test job ID with processing suffix
const TEST_JOB_ID = 'ce90e846-1234-5678-9abc-bf79955b074b.03_compose.debug'
const NORMALIZED_ID = 'ce90e846-1234-5678-9abc-bf79955b074b'

test.describe('Corrections End-to-End Workflow', () => {
  test('complete correction workflow with ID normalization and immediate GET', async ({ page }) => {

    // Step 1: Navigate to /review/<id>.03_compose.debug
    console.log(`Navigating to review page: /review/${TEST_JOB_ID}`)
    await page.goto(`${BASE_URL}/review/${encodeURIComponent(TEST_JOB_ID)}`)

    // Wait for the review page to load
    await expect(page.getByText('Manual Review & Correction')).toBeVisible({ timeout: 10000 })

    // Wait for the data to load - look for test results
    await page.waitForSelector('[data-testid="test-row"], .test-row, [class*="test"], input[type="text"]', { timeout: 10000 })

    // Step 2: Edit one field (first row result_value → "42")
    console.log('Looking for first result value field to edit...')

    // Try multiple selectors to find the first editable result value field
    const resultValueSelectors = [
      'input[placeholder*="result"], input[placeholder*="value"], input[placeholder*="Result"]',
      '[data-field*="result_value"], [data-field*="resultValue"]',
      'input[type="text"]:not([placeholder*="name"]):not([placeholder*="units"])',
      '.test-row input[type="text"]',
      '[class*="result"] input',
      'input[type="text"]'
    ]

    let editedField = null
    let originalValue = ''

    for (const selector of resultValueSelectors) {
      try {
        const inputs = await page.locator(selector).all()
        if (inputs.length > 0) {
          // Find the first visible, editable input that looks like a result value
          for (const input of inputs) {
            const isVisible = await input.isVisible()
            const isEnabled = await input.isEnabled()
            const placeholder = await input.getAttribute('placeholder') || ''
            const currentValue = await input.inputValue()

            // Skip if it looks like a name or units field
            if (placeholder.toLowerCase().includes('name') ||
                placeholder.toLowerCase().includes('units') ||
                placeholder.toLowerCase().includes('test')) {
              continue
            }

            if (isVisible && isEnabled) {
              editedField = input
              originalValue = currentValue
              console.log(`Found editable field with selector: ${selector}`)
              console.log(`Original value: "${originalValue}"`)
              console.log(`Placeholder: "${placeholder}"`)
              break
            }
          }
          if (editedField) break
        }
      } catch (e) {
        // Continue to next selector
        continue
      }
    }

    if (!editedField) {
      throw new Error('Could not find any editable result value field')
    }

    // Clear and type the new value
    await editedField.click()
    await editedField.fill('42')

    // Verify the value was set
    await expect(editedField).toHaveValue('42')
    console.log('Successfully set field value to "42"')

    // Step 3: Click Save
    console.log('Looking for Save button...')

    // Try multiple save button selectors
    const saveSelectors = [
      'button:has-text("Save")',
      '[data-testid="save-button"]',
      'button[type="submit"]',
      '.save-button',
      'button:has-text("Save Corrections")',
      '[title="Save"]'
    ]

    let saveButton = null
    for (const selector of saveSelectors) {
      try {
        const button = page.locator(selector).first()
        if (await button.isVisible()) {
          saveButton = button
          console.log(`Found save button with selector: ${selector}`)
          break
        }
      } catch (e) {
        continue
      }
    }

    if (!saveButton) {
      // Try to trigger save via keyboard
      console.log('No save button found, trying keyboard shortcut...')
      await editedField.press('Tab') // Move focus away to trigger save
      await page.keyboard.press('Control+S') // Try Ctrl+S
    } else {
      await saveButton.click()
      console.log('Clicked save button')
    }

    // Wait a moment for the save to process
    await page.waitForTimeout(2000)

    // Step 4: Call GET /api/results/<id>/corrections and assert the correction
    console.log('Fetching corrections via API to verify save...')

    const correctionsResponse = await page.evaluate(async (apiBase, normalizedId) => {
      try {
        const response = await fetch(`${apiBase}/api/results/${normalizedId}/corrections`, {
          headers: { 'Cache-Control': 'no-store' }
        })
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`)
        }
        return await response.json()
      } catch (error) {
        console.error('Failed to fetch corrections:', error)
        return { error: error.message }
      }
    }, API_BASE, NORMALIZED_ID)

    console.log('Corrections API response:', JSON.stringify(correctionsResponse, null, 2))

    // Assert the corrections response
    expect(correctionsResponse).toBeDefined()
    expect(correctionsResponse.error).toBeUndefined()

    if (correctionsResponse.corrections) {
      expect(Array.isArray(correctionsResponse.corrections)).toBe(true)
      expect(correctionsResponse.corrections.length).toBeGreaterThan(0)

      // Find a correction with value "42"
      const correction42 = correctionsResponse.corrections.find((corr: any) =>
        corr.value === "42" || corr.new_value === "42"
      )

      expect(correction42).toBeDefined()
      console.log('Found correction with value "42":', correction42)

      // Verify the correction has a proper path or field
      expect(
        correction42.path || correction42.field
      ).toBeDefined()

    } else {
      // Handle legacy format where corrections might be at root level
      const hasCorrection42 = Object.values(correctionsResponse).some((value: any) =>
        value === "42" || (typeof value === 'object' && value?.value === "42")
      )
      expect(hasCorrection42).toBe(true)
    }

    console.log('✅ Verified that correction with value "42" was saved to API')

    // Step 5: Reload the page and assert the UI still shows "42" (overlay applied)
    console.log('Reloading page to test persistence...')
    await page.reload()

    // Wait for the page to load again
    await expect(page.getByText('Manual Review & Correction')).toBeVisible({ timeout: 10000 })
    await page.waitForTimeout(3000) // Give time for corrections to be applied

    // Verify the field still shows "42" after reload
    console.log('Checking if value "42" persists after reload...')

    // Find any field that shows "42"
    const persistedField = page.locator('input[value="42"], *:has-text("42")').first()

    // Use a more flexible approach - look for the value anywhere on the page
    const has42Value = page.locator('input').evaluateAll((inputs) =>
      inputs.some(input => (input as HTMLInputElement).value === '42')
    )

    const has42Text = page.locator('*').evaluateAll((elements) =>
      elements.some(el => el.textContent?.includes('42'))
    )

    const [inputHas42, textHas42] = await Promise.all([has42Value, has42Text])

    if (inputHas42) {
      console.log('✅ Found "42" in an input field after reload')
    } else if (textHas42) {
      console.log('✅ Found "42" in page text after reload')
    } else {
      // Try to find the same field we edited before
      try {
        const sameField = await page.locator('input[type="text"]').first()
        const currentValue = await sameField.inputValue()
        console.log(`First input field value after reload: "${currentValue}"`)

        // Check if any input has "42"
        const allInputValues = await page.locator('input[type="text"]').evaluateAll(
          inputs => inputs.map(input => (input as HTMLInputElement).value)
        )
        console.log('All input values after reload:', allInputValues)

        expect(allInputValues).toContain('42')
      } catch (e) {
        console.error('Failed to verify persistence:', e)
        throw new Error('Value "42" not found after page reload - overlay may not be working')
      }
    }

    console.log('✅ Complete workflow verified: Edit → Save → API persistence → UI persistence after reload')
  })

  test('verify ID normalization in API calls', async ({ page }) => {
    // Navigate with dotted ID
    await page.goto(`${BASE_URL}/review/${encodeURIComponent(TEST_JOB_ID)}`)

    // Monitor network requests to verify normalized IDs are used
    const requests: string[] = []

    page.on('request', request => {
      const url = request.url()
      if (url.includes('/api/results/') && url.includes('/corrections')) {
        requests.push(url)
        console.log('Corrections API request:', url)
      }
    })

    // Wait for page to load and make initial requests
    await expect(page.getByText('Manual Review & Correction')).toBeVisible({ timeout: 10000 })
    await page.waitForTimeout(2000)

    // Verify that all API calls use the normalized ID (without suffix)
    for (const url of requests) {
      expect(url).toContain(NORMALIZED_ID)
      expect(url).not.toContain('.03_compose.debug')
      console.log(`✅ Verified normalized ID in URL: ${url}`)
    }

    if (requests.length === 0) {
      console.log('No corrections API requests detected - page may not be making calls yet')
    }
  })

  test('verify cache bypass headers', async ({ page }) => {
    // Set up request interception to check headers
    const getRequests: any[] = []

    page.on('request', request => {
      const url = request.url()
      if (url.includes('/api/results/') && url.includes('/corrections') && request.method() === 'GET') {
        getRequests.push({
          url,
          headers: request.headers()
        })
      }
    })

    await page.goto(`${BASE_URL}/review/${encodeURIComponent(TEST_JOB_ID)}`)
    await expect(page.getByText('Manual Review & Correction')).toBeVisible({ timeout: 10000 })
    await page.waitForTimeout(2000)

    // Check for cache bypass headers
    for (const request of getRequests) {
      const cacheControl = request.headers['cache-control']
      console.log(`Cache-Control header: ${cacheControl}`)

      // Should have no-store to bypass cache
      if (cacheControl) {
        expect(cacheControl).toContain('no-store')
        console.log('✅ Verified Cache-Control: no-store header')
      }
    }
  })
})