import { test, expect } from '@playwright/test'

test.describe('Corrections Review Flow', () => {
  const testJobId = '30dd8235-cc1c-4ef7-a9b7-99d8d8c94547.03_compose.debug'
  
  test.beforeEach(async ({ page }) => {
    // Mock the initial API responses
    await page.route(`**/api/results/${testJobId}`, async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          job_id: testJobId,
          lab_panels: [
            {
              id: 'panel_1',
              name: 'Chemistry Panel',
              test_rows: [
                {
                  id: 'test_1',
                  text: 'Glucose 95 mg/dL (70-100)',
                  test_name: 'Glucose',
                  result_value: '95',
                  units: 'mg/dL',
                  reference_range: '70-100',
                  flag: '',
                  line_number: 1,
                  page: 1,
                  confidence: 0.95,
                  field_confidences: {
                    test_name_clarity: 0.98,
                    value_parse: 0.92,
                    unit_validity: 0.96,
                    reference_range: 0.94
                  }
                },
                {
                  id: 'test_2', 
                  text: 'Creatinine 1.1 mg/dL (0.6-1.3) H',
                  test_name: 'Creatinine',
                  result_value: '1.1',
                  units: 'mg/dL',
                  reference_range: '0.6-1.3',
                  flag: 'H',
                  line_number: 2,
                  page: 1,
                  confidence: 0.89,
                  field_confidences: {
                    test_name_clarity: 0.95,
                    value_parse: 0.88,
                    unit_validity: 0.92,
                    reference_range: 0.85
                  }
                }
              ],
              panel_score: 0.92,
              needs_review: false,
              review_reasons: []
            }
          ],
          document_info: {
            needs_review: false,
            document_score: 0.91,
            confidence_distribution: { high: 15, medium: 3, low: 0 }
          }
        })
      })
    })

    // Mock extracted text endpoint
    await page.route(`**/api/results/${testJobId}/extracted-text`, async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          pages: [
            {
              page: 1,
              lines: [
                {
                  text: 'Lab Report Header',
                  bbox: [10, 10, 200, 30],
                  confidence: 0.98,
                  role: 'HEADER_FIELD'
                },
                {
                  text: 'Glucose 95 mg/dL (70-100)',
                  bbox: [10, 50, 300, 70],
                  confidence: 0.95,
                  role: 'TEST_ROW'
                },
                {
                  text: 'Creatinine 1.1 mg/dL (0.6-1.3) H',
                  bbox: [10, 80, 320, 100],
                  confidence: 0.89,
                  role: 'TEST_ROW'
                }
              ]
            }
          ]
        })
      })
    })

    // Mock health check
    await page.route('**/api/health', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true })
      })
    })
  })

  test('should load review page and perform correction workflow', async ({ page }) => {
    // Track API calls
    const apiCalls: Array<{ method: string; url: string; status: number }> = []
    
    page.on('response', response => {
      if (response.url().includes('/api/')) {
        apiCalls.push({
          method: response.request().method(),
          url: response.url(),
          status: response.status()
        })
      }
    })

    // 1. Mock initial GET corrections to return empty
    await page.route(`**/api/results/${testJobId}/corrections`, async route => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            corrections: [],
            history: []
          })
        })
      }
    }, { times: 1 })

    // 2. Navigate to review page
    await page.goto(`/review/${testJobId}`)

    // 3. Wait for page to load and initial API calls
    await page.waitForSelector('[data-testid="review-page"]', { timeout: 10000 })
    
    // Wait for initial corrections GET call
    await page.waitForResponse(response => 
      response.url().includes(`/results/${testJobId}/corrections`) && 
      response.request().method() === 'GET' &&
      response.status() === 200
    )

    // Verify initial state shows no corrections
    const initialCorrectionsCall = apiCalls.find(call => 
      call.url.includes('/corrections') && call.method === 'GET'
    )
    expect(initialCorrectionsCall?.status).toBe(200)

    // 4. Find the first test row and edit the result value
    const firstTestRow = page.locator('[data-testid="test-row"]').first()
    await expect(firstTestRow).toBeVisible()

    // Click on the result value field to edit it
    const resultValueField = firstTestRow.locator('[data-testid="result-value-field"]')
    await resultValueField.click()

    // Enter new value
    const resultValueInput = firstTestRow.locator('input[placeholder*="result"]').first()
    await resultValueInput.fill('96')
    
    // Save the field edit (press Enter or click save button)
    await resultValueInput.press('Enter')

    // 5. Verify the Save button is now enabled
    const saveButton = page.locator('button:has-text("Save Corrections")')
    await expect(saveButton).toBeEnabled()

    // 6. Mock the POST corrections endpoint
    let postRequestBody: any = null
    await page.route(`**/api/results/${testJobId}/corrections`, async route => {
      if (route.request().method() === 'POST') {
        postRequestBody = await route.request().postDataJSON()
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            saved: true,
            corrections_count: 1
          })
        })
      }
    }, { times: 1 })

    // 7. Mock the subsequent GET corrections to return the saved correction
    await page.route(`**/api/results/${testJobId}/corrections`, async route => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            corrections: [
              {
                op: "replace",
                path: "panels[0].test_rows[0].result_value",
                field: "result_value",
                value: "96",
                reason: "manual correction"
              }
            ],
            history: [
              {
                at: new Date().toISOString(),
                result_id: testJobId,
                corrections: [
                  {
                    op: "replace",
                    path: "panels[0].test_rows[0].result_value",
                    field: "result_value", 
                    value: "96",
                    reason: "manual correction"
                  }
                ],
                reviewer: "ui",
                source: "review-ui",
                version: 1,
                ui_build: null
              }
            ]
          })
        })
      }
    })

    // 8. Click Save Corrections button
    await saveButton.click()

    // 9. Wait for POST request to complete
    await page.waitForResponse(response => 
      response.url().includes(`/results/${testJobId}/corrections`) && 
      response.request().method() === 'POST' &&
      response.status() === 200
    )

    // 10. Verify POST request body has correct Shape A format
    expect(postRequestBody).toBeTruthy()
    expect(postRequestBody.corrections).toBeInstanceOf(Array)
    expect(postRequestBody.corrections.length).toBe(1)
    expect(postRequestBody.corrections[0]).toMatchObject({
      op: "replace",
      path: expect.stringContaining("result_value"),
      field: "result_value",
      value: "96",
      reason: "manual correction"
    })
    expect(postRequestBody.reviewer).toBe("ui")
    expect(postRequestBody.source).toBe("review-ui")
    expect(postRequestBody.version).toBe(1)

    // 11. Wait for success toast
    await expect(page.locator('.toast:has-text("Corrections saved successfully")')).toBeVisible()

    // 12. Wait for subsequent GET request to fetch updated corrections
    await page.waitForResponse(response => 
      response.url().includes(`/results/${testJobId}/corrections`) && 
      response.request().method() === 'GET' &&
      response.status() === 200,
      { timeout: 5000 }
    )

    // 13. Verify the final API call sequence
    const postCall = apiCalls.find(call => 
      call.url.includes('/corrections') && call.method === 'POST'
    )
    const finalGetCall = apiCalls.filter(call => 
      call.url.includes('/corrections') && call.method === 'GET'
    )

    expect(postCall?.status).toBe(200)
    expect(finalGetCall.length).toBeGreaterThanOrEqual(2) // Initial + after save
    expect(finalGetCall.every(call => call.status === 200)).toBe(true)

    // 14. Verify Save button is disabled again (no pending changes)
    await expect(saveButton).toBeDisabled()
  })

  test('should handle validation errors gracefully', async ({ page }) => {
    // Mock POST to return validation error
    await page.route(`**/api/results/${testJobId}/corrections`, async route => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 422,
          contentType: 'application/json',
          body: JSON.stringify({
            detail: "invalid_payload",
            errors: [
              {
                type: "missing",
                loc: ["body", "corrections"],
                msg: "Field required"
              }
            ],
            hint: "Send {corrections:[...]} with valid correction objects"
          })
        })
      }
    })

    // Mock initial GET corrections
    await page.route(`**/api/results/${testJobId}/corrections`, async route => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ corrections: [], history: [] })
        })
      }
    })

    await page.goto(`/review/${testJobId}`)
    await page.waitForSelector('[data-testid="review-page"]')

    // Make an edit and try to save
    const firstTestRow = page.locator('[data-testid="test-row"]').first()
    const resultValueField = firstTestRow.locator('[data-testid="result-value-field"]')
    await resultValueField.click()
    
    const resultValueInput = firstTestRow.locator('input[placeholder*="result"]').first()
    await resultValueInput.fill('invalid')
    await resultValueInput.press('Enter')

    const saveButton = page.locator('button:has-text("Save Corrections")')
    await saveButton.click()

    // Should show error toast with structured error message
    await expect(page.locator('.toast:has-text("invalid_payload")')).toBeVisible()
  })

  test('should handle empty corrections appropriately', async ({ page }) => {
    // Mock initial GET and subsequent calls
    await page.route(`**/api/results/${testJobId}/corrections`, async route => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ corrections: [], history: [] })
        })
      }
    })

    await page.goto(`/review/${testJobId}`)
    await page.waitForSelector('[data-testid="review-page"]')

    // Try to save without making any edits
    const saveButton = page.locator('button:has-text("Save Corrections")')
    
    // Should be disabled when no changes
    await expect(saveButton).toBeDisabled()

    // Should show info toast if somehow clicked
    // (This tests the frontend validation before API call)
  })
})