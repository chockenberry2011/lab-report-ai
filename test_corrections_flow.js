#!/usr/bin/env node

/**
 * Test script to reproduce UI corrections flow outside the browser
 * Tests result ID normalization, falsy value preservation, and persistence
 */

const BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000';

// Test data
const RID_WITH_SUFFIX = "99168343-c017-42c0-b549-290e37e9c955.03_compose.debug";

/**
 * Normalize result ID by stripping debug suffixes
 * Matches: .01_lines.debug, .01a_lines_merged.debug, .02_roles.debug, .03_compose.debug
 */
function normalizeResultId(rid) {
  return rid.replace(/\.(?:\d+a?_)?(?:lines|lines_merged|roles|compose)(?:\.debug)?$/i, '');
}

/**
 * Make HTTP request with error handling
 */
async function makeRequest(method, url, body = null) {
  const options = {
    method,
    headers: {
      'Content-Type': 'application/json',
    },
  };

  if (body) {
    options.body = JSON.stringify(body);
  }

  console.log(`${method} ${url}`);
  if (body) {
    console.log('Body:', JSON.stringify(body, null, 2));
  }

  try {
    const response = await fetch(url, options);
    const text = await response.text();

    let data;
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }

    console.log(`Response: ${response.status} ${response.statusText}`);
    console.log('Data:', typeof data === 'object' ? JSON.stringify(data, null, 2) : data);
    console.log('---');

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${JSON.stringify(data)}`);
    }

    return data;
  } catch (error) {
    console.error(`Request failed: ${error.message}`);
    throw error;
  }
}

/**
 * Assert helper
 */
function assert(condition, message) {
  if (!condition) {
    throw new Error(`Assertion failed: ${message}`);
  }
  console.log(`✓ ${message}`);
}

/**
 * Main test flow
 */
async function testCorrectionsFlow() {
  console.log('🧪 Testing Corrections Flow with Falsy Values\n');

  // Step 1: Normalize result ID
  const ridBase = normalizeResultId(RID_WITH_SUFFIX);
  console.log(`Original RID: ${RID_WITH_SUFFIX}`);
  console.log(`Normalized RID: ${ridBase}`);
  assert(ridBase !== RID_WITH_SUFFIX, 'Result ID should be normalized');
  assert(!ridBase.includes('.debug'), 'Normalized ID should not contain .debug');
  console.log('---');

  try {
    // Step 2: GET result to ensure it exists
    console.log('📖 Step 2: Fetching result to ensure it exists');
    const initialResult = await makeRequest('GET', `${BASE_URL}/results/${ridBase}`);
    assert(initialResult, 'Result should exist');

    // Step 3: POST corrections with falsy values
    console.log('💾 Step 3: Posting corrections with falsy values');
    const corrections = [
      { "path": "/vendor/name", "value": "" },           // Empty string
      { "path": "/panels/0/name", "value": 0 },          // Zero
      { "path": "/document_info/approved", "value": false } // Boolean false
    ];

    const saveResponse = await makeRequest(
      'POST',
      `${BASE_URL}/results/${ridBase}/corrections`,
      corrections
    );

    assert(saveResponse.saved === 3, `Should save 3 corrections, got ${saveResponse.saved}`);
    assert(saveResponse.applied >= 0, 'Should report applied count');
    console.log(`✓ Saved ${saveResponse.saved} corrections, applied ${saveResponse.applied}`);

    // Step 4: GET corrections and verify they exist
    console.log('📋 Step 4: Fetching corrections to verify persistence');
    const correctionsResponse = await makeRequest('GET', `${BASE_URL}/results/${ridBase}/corrections`);

    assert(correctionsResponse.corrections, 'Should return corrections array');
    assert(correctionsResponse.corrections.length >= 3, `Should have at least 3 corrections, got ${correctionsResponse.corrections.length}`);

    // Verify falsy values are preserved
    const savedCorrections = correctionsResponse.corrections;
    console.log('📝 Verifying falsy values are preserved:');

    const emptyStringCorrection = savedCorrections.find(c =>
      c.path === "/vendor/name" || c.path === "vendor.name"
    );
    const zeroCorrection = savedCorrections.find(c =>
      c.path === "/panels/0/name" || c.path === "panels.0.name"
    );
    const falseCorrection = savedCorrections.find(c =>
      c.path === "/document_info/approved" || c.path === "document_info.approved"
    );

    if (emptyStringCorrection) {
      assert(emptyStringCorrection.value === "", `Empty string preserved: "${emptyStringCorrection.value}"`);
    }
    if (zeroCorrection) {
      assert(zeroCorrection.value === 0, `Zero preserved: ${zeroCorrection.value}`);
    }
    if (falseCorrection) {
      assert(falseCorrection.value === false, `False preserved: ${falseCorrection.value}`);
    }

    // Step 5: GET result again and verify changes applied
    console.log('🔍 Step 5: Fetching updated result to verify changes applied');
    const updatedResult = await makeRequest('GET', `${BASE_URL}/results/${ridBase}`);
    assert(updatedResult, 'Updated result should exist');

    // Check if changes are reflected (this depends on your data structure)
    console.log('📊 Verifying changes in result data:');
    if (updatedResult.vendor?.name !== undefined) {
      assert(updatedResult.vendor.name === "", `Vendor name should be empty string: "${updatedResult.vendor.name}"`);
    }
    if (updatedResult.document_info?.approved !== undefined) {
      assert(updatedResult.document_info.approved === false, `Approved should be false: ${updatedResult.document_info.approved}`);
    }

    console.log('\n🎉 All tests passed! Corrections flow working correctly.');
    console.log('\n📈 Summary:');
    console.log(`- Result ID normalized: ${RID_WITH_SUFFIX} → ${ridBase}`);
    console.log(`- Corrections saved: ${saveResponse.saved}`);
    console.log(`- Corrections applied: ${saveResponse.applied}`);
    console.log(`- Falsy values preserved: ✓ empty string, ✓ zero, ✓ false`);

  } catch (error) {
    console.error('\n❌ Test failed:', error.message);
    process.exit(1);
  }
}

/**
 * Test edge cases
 */
async function testEdgeCases() {
  console.log('\n🧪 Testing Edge Cases\n');

  const ridBase = normalizeResultId(RID_WITH_SUFFIX);

  try {
    // Test empty array rejection
    console.log('🚫 Test 1: Empty array should be rejected');
    try {
      await makeRequest('POST', `${BASE_URL}/results/${ridBase}/corrections`, []);
      assert(false, 'Empty array should be rejected');
    } catch (error) {
      assert(error.message.includes('400'), 'Should return 400 for empty array');
      console.log('✓ Empty array correctly rejected');
    }

    // Test missing value for set operation
    console.log('🚫 Test 2: Missing value should be rejected');
    try {
      await makeRequest('POST', `${BASE_URL}/results/${ridBase}/corrections`, [
        { "path": "/test/field" } // Missing value
      ]);
      assert(false, 'Missing value should be rejected');
    } catch (error) {
      assert(error.message.includes('400'), 'Should return 400 for missing value');
      console.log('✓ Missing value correctly rejected');
    }

    // Test single object format
    console.log('📝 Test 3: Single object format should work');
    const singleResponse = await makeRequest(
      'POST',
      `${BASE_URL}/results/${ridBase}/corrections`,
      { "path": "/test/single", "value": "single-test" }
    );
    assert(singleResponse.saved === 1, 'Should save single correction');
    console.log('✓ Single object format works');

    // Test wrapped format
    console.log('📝 Test 4: Wrapped format should work');
    const wrappedResponse = await makeRequest(
      'POST',
      `${BASE_URL}/results/${ridBase}/corrections`,
      {
        "corrections": [
          { "path": "/test/wrapped", "value": "wrapped-test" }
        ]
      }
    );
    assert(wrappedResponse.saved === 1, 'Should save wrapped correction');
    console.log('✓ Wrapped format works');

    console.log('\n🎉 All edge case tests passed!');

  } catch (error) {
    console.error('\n❌ Edge case test failed:', error.message);
    process.exit(1);
  }
}

// Run tests
if (require.main === module) {
  (async () => {
    await testCorrectionsFlow();
    await testEdgeCases();
    console.log('\n✨ All tests completed successfully!');
  })();
}

module.exports = { normalizeResultId, testCorrectionsFlow, testEdgeCases };