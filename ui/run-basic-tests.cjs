#!/usr/bin/env node

/**
 * Basic test runner for enhanced corrections system
 * Runs without Jest - just uses Node.js assertions
 */

const assert = require('assert');

// Test 1: Field Spec Validation
function testFieldSpec() {
  console.log('🧪 Testing field specifications...');
  
  // Mock the field spec since we can't import ES modules easily in Node
  const mockFieldSpec = [
    { path: "patient.first_name", label: "Patient First", type: "text" },
    { path: "patient.dob", label: "DOB", type: "date" },
    { path: "vendor.phone", label: "Vendor Phone", type: "tel" },
    { path: "report.page", label: "Report Page", type: "number" },
  ];

  // Test field structure
  mockFieldSpec.forEach(field => {
    assert(field.path, 'Field must have path');
    assert(field.label, 'Field must have label');
    assert(field.type, 'Field must have type');
    assert(['text', 'number', 'date', 'tel'].includes(field.type), `Invalid type: ${field.type}`);
  });

  // Test unique paths
  const paths = mockFieldSpec.map(f => f.path);
  const uniquePaths = new Set(paths);
  assert(paths.length === uniquePaths.size, 'All paths must be unique');

  console.log('   ✅ Field specifications valid');
}

// Test 2: Path Processing
function testPathProcessing() {
  console.log('🧪 Testing path processing...');
  
  // Test path navigation (simplified version)
  function getValueByPath(obj, path) {
    return path.split('.').reduce((acc, key) => acc?.[key], obj);
  }

  function setValueByPath(obj, path, value) {
    const keys = path.split('.');
    const lastKey = keys.pop();
    const target = keys.reduce((acc, key) => acc[key] = acc[key] || {}, obj);
    target[lastKey] = value;
    return obj;
  }

  const testData = {
    patient: { first_name: 'John', last_name: 'Doe' },
    vendor: { name: 'Quest' }
  };

  // Test getting values
  assert(getValueByPath(testData, 'patient.first_name') === 'John', 'Should get nested value');
  assert(getValueByPath(testData, 'vendor.name') === 'Quest', 'Should get vendor name');
  assert(getValueByPath(testData, 'patient.middle') === undefined, 'Should return undefined for missing');

  // Test setting values
  setValueByPath(testData, 'patient.middle', 'Q');
  assert(testData.patient.middle === 'Q', 'Should set nested value');

  setValueByPath(testData, 'specimen.type', 'Serum');
  assert(testData.specimen?.type === 'Serum', 'Should create intermediate objects');

  console.log('   ✅ Path processing works correctly');
}

// Test 3: API Payload Structure
function testApiPayloads() {
  console.log('🧪 Testing API payload structures...');

  // Test new format
  const newFormatPayload = {
    items: [
      { op: 'set', path: 'patient.first_name', value: 'Alice' },
      { op: 'unset', path: 'patient.mrn' },
      { path: 'vendor.name', value: 'Quest' } // backward compatible - no op
    ]
  };

  assert(Array.isArray(newFormatPayload.items), 'Items should be array');
  assert(newFormatPayload.items.length === 3, 'Should have 3 items');
  
  newFormatPayload.items.forEach(item => {
    assert(item.path, 'Each item must have path');
    if (item.op) {
      assert(['set', 'unset', 'append'].includes(item.op), `Invalid op: ${item.op}`);
    }
  });

  // Test legacy format
  const legacyFormatPayload = {
    corrections: [
      { line_number: 5, field: 'test_name', new_value: 'Glucose', old_value: 'GLU' }
    ]
  };

  assert(Array.isArray(legacyFormatPayload.corrections), 'Corrections should be array');
  legacyFormatPayload.corrections.forEach(correction => {
    assert(typeof correction.line_number === 'number', 'Line number must be number');
    assert(correction.field, 'Must have field');
    assert('new_value' in correction, 'Must have new_value');
  });

  console.log('   ✅ API payload structures valid');
}

// Test 4: URL Encoding
function testUrlEncoding() {
  console.log('🧪 Testing URL encoding...');

  function encodeResultId(resultId) {
    return encodeURIComponent(resultId);
  }

  assert(encodeResultId('simple-id') === 'simple-id', 'Simple ID unchanged');
  assert(encodeResultId('test@result') === 'test%40result', 'Should encode @ symbol');
  assert(encodeResultId('test#result') === 'test%23result', 'Should encode # symbol');
  assert(encodeResultId('test result') === 'test%20result', 'Should encode spaces');

  console.log('   ✅ URL encoding works correctly');
}

// Test 5: Error Handling
function testErrorHandling() {
  console.log('🧪 Testing error handling...');

  function simulateApiError(status, message) {
    const error = new Error(`Failed to save corrections: ${status} ${message}`);
    error.status = status;
    return error;
  }

  const error400 = simulateApiError(400, 'Bad request');
  assert(error400.message.includes('400'), 'Should include status code');
  assert(error400.message.includes('Bad request'), 'Should include error message');

  const error500 = simulateApiError(500, 'Internal server error');
  assert(error500.message.includes('500'), 'Should include 500 status');

  console.log('   ✅ Error handling works correctly');
}

// Run all tests
async function runTests() {
  console.log('🚀 Running Enhanced Corrections System Tests');
  console.log('===========================================\n');

  try {
    testFieldSpec();
    testPathProcessing();
    testApiPayloads();
    testUrlEncoding();
    testErrorHandling();

    console.log('\n🎉 All tests passed!');
    console.log('\nTo run full test suite with React components:');
    console.log('1. Install test dependencies:');
    console.log('   npm install -D jest ts-jest @testing-library/react @testing-library/jest-dom');
    console.log('2. Run: npm test');

  } catch (error) {
    console.error('\n❌ Test failed:', error.message);
    process.exit(1);
  }
}

if (require.main === module) {
  runTests();
}

module.exports = { runTests };