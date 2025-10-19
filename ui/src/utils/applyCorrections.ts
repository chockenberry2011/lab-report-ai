import { normalizeResultId } from '@/lib/normalizeIds'

export type CorrectionItem = {
  // Preferred op/path/value format
  op?: string;
  path?: string;
  value?: unknown;

  // Fallback field/new_value format
  field?: string;
  new_value?: unknown;
  old_value?: unknown;

  // Metadata
  note?: string;
  source?: string;
  ts?: string;
  location?: { page?: number; start?: number; end?: number };
};

/**
 * Apply a correction to an object, preferring op/path/value format
 * Falls back to field/new_value if op/path/value not available
 */
export function applyCorrectionToObject(data: any, correction: CorrectionItem): any {
  if (!data || typeof data !== 'object') {
    return data;
  }

  // Prefer op/path/value format
  if (correction.path && correction.op) {
    return applyPathBasedCorrection(data, correction);
  }

  // Fallback to field/new_value format
  if (correction.field !== undefined) {
    return applyFieldBasedCorrection(data, correction);
  }

  // No valid correction format found
  console.warn('Invalid correction format:', correction);
  return data;
}

/**
 * Apply corrections using op/path/value format
 */
function applyPathBasedCorrection(data: any, correction: CorrectionItem): any {
  const { op = 'replace', path, value } = correction;

  if (!path) return data;

  // Handle different operation types
  switch (op) {
    case 'replace':
    case 'set':
      return setValueAtPath(data, path, value);

    case 'unset':
    case 'remove':
      return unsetValueAtPath(data, path);

    case 'append':
      return appendValueAtPath(data, path, value);

    default:
      console.warn('Unknown operation:', op);
      return setValueAtPath(data, path, value);
  }
}

/**
 * Apply corrections using field/new_value format (legacy)
 */
function applyFieldBasedCorrection(data: any, correction: CorrectionItem): any {
  const { field, new_value } = correction;

  if (!field) return data;

  // Convert field to path format and apply
  return setValueAtPath(data, field, new_value);
}

/**
 * Set a value at a path in an object
 * Supports both dot notation (patient.name) and bracket notation (panels[0].tests[1].value)
 */
function setValueAtPath(obj: any, path: string, value: unknown): any {
  const result = JSON.parse(JSON.stringify(obj)); // Deep clone
  const pathSegments = parsePath(path);

  let current = result;

  // Navigate to the parent of the target property
  for (let i = 0; i < pathSegments.length - 1; i++) {
    const segment = pathSegments[i];

    if (!(segment in current)) {
      // Create new object or array as needed
      const nextSegment = pathSegments[i + 1];
      current[segment] = isArrayIndex(nextSegment) ? [] : {};
    }

    current = current[segment];
  }

  // Set the final value
  const finalSegment = pathSegments[pathSegments.length - 1];
  current[finalSegment] = value;

  return result;
}

/**
 * Remove a value at a path in an object
 */
function unsetValueAtPath(obj: any, path: string): any {
  const result = JSON.parse(JSON.stringify(obj)); // Deep clone
  const pathSegments = parsePath(path);

  let current = result;

  // Navigate to the parent of the target property
  for (let i = 0; i < pathSegments.length - 1; i++) {
    const segment = pathSegments[i];
    if (!(segment in current)) {
      return result; // Path doesn't exist, nothing to unset
    }
    current = current[segment];
  }

  // Remove the final property
  const finalSegment = pathSegments[pathSegments.length - 1];
  if (Array.isArray(current)) {
    current.splice(parseInt(finalSegment), 1);
  } else {
    delete current[finalSegment];
  }

  return result;
}

/**
 * Append a value to an array at a path
 */
function appendValueAtPath(obj: any, path: string, value: unknown): any {
  const result = JSON.parse(JSON.stringify(obj)); // Deep clone
  const pathSegments = parsePath(path);

  let current = result;

  // Navigate to the target array
  for (const segment of pathSegments) {
    if (!(segment in current)) {
      current[segment] = [];
    }
    current = current[segment];
  }

  // Append to array
  if (Array.isArray(current)) {
    current.push(value);
  } else {
    console.warn('Cannot append to non-array at path:', path);
  }

  return result;
}

/**
 * Parse a path string into segments
 * Handles: "patient.name", "panels[0].tests[1].value", "panels.0.tests.1.value"
 */
function parsePath(path: string): string[] {
  return path
    .replace(/\[(\d+)\]/g, '.$1') // Convert [0] to .0
    .split('.')
    .filter(segment => segment !== '');
}

/**
 * Check if a string represents an array index
 */
function isArrayIndex(segment: string): boolean {
  return /^\d+$/.test(segment);
}

/**
 * Apply multiple corrections to an object
 */
export function applyCorrections(data: any, corrections: CorrectionItem[]): any {
  if (!corrections || corrections.length === 0) {
    return data;
  }

  return corrections.reduce((current, correction) => {
    return applyCorrectionToObject(current, correction);
  }, data);
}

/**
 * Normalize result ID for consistent store keys
 */
export function normalizeStoreKey(rawId: string): string {
  return normalizeResultId(rawId);
}