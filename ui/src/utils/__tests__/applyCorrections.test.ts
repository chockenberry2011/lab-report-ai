import { applyCorrectionToObject, applyCorrections, CorrectionItem } from '@/utils/applyCorrections'

describe('applyCorrections', () => {
  const sampleData = {
    patient: {
      first_name: "John",
      last_name: "Doe",
      age: 30
    },
    panels: [
      {
        name: "CBC",
        tests: [
          { name: "WBC", value: "5.0", units: "K/uL" },
          { name: "RBC", value: "4.5", units: "M/uL" }
        ]
      }
    ]
  }

  describe('op/path/value format (preferred)', () => {
    it('should apply replace operation', () => {
      const correction: CorrectionItem = {
        op: "replace",
        path: "patient.first_name",
        value: "Jane"
      }

      const result = applyCorrectionToObject(sampleData, correction)
      expect(result.patient.first_name).toBe("Jane")
      expect(result.patient.last_name).toBe("Doe") // unchanged
    })

    it('should apply set operation to nested arrays', () => {
      const correction: CorrectionItem = {
        op: "set",
        path: "panels[0].tests[0].value",
        value: "6.0"
      }

      const result = applyCorrectionToObject(sampleData, correction)
      expect(result.panels[0].tests[0].value).toBe("6.0")
      expect(result.panels[0].tests[0].name).toBe("WBC") // unchanged
    })

    it('should create new nested objects when path does not exist', () => {
      const correction: CorrectionItem = {
        op: "set",
        path: "patient.address.city",
        value: "New York"
      }

      const result = applyCorrectionToObject(sampleData, correction)
      expect(result.patient.address.city).toBe("New York")
    })

    it('should unset values', () => {
      const correction: CorrectionItem = {
        op: "unset",
        path: "patient.age"
      }

      const result = applyCorrectionToObject(sampleData, correction)
      expect(result.patient.age).toBeUndefined()
      expect(result.patient.first_name).toBe("John") // unchanged
    })

    it('should append to arrays', () => {
      const correction: CorrectionItem = {
        op: "append",
        path: "panels[0].tests",
        value: { name: "PLT", value: "300", units: "K/uL" }
      }

      const result = applyCorrectionToObject(sampleData, correction)
      expect(result.panels[0].tests).toHaveLength(3)
      expect(result.panels[0].tests[2]).toEqual({ name: "PLT", value: "300", units: "K/uL" })
    })
  })

  describe('field/new_value format (fallback)', () => {
    it('should apply field-based corrections', () => {
      const correction: CorrectionItem = {
        field: "patient.first_name",
        new_value: "Jane",
        old_value: "John"
      }

      const result = applyCorrectionToObject(sampleData, correction)
      expect(result.patient.first_name).toBe("Jane")
    })

    it('should handle array access in field format', () => {
      const correction: CorrectionItem = {
        field: "panels.0.tests.1.value",
        new_value: "4.8"
      }

      const result = applyCorrectionToObject(sampleData, correction)
      expect(result.panels[0].tests[1].value).toBe("4.8")
    })
  })

  describe('preference order', () => {
    it('should prefer op/path/value over field/new_value when both present', () => {
      const correction: CorrectionItem = {
        // Preferred format
        op: "replace",
        path: "patient.first_name",
        value: "Alice",
        // Fallback format (should be ignored)
        field: "patient.first_name",
        new_value: "Bob"
      }

      const result = applyCorrectionToObject(sampleData, correction)
      expect(result.patient.first_name).toBe("Alice") // Uses op/path/value
    })
  })

  describe('multiple corrections', () => {
    it('should apply multiple corrections in sequence', () => {
      const corrections: CorrectionItem[] = [
        {
          op: "replace",
          path: "patient.first_name",
          value: "Jane"
        },
        {
          field: "patient.last_name",
          new_value: "Smith"
        },
        {
          op: "set",
          path: "panels[0].tests[0].value",
          value: "5.5"
        }
      ]

      const result = applyCorrections(sampleData, corrections)
      expect(result.patient.first_name).toBe("Jane")
      expect(result.patient.last_name).toBe("Smith")
      expect(result.panels[0].tests[0].value).toBe("5.5")
    })
  })

  describe('error handling', () => {
    it('should handle invalid correction formats gracefully', () => {
      const correction: CorrectionItem = {
        note: "Invalid correction with no path or field"
      }

      const result = applyCorrectionToObject(sampleData, correction)
      expect(result).toEqual(sampleData) // unchanged
    })

    it('should handle null/undefined data', () => {
      const correction: CorrectionItem = {
        op: "set",
        path: "test",
        value: "value"
      }

      expect(applyCorrectionToObject(null, correction)).toBe(null)
      expect(applyCorrectionToObject(undefined, correction)).toBe(undefined)
    })
  })

  describe('path parsing', () => {
    it('should handle various path formats', () => {
      const testCases = [
        { path: "patient.name", expected: "Jane" },
        { path: "panels[0].name", expected: "Complete Blood Count" },
        { path: "panels.0.name", expected: "Complete Blood Count" }, // alternative syntax
      ]

      testCases.forEach(({ path, expected }) => {
        const correction: CorrectionItem = {
          op: "set",
          path,
          value: expected
        }
        const result = applyCorrectionToObject(sampleData, correction)

        // Navigate to the expected location based on path
        if (path === "patient.name") {
          expect(result.patient.name).toBe(expected)
        } else if (path.includes("panels")) {
          expect(result.panels[0].name).toBe(expected)
        }
      })
    })
  })
})