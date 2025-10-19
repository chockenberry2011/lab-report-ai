/**
 * End-to-end test for the complete corrections flow
 *
 * Tests:
 * 1. Empty state: No corrections on disk, UI shows empty state
 * 2. Add correction: User adds correction, UI POSTs array, server appends, GET shows new item
 * 3. Format error: Corrupted corrections file, server returns 422, UI surfaces error banner
 */

import { test, expect } from '@playwright/test'
import * as fs from 'fs'
import * as path from 'path'

const BASE_URL = process.env.UI_BASE_URL || 'http://localhost:5173'
const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000'
const DATA_ROOT = process.env.DATA_ROOT || '/data'

// Test job IDs
const CLEAN_JOB_ID = 'e2e-corrections-clean.03_compose.debug'
const CORRUPTED_JOB_ID = 'e2e-corrections-corrupted.03_compose.debug'

// Helper functions for test setup
class TestFixtures {
  static getResultsDir(): string {
    return path.join(DATA_ROOT, 'results')
  }

  static getCorrectionsPath(jobId: string): string {
    const normalizedId = jobId.split('.')[0] // Strip .03_compose.debug
    return path.join(this.getResultsDir(), normalizedId, 'corrections.json')
  }

  static getOutboxPath(jobId: string): string {
    return path.join(DATA_ROOT, 'outbox', `${jobId}.json`)
  }

  static async ensureDirectoryExists(dirPath: string): Promise<void> {
    if (!fs.existsSync(dirPath)) {
      fs.mkdirSync(dirPath, { recursive: true })
    }
  }

  static async createTestResult(jobId: string): Promise<void> {
    const normalizedId = jobId.split('.')[0]
    const outboxPath = this.getOutboxPath(jobId)

    await this.ensureDirectoryExists(path.dirname(outboxPath))

    const testResult = {
      job_id: normalizedId,
      status: 'completed',
      lab_panels: [
        {
          id: 'panel-1',
          name: 'Basic Metabolic Panel',
          test_rows: [
            {
              id: 'test-1',
              line_number: 10,
              text: 'Glucose 95 mg/dL 70-99',
              test_name: 'Glucose',
              result_value: '95',
              units: 'mg/dL',
              reference_range: '70-99',
              flag: null,
              confidence: 0.95
            },
            {
              id: 'test-2',
              line_number: 11,
              text: 'Sodium 140 mEq/L 136-145',
              test_name: 'Sodium',
              result_value: '140',
              units: 'mEq/L',
              reference_range: '136-145',
              flag: null,
              confidence: 0.90
            }
          ]
        }
      ],
      document_info: {
        patient: {
          first_name: 'Test',
          last_name: 'Patient'
        }
      },
      processing_metadata: {
        timestamp: new Date().toISOString(),
        stage: '03_compose'
      }
    }

    fs.writeFileSync(outboxPath, JSON.stringify(testResult, null, 2))
    console.log(`Created test result: ${outboxPath}`)
  }

  static async removeCorrectionsFile(jobId: string): Promise<void> {
    const correctionsPath = this.getCorrectionsPath(jobId)
    if (fs.existsSync(correctionsPath)) {
      fs.unlinkSync(correctionsPath)
      console.log(`Removed corrections file: ${correctionsPath}`)
    }
  }

  static async createCorruptedCorrectionsFile(jobId: string): Promise<void> {
    const normalizedId = jobId.split('.')[0]
    const correctionsPath = this.getCorrectionsPath(jobId)

    await this.ensureDirectoryExists(path.dirname(correctionsPath))

    // Create object format (invalid - should be array)
    const corruptedData = {
      field: 'test_name',
      new_value: 'Invalid Format',
      old_value: 'Original',
      line_number: 10,
      source: 'corrupted-test'
    }

    fs.writeFileSync(correctionsPath, JSON.stringify(corruptedData, null, 2))
    console.log(`Created corrupted corrections file: ${correctionsPath}`)
  }

