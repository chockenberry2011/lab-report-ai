/**
 * Test fixtures and utilities for corrections end-to-end tests
 */

import * as fs from 'fs'
import * as path from 'path'

export interface TestResult {
  job_id: string
  status: string
  lab_panels: Array<{
    id: string
    name: string
    test_rows: Array<{
      id: string
      line_number: number
      text: string
      test_name: string
      result_value: string
      units: string
      reference_range?: string
      flag?: string
      confidence?: number
    }>
  }>
  document_info?: any
  processing_metadata?: any
}

export interface Correction {
  field: string
  new_value: any
  old_value?: any
  line_number?: number
  source?: string
  ts?: string
  note?: string
}

export class TestFixtures {
  private static readonly DATA_ROOT = process.env.DATA_ROOT || '/data'
  private static readonly RESULTS_DIR = path.join(this.DATA_ROOT, 'results')
  private static readonly OUTBOX_DIR = path.join(this.DATA_ROOT, 'outbox')

  /**
   * Get the path to a corrections file for a given job ID
   */
  static getCorrectionsPath(jobId: string): string {
    const normalizedId = this.normalizeJobId(jobId)
    return path.join(this.RESULTS_DIR, normalizedId, 'corrections.json')
  }

  /**
   * Get the path to a result file for a given job ID
   */
  static getOutboxPath(jobId: string): string {
    return path.join(this.OUTBOX_DIR, `${jobId}.json`)
  }

  /**
   * Normalize job ID by stripping debug suffixes
   */
  private static normalizeJobId(jobId: string): string {
    return jobId.split('.')[0]
  }

  /**
   * Ensure a directory exists, creating it if necessary
   */
  static async ensureDirectoryExists(dirPath: string): Promise<void> {
    if (!fs.existsSync(dirPath)) {
      fs.mkdirSync(dirPath, { recursive: true })
    }
  }

