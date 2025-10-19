/**
 * Page helper utilities for Playwright tests
 * Provides reusable functions for interacting with the corrections UI
 */

import { Page, expect, Locator } from '@playwright/test'

export interface ApiCallOptions {
  method?: string
  timeout?: number
  expectedStatus?: number
}

export interface ToastOptions {
  timeout?: number
  type?: 'success' | 'error' | 'warning' | 'info'
}

export class PageHelpers {
  constructor(private page: Page) {}

  /**
   * Wait for an API call matching the given pattern
   */
  async waitForApiCall(urlPattern: string, options: ApiCallOptions = {}): Promise<any> {
    const { method = 'GET', timeout = 10000, expectedStatus } = options

    const responsePromise = this.page.waitForResponse((response) => {
      const matchesUrl = response.url().includes(urlPattern)
      const matchesMethod = response.request().method() === method
      const matchesStatus = expectedStatus ? response.status() === expectedStatus : true

      return matchesUrl && matchesMethod && matchesStatus
    }, { timeout })

    return responsePromise
  }

  /**
   * Intercept and mock an API call
   */
  async interceptApiCall(urlPattern: string, mockResponse: any, status = 200): Promise<void> {
    await this.page.route(urlPattern, (route) => {
      route.fulfill({
        status,
        contentType: 'application/json',
        body: JSON.stringify(mockResponse)
      })
    })
  }

  /**
   * Get toast/notification text content
   */
  async getToastText(options: ToastOptions = {}): Promise<string | null> {
    const { timeout = 5000 } = options

    try {
      // Try multiple selectors for different toast libraries
      const toastSelectors = [
        '[data-testid="toast"]',
        '.Toastify__toast',
        '[role="alert"]',
        '.toast',
        '.notification',
        '.alert'
      ]

      for (const selector of toastSelectors) {
        const toast = this.page.locator(selector).first()
        try {
          await toast.waitFor({ timeout: 1000 })
          const text = await toast.textContent()
          if (text && text.trim()) {
            return text.trim()
          }
        } catch (e) {
          // Try next selector
          continue
        }
      }

      return null
    } catch (e) {
      console.log('No toast found:', e)
      return null
    }
  }

  /**
   * Wait for a specific toast message to appear
   */
  async waitForToast(expectedText: string, options: ToastOptions = {}): Promise<void> {
    const { timeout = 10000 } = options

    const toast = this.page.locator(`text="${expectedText}"`).or(
      this.page.locator(`[role="alert"]:has-text("${expectedText}")`)
    ).or(
      this.page.locator(`.toast:has-text("${expectedText}")`)
    )

    await expect(toast).toBeVisible({ timeout })
  }

  /**
   * Navigate to review page and wait for it to load
   */
  async navigateToReview(jobId: string, baseUrl = 'http://localhost:5173'): Promise<void> {
    const url = `${baseUrl}/review/${encodeURIComponent(jobId)}`
    await this.page.goto(url)

    // Wait for key elements to ensure page is loaded
    await expect(this.page.getByText('Manual Review & Correction')).toBeVisible({ timeout: 15000 })
  }

  /**
   * Find and interact with a test row in the corrections table
   */
  async findTestRow(testName: string): Promise<Locator> {
    const row = this.page.locator(`tr:has-text("${testName}")`).first()
    await expect(row).toBeVisible({ timeout: 5000 })
    return row
  }

  /**
   * Edit a field in a test row
   */
  async editTestField(testName: string, fieldIndex = 0, newValue: string): Promise<void> {
    const row = await this.findTestRow(testName)
    const cell = row.locator('td').nth(fieldIndex)

    // Try clicking to activate edit mode
    await cell.click()

    // Try double-clicking if single click doesn't work
    let input = this.page.locator('input').first()
    if (await input.count() === 0) {
      await cell.dblclick()
      input = this.page.locator('input').first()
    }

    // Wait for input to appear and be editable
    await input.waitFor({ timeout: 5000 })
    await input.clear()
    await input.fill(newValue)
  }

  /**
   * Save corrections using the save button
   */
  async saveCorrections(): Promise<void> {
    const saveButton = this.page.getByRole('button', { name: /save/i }).first()
    await expect(saveButton).toBeVisible()
    await expect(saveButton).toBeEnabled()
    await saveButton.click()
  }

  /**
   * Verify a correction is visible in the UI
   */
  async verifyCorrection(expectedValue: string, timeout = 10000): Promise<void> {
    await expect(this.page.getByText(expectedValue)).toBeVisible({ timeout })
  }