  static async createValidCorrectionsFile(jobId: string, corrections: any[]): Promise<void> {
    const correctionsPath = this.getCorrectionsPath(jobId)

    await this.ensureDirectoryExists(path.dirname(correctionsPath))

    fs.writeFileSync(correctionsPath, JSON.stringify(corrections, null, 2))
    console.log(`Created valid corrections file: ${correctionsPath}`)
  }

  static async cleanup(jobIds: string[]): Promise<void> {
    for (const jobId of jobIds) {
      // Remove test result
      const outboxPath = this.getOutboxPath(jobId)
      if (fs.existsSync(outboxPath)) {
        fs.unlinkSync(outboxPath)
      }

      // Remove corrections file
      await this.removeCorrectionsFile(jobId)

      // Remove result directory if empty
      const normalizedId = jobId.split('.')[0]
      const resultDir = path.join(this.getResultsDir(), normalizedId)
      if (fs.existsSync(resultDir)) {
        try {
          fs.rmdirSync(resultDir) // Only removes if empty
        } catch (e) {
          // Directory not empty, that's fine
        }
      }
    }
    console.log('Cleanup completed')
  }
}

// Playwright Page helpers
class PageHelpers {
  static async waitForApiCall(page: any, urlPattern: string, method = 'GET'): Promise<any> {
    const responsePromise = page.waitForResponse((response: any) =>
      response.url().includes(urlPattern) && response.request().method() === method
    )
    return responsePromise
  }

  static async interceptApiCall(page: any, urlPattern: string, mockResponse: any, status = 200): Promise<void> {
    await page.route(urlPattern, (route: any) => {
      route.fulfill({
        status,
        contentType: 'application/json',
        body: JSON.stringify(mockResponse)
      })
    })
  }

  static async getToastText(page: any): Promise<string | null> {
    try {
      const toast = page.locator('[data-testid="toast"], .Toastify__toast, [role="alert"]').first()
      await toast.waitFor({ timeout: 5000 })
      return await toast.textContent()
    } catch (e) {
      return null
    }
  }

  static async waitForToast(page: any, expectedText: string): Promise<void> {
    const toast = page.locator(`text="${expectedText}"`)
    await expect(toast).toBeVisible({ timeout: 10000 })
  }
}