  /**
   * Create a test result file in the outbox
   */
  static async createTestResult(jobId: string, customData?: Partial<TestResult>): Promise<void> {
    const normalizedId = this.normalizeJobId(jobId)
    const outboxPath = this.getOutboxPath(jobId)

    await this.ensureDirectoryExists(path.dirname(outboxPath))

    const defaultResult: TestResult = {
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
              confidence: 0.90
            },
            {
              id: 'test-3',
              line_number: 12,
              text: 'Potassium 4.2 mEq/L 3.5-5.1',
              test_name: 'Potassium',
              result_value: '4.2',
              units: 'mEq/L',
              reference_range: '3.5-5.1',
              confidence: 0.88
            }
          ]
        }
      ],
      document_info: {
        patient: {
          first_name: 'Test',
          last_name: 'Patient',
          mrn: 'E2E-12345'
        },
        performing_lab: {
          name: 'E2E Test Lab'
        }
      },
      processing_metadata: {
        timestamp: new Date().toISOString(),
        stage: '03_compose',
        version: '1.0.0'
      }
    }

    const result = { ...defaultResult, ...customData }

    fs.writeFileSync(outboxPath, JSON.stringify(result, null, 2))
    console.log(`✅ Created test result: ${outboxPath}`)
  }

  /**
   * Remove a corrections file
   */
  static async removeCorrectionsFile(jobId: string): Promise<void> {
    const correctionsPath = this.getCorrectionsPath(jobId)
    if (fs.existsSync(correctionsPath)) {
      fs.unlinkSync(correctionsPath)
      console.log(`🗑️  Removed corrections file: ${correctionsPath}`)
    }
  }

  /**
   * Create a corrupted corrections file (object instead of array)
   */
  static async createCorruptedCorrectionsFile(jobId: string): Promise<void> {
    const correctionsPath = this.getCorrectionsPath(jobId)

    await this.ensureDirectoryExists(path.dirname(correctionsPath))

    // Create object format (invalid - should be array)
    const corruptedData = {
      field: 'test_name',
      new_value: 'Corrupted Format',
      old_value: 'Original',
      line_number: 10,
      source: 'corrupted-test',
      ts: new Date().toISOString()
    }

    fs.writeFileSync(correctionsPath, JSON.stringify(corruptedData, null, 2))
    console.log(`⚠️  Created corrupted corrections file: ${correctionsPath}`)
  }

  /**
   * Create a valid corrections file with array format
   */
  static async createValidCorrectionsFile(jobId: string, corrections: Correction[]): Promise<void> {
    const correctionsPath = this.getCorrectionsPath(jobId)

    await this.ensureDirectoryExists(path.dirname(correctionsPath))

    fs.writeFileSync(correctionsPath, JSON.stringify(corrections, null, 2))
    console.log(`✅ Created valid corrections file: ${correctionsPath} (${corrections.length} items)`)
  }

  /**
   * Read corrections file contents
   */
  static async readCorrectionsFile(jobId: string): Promise<any | null> {
    const correctionsPath = this.getCorrectionsPath(jobId)

    if (!fs.existsSync(correctionsPath)) {
      return null
    }

    try {
      const content = fs.readFileSync(correctionsPath, 'utf8')
      return JSON.parse(content)
    } catch (error) {
      console.error(`Error reading corrections file: ${error}`)
      return null
    }
  }

  /**
   * Cleanup test data for given job IDs
   */
  static async cleanup(jobIds: string[]): Promise<void> {
    console.log(`🧹 Starting cleanup for ${jobIds.length} job IDs...`)

    for (const jobId of jobIds) {
      try {
        // Remove test result
        const outboxPath = this.getOutboxPath(jobId)
        if (fs.existsSync(outboxPath)) {
          fs.unlinkSync(outboxPath)
          console.log(`🗑️  Removed result: ${outboxPath}`)
        }

        // Remove corrections file
        await this.removeCorrectionsFile(jobId)

        // Remove result directory if empty
        const normalizedId = this.normalizeJobId(jobId)
        const resultDir = path.join(this.RESULTS_DIR, normalizedId)
        if (fs.existsSync(resultDir)) {
          try {
            const contents = fs.readdirSync(resultDir)
            if (contents.length === 0) {
              fs.rmdirSync(resultDir)
              console.log(`🗑️  Removed empty directory: ${resultDir}`)
            }
          } catch (e) {
            // Directory not empty or other error, that's fine
          }
        }
      } catch (error) {
        console.warn(`Warning during cleanup of ${jobId}: ${error}`)
      }
    }

    console.log('✅ Cleanup completed')
  }

  /**
   * Create sample corrections data
   */
  static createSampleCorrections(count = 3): Correction[] {
    const fields = ['test_name', 'result_value', 'units', 'reference_range', 'flag']
    const corrections: Correction[] = []

    for (let i = 0; i < count; i++) {
      corrections.push({
        field: fields[i % fields.length],
        new_value: `Corrected Value ${i + 1}`,
        old_value: `Original Value ${i + 1}`,
        line_number: 10 + i,
        source: 'e2e-test',
        ts: new Date().toISOString(),
        note: `E2E test correction ${i + 1}`
      })
    }

    return corrections
  }

  /**
   * Verify corrections file format
   */
  static async verifyCorrectionsFormat(jobId: string): Promise<{ isValid: boolean; isArray: boolean; count: number; error?: string }> {
    try {
      const data = await this.readCorrectionsFile(jobId)

      if (data === null) {
        return { isValid: true, isArray: false, count: 0 } // No file is valid (empty state)
      }

      const isArray = Array.isArray(data)
      const count = isArray ? data.length : 1

      return {
        isValid: isArray,
        isArray,
        count,
        error: isArray ? undefined : 'File contains object instead of array'
      }
    } catch (error) {
      return {
        isValid: false,
        isArray: false,
        count: 0,
        error: `Failed to read corrections file: ${error}`
      }
    }
  }

  /**
   * Wait for file system changes (useful for async operations)
   */
  static async waitForFile(filePath: string, timeoutMs = 5000): Promise<boolean> {
    const startTime = Date.now()

    while (Date.now() - startTime < timeoutMs) {
      if (fs.existsSync(filePath)) {
        return true
      }
      await new Promise(resolve => setTimeout(resolve, 100))
    }

    return false
  }

  /**
   * Get test environment info
   */
  static getEnvironmentInfo() {
    return {
      dataRoot: this.DATA_ROOT,
      resultsDir: this.RESULTS_DIR,
      outboxDir: this.OUTBOX_DIR,
      nodeEnv: process.env.NODE_ENV,
      apiBase: process.env.API_BASE_URL || 'http://localhost:8000',
      uiBase: process.env.UI_BASE_URL || 'http://localhost:5173'
    }
  }
}