  /**
   * Get all visible corrections from the UI
   */
  async getVisibleCorrections(): Promise<string[]> {
    // This depends on how corrections are displayed in the UI
    // Adjust selectors based on actual implementation
    const correctionElements = this.page.locator('.correction-item, .corrected-value, .highlight')
    const count = await correctionElements.count()

    const corrections: string[] = []
    for (let i = 0; i < count; i++) {
      const text = await correctionElements.nth(i).textContent()
      if (text && text.trim()) {
        corrections.push(text.trim())
      }
    }

    return corrections
  }

  /**
   * Wait for page to be fully loaded and interactive
   */
  async waitForPageLoad(): Promise<void> {
    // Wait for network to be idle
    await this.page.waitForLoadState('networkidle')

    // Wait for key UI elements
    await expect(this.page.getByText('Manual Review & Correction')).toBeVisible()

    // Wait a bit more to ensure JavaScript has finished executing
    await this.page.waitForTimeout(1000)
  }

  /**
   * Check if error banner is displayed
   */
  async checkForErrorBanner(expectedText?: string): Promise<boolean> {
    const errorSelectors = [
      '[role="alert"]',
      '.error-banner',
      '.alert-error',
      '.toast-error',
      '.notification-error'
    ]

    for (const selector of errorSelectors) {
      try {
        const element = this.page.locator(selector).first()
        await element.waitFor({ timeout: 2000 })

        if (expectedText) {
          const text = await element.textContent()
          if (text && text.includes(expectedText)) {
            return true
          }
        } else {
          return true // Found error banner
        }
      } catch (e) {
        // Try next selector
        continue
      }
    }

    return false
  }

  /**
   * Get current URL path
   */
  async getCurrentPath(): Promise<string> {
    return new URL(this.page.url()).pathname
  }

  /**
   * Verify API request body format
   */
  async verifyApiRequestBody(response: any, expectedFormat: 'array' | 'object'): Promise<void> {
    const request = response.request()
    const body = request.postDataJSON()

    if (expectedFormat === 'array') {
      expect(Array.isArray(body)).toBeTruthy()
    } else {
      expect(typeof body).toBe('object')
      expect(Array.isArray(body)).toBeFalsy()
    }
  }

  /**
   * Fill a form field by label
   */
  async fillFieldByLabel(label: string, value: string): Promise<void> {
    const field = this.page.getByLabel(label).or(
      this.page.locator(`input[placeholder*="${label}"]`)
    ).or(
      this.page.locator(`text="${label}"`).locator('..').locator('input')
    )

    await field.waitFor({ timeout: 5000 })
    await field.clear()
    await field.fill(value)
  }

  /**
   * Wait for element to be stable (not animating)
   */
  async waitForStable(locator: Locator, timeout = 5000): Promise<void> {
    await locator.waitFor({ timeout })

    // Wait for element to stop moving/changing
    let previousBoundingBox: any = null
    const maxAttempts = 10

    for (let i = 0; i < maxAttempts; i++) {
      const currentBoundingBox = await locator.boundingBox()

      if (previousBoundingBox &&
          JSON.stringify(currentBoundingBox) === JSON.stringify(previousBoundingBox)) {
        return // Element is stable
      }

      previousBoundingBox = currentBoundingBox
      await this.page.waitForTimeout(200)
    }
  }

  /**
   * Take screenshot with test context
   */
  async takeScreenshot(name: string): Promise<void> {
    await this.page.screenshot({
      path: `test-results/screenshots/${name}-${Date.now()}.png`,
      fullPage: true
    })
  }

  /**
   * Log current page state for debugging
   */
  async logPageState(): Promise<void> {
    console.log('=== Page State Debug ===')
    console.log('URL:', this.page.url())
    console.log('Title:', await this.page.title())

    // Log any error messages
    const errors = await this.page.locator('[role="alert"], .error, .alert-error').all()
    if (errors.length > 0) {
      console.log('Errors found:')
      for (const error of errors) {
        const text = await error.textContent()
        console.log('  -', text?.trim())
      }
    }

    // Log any toast messages
    const toasts = await this.page.locator('.toast, .notification').all()
    if (toasts.length > 0) {
      console.log('Toasts found:')
      for (const toast of toasts) {
        const text = await toast.textContent()
        console.log('  -', text?.trim())
      }
    }

    console.log('=== End Page State ===')
  }
}

/**
 * Factory function to create PageHelpers instance
 */
export function createPageHelpers(page: Page): PageHelpers {
  return new PageHelpers(page)
}