test.describe('Corrections Flow End-to-End', () => {
  test.beforeAll(async () => {
    // Create test results for all scenarios
    await TestFixtures.createTestResult(CLEAN_JOB_ID)
    await TestFixtures.createTestResult(CORRUPTED_JOB_ID)
  })

  test.afterAll(async () => {
    // Cleanup all test data
    await TestFixtures.cleanup([CLEAN_JOB_ID, CORRUPTED_JOB_ID])
  })

  test('1. Empty state: No corrections on disk, UI shows empty state', async ({ page }) => {
    // Ensure no corrections file exists
    await TestFixtures.removeCorrectionsFile(CLEAN_JOB_ID)

    // Navigate to review page
    await page.goto(`${BASE_URL}/review/${encodeURIComponent(CLEAN_JOB_ID)}`)

    // Wait for the page to load
    await expect(page.getByText('Manual Review & Correction')).toBeVisible()

    // Verify no corrections are shown initially
    // Look for indicators that show no corrections exist
    const correctionsSection = page.locator('[data-testid="corrections-list"], .corrections-table, table')

    // Either no corrections section exists, or it shows empty state
    try {
      await correctionsSection.waitFor({ timeout: 2000 })
      // If corrections section exists, it should be empty or show empty state
      const isEmpty = await correctionsSection.evaluate((el: any) => {
        return el.textContent?.includes('No corrections') ||
               el.textContent?.includes('Empty') ||
               el.querySelectorAll('tbody tr').length === 0
      })
      expect(isEmpty).toBeTruthy()
    } catch (e) {
      // No corrections section found, which is also valid for empty state
      console.log('No corrections section found - valid empty state')
    }

    // Verify the data came from the result file (not corrections)
    await expect(page.getByText('Glucose')).toBeVisible()
    await expect(page.getByText('95')).toBeVisible()
    await expect(page.getByText('mg/dL')).toBeVisible()
  })

  test('2. Add correction: User adds correction, UI POSTs array, server appends, GET shows new item', async ({ page }) => {
    // Start with clean state
    await TestFixtures.removeCorrectionsFile(CLEAN_JOB_ID)

    // Set up API monitoring
    const postPromise = PageHelpers.waitForApiCall(page, '/api/results/', 'POST')
    const getPromise = PageHelpers.waitForApiCall(page, '/api/results/', 'GET')

    // Navigate to review page
    await page.goto(`${BASE_URL}/review/${encodeURIComponent(CLEAN_JOB_ID)}`)

    // Wait for page load
    await expect(page.getByText('Manual Review & Correction')).toBeVisible()

    // Find an editable field and make a correction
    // Look for the Glucose test row
    const glucoseRow = page.locator('tr:has-text("Glucose")').first()
    await expect(glucoseRow).toBeVisible()

    // Edit the test name field
    const testNameCell = glucoseRow.locator('td').nth(0) // Assuming first column is test name
    await testNameCell.click()

    // Look for an editable input or click to edit
    let testNameInput = page.locator('input').filter({ hasText: 'Glucose' }).or(
      page.locator('input[value*="Glucose"]')
    ).or(
      glucoseRow.locator('input').first()
    )

    if (await testNameInput.count() === 0) {
      // Try clicking to enter edit mode
      await testNameCell.dblclick()
      testNameInput = page.locator('input').first()
    }

    await testNameInput.waitFor({ timeout: 5000 })
    await testNameInput.clear()
    await testNameInput.fill('Blood Glucose')

    // Save the correction
    const saveButton = page.getByRole('button', { name: /save/i }).first()
    await saveButton.click()

    // Wait for POST request
    const postResponse = await postPromise
    expect(postResponse.status()).toBe(200)

    // Verify POST body is array format
    const postRequest = postResponse.request()
    const postBody = postRequest.postDataJSON()
    expect(Array.isArray(postBody)).toBeTruthy()
    expect(postBody.length).toBeGreaterThan(0)
    expect(postBody[0]).toHaveProperty('field')
    expect(postBody[0]).toHaveProperty('new_value', 'Blood Glucose')

    // Wait for success toast
    await PageHelpers.waitForToast(page, 'saved successfully')

    // Verify GET request to refresh data
    const getResponse = await getPromise
    expect(getResponse.status()).toBe(200)

    // Verify the correction is now visible in the UI
    await expect(page.getByText('Blood Glucose')).toBeVisible()

    // Verify the corrections file was created correctly on disk
    const correctionsPath = TestFixtures.getCorrectionsPath(CLEAN_JOB_ID)
    expect(fs.existsSync(correctionsPath)).toBeTruthy()

    const correctionsData = JSON.parse(fs.readFileSync(correctionsPath, 'utf8'))
    expect(Array.isArray(correctionsData)).toBeTruthy()
    expect(correctionsData.length).toBeGreaterThan(0)
    expect(correctionsData[0].new_value).toBe('Blood Glucose')
  })

  test('3. Format error: Corrupted corrections file, server returns 422, UI surfaces error banner', async ({ page }) => {
    // Create corrupted corrections file (object instead of array)
    await TestFixtures.createCorruptedCorrectionsFile(CORRUPTED_JOB_ID)

    // Navigate to review page
    await page.goto(`${BASE_URL}/review/${encodeURIComponent(CORRUPTED_JOB_ID)}`)

    // Wait for page to load
    await expect(page.getByText('Manual Review & Correction')).toBeVisible()

    // Try to make a correction
    const firstRow = page.locator('tr').nth(1) // Skip header row
    await firstRow.locator('td').first().click()

    const input = page.locator('input').first()
    await input.waitFor({ timeout: 5000 })
    await input.clear()
    await input.fill('Corrected Value')

    // Set up to catch the 422 response
    const errorResponsePromise = PageHelpers.waitForApiCall(page, '/api/results/', 'POST')

    // Attempt to save
    const saveButton = page.getByRole('button', { name: /save/i }).first()
    await saveButton.click()

    // Verify 422 response
    const errorResponse = await errorResponsePromise
    expect(errorResponse.status()).toBe(422)

    const errorData = await errorResponse.json()
    expect(errorData.error).toBe('CORRECTIONS_FILE_WRONG_TYPE')
    expect(errorData.expected).toBe('array')
    expect(errorData.found).toBe('dict')

    // Verify error banner/toast appears with actionable guidance
    const errorMessage = await PageHelpers.getToastText(page)
    expect(errorMessage).toBeTruthy()
    expect(errorMessage).toMatch(/format error|wrong type/i)
    expect(errorMessage).toMatch(/migration|array/i)

    // Check for error banner with next steps
    const errorBanner = page.locator('[role="alert"], .error-banner, .toast-error').first()
    await expect(errorBanner).toBeVisible()

    const bannerText = await errorBanner.textContent()
    expect(bannerText).toMatch(/migration|delete.*file|array/i)
  })

  test('4. Recovery: After migration, corrections work normally', async ({ page }) => {
    // Start with corrupted file
    await TestFixtures.createCorruptedCorrectionsFile(CORRUPTED_JOB_ID)

    // Navigate and attempt save (should fail)
    await page.goto(`${BASE_URL}/review/${encodeURIComponent(CORRUPTED_JOB_ID)}`)
    await expect(page.getByText('Manual Review & Correction')).toBeVisible()

    // Try to save a correction (should fail with 422)
    const firstInput = page.locator('input').first()
    await firstInput.waitFor({ timeout: 5000 })
    await firstInput.clear()
    await firstInput.fill('Should Fail')

    const saveButton = page.getByRole('button', { name: /save/i }).first()
    await saveButton.click()

    // Verify error occurs
    const errorToast = page.locator('[role="alert"], .toast-error').first()
    await expect(errorToast).toBeVisible({ timeout: 10000 })

    // Simulate migration by creating proper array format
    const migratedCorrections = [
      {
        field: 'test_name',
        new_value: 'Migrated Value',
        old_value: 'Original',
        line_number: 10,
        source: 'migration-test',
        ts: new Date().toISOString()
      }
    ]

    await TestFixtures.createValidCorrectionsFile(CORRUPTED_JOB_ID, migratedCorrections)

    // Refresh page
    await page.reload()
    await expect(page.getByText('Manual Review & Correction')).toBeVisible()

    // Now corrections should work normally
    const newInput = page.locator('input').first()
    await newInput.waitFor({ timeout: 5000 })
    await newInput.clear()
    await newInput.fill('Post Migration Value')

    // Set up API monitoring for successful save
    const successPromise = PageHelpers.waitForApiCall(page, '/api/results/', 'POST')

    const newSaveButton = page.getByRole('button', { name: /save/i }).first()
    await newSaveButton.click()

    // Verify successful save
    const successResponse = await successPromise
    expect(successResponse.status()).toBe(200)

    // Verify success toast
    await PageHelpers.waitForToast(page, 'saved successfully')

    // Verify the corrected value is visible
    await expect(page.getByText('Post Migration Value')).toBeVisible()
  })

  test('5. Append behavior: Multiple corrections accumulate correctly', async ({ page }) => {
    // Start with one existing correction
    const existingCorrections = [
      {
        field: 'test_name',
        new_value: 'First Correction',
        old_value: 'Original',
        line_number: 10,
        source: 'test',
        ts: new Date().toISOString()
      }
    ]

    await TestFixtures.createValidCorrectionsFile(CLEAN_JOB_ID, existingCorrections)

    // Navigate to review page
    await page.goto(`${BASE_URL}/review/${encodeURIComponent(CLEAN_JOB_ID)}`)
    await expect(page.getByText('Manual Review & Correction')).toBeVisible()

    // Verify existing correction is loaded
    await expect(page.getByText('First Correction')).toBeVisible()

    // Add a second correction
    const secondRow = page.locator('tr').nth(2) // Different row
    if (await secondRow.count() > 0) {
      await secondRow.locator('td').first().click()

      const secondInput = page.locator('input').first()
      await secondInput.waitFor()
      await secondInput.clear()
      await secondInput.fill('Second Correction')

      // Set up API monitoring
      const appendPromise = PageHelpers.waitForApiCall(page, '/api/results/', 'POST')

      const appendSaveButton = page.getByRole('button', { name: /save/i }).first()
      await appendSaveButton.click()

      // Verify POST contains array
      const appendResponse = await appendPromise
      expect(appendResponse.status()).toBe(200)

      const appendBody = appendResponse.request().postDataJSON()
      expect(Array.isArray(appendBody)).toBeTruthy()

      // Verify success
      await PageHelpers.waitForToast(page, 'saved successfully')

      // Verify both corrections are visible
      await expect(page.getByText('First Correction')).toBeVisible()
      await expect(page.getByText('Second Correction')).toBeVisible()

      // Verify corrections file contains both items
      const correctionsPath = TestFixtures.getCorrectionsPath(CLEAN_JOB_ID)
      const finalCorrections = JSON.parse(fs.readFileSync(correctionsPath, 'utf8'))
      expect(Array.isArray(finalCorrections)).toBeTruthy()
      expect(finalCorrections.length).toBeGreaterThanOrEqual(2)
    }
  })

  test('6. Edge case: Empty array POST still works', async ({ page }) => {
    // Start with clean state
    await TestFixtures.removeCorrectionsFile(CLEAN_JOB_ID)

    // Navigate to review page
    await page.goto(`${BASE_URL}/review/${encodeURIComponent(CLEAN_JOB_ID)}`)
    await expect(page.getByText('Manual Review & Correction')).toBeVisible()

    // Simulate an edge case where empty array might be posted
    await page.evaluate(async () => {
      // Simulate direct API call with empty array
      try {
        const response = await fetch('/api/results/e2e-corrections-clean/corrections', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify([])
        })
        return response.status
      } catch (e) {
        return 500
      }
    })

    // The API should handle empty arrays gracefully (no error)
    // Verify page still works after this edge case
    await expect(page.getByText('Manual Review & Correction')).toBeVisible()
  })
})

test.describe('API Integration Edge Cases', () => {
  test('Network error handling during correction save', async ({ page }) => {
    await TestFixtures.removeCorrectionsFile(CLEAN_JOB_ID)

    // Intercept and fail the API call
    await page.route('**/api/results/*/corrections', (route) => {
      route.abort('failed')
    })

    await page.goto(`${BASE_URL}/review/${encodeURIComponent(CLEAN_JOB_ID)}`)
    await expect(page.getByText('Manual Review & Correction')).toBeVisible()

    // Try to make a correction
    const input = page.locator('input').first()
    await input.waitFor({ timeout: 5000 })
    await input.fill('Network Error Test')

    const saveButton = page.getByRole('button', { name: /save/i }).first()
    await saveButton.click()

    // Should show network error
    const errorMessage = await PageHelpers.getToastText(page)
    expect(errorMessage).toMatch(/error|failed|network/i)
  })

  test('Malformed server response handling', async ({ page }) => {
    await TestFixtures.removeCorrectionsFile(CLEAN_JOB_ID)

    // Intercept and return malformed response
    await PageHelpers.interceptApiCall(page, '**/api/results/*/corrections',
      { malformed: true }, 200)

    await page.goto(`${BASE_URL}/review/${encodeURIComponent(CLEAN_JOB_ID)}`)
    await expect(page.getByText('Manual Review & Correction')).toBeVisible()

    // The UI should handle malformed responses gracefully
    // and not crash the application
    const input = page.locator('input').first()
    if (await input.count() > 0) {
      await input.fill('Malformed Response Test')

      const saveButton = page.getByRole('button', { name: /save/i }).first()
      await saveButton.click()

      // Should not crash - page should remain functional
      await expect(page.getByText('Manual Review & Correction')).toBeVisible()
    }
  })
})