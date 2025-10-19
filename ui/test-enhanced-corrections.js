#!/usr/bin/env node

/**
 * Simple integration test for the enhanced corrections system
 * Tests both new path-based corrections and legacy line-based corrections
 */

const fetch = require('node-fetch');

const API_BASE = process.env.API_BASE || 'http://localhost:8000/api';
const TEST_RESULT_ID = process.argv[2] || 'test-result-id';

async function testCorrections() {
  console.log('🧪 Testing Enhanced Corrections System');
  console.log('=====================================\n');

  // Test 1: New path-based corrections
  console.log('1️⃣ Testing new path-based corrections...');
  try {
    const newFormatPayload = {
      items: [
        { op: "set", path: "patient.first_name", value: "Alice" },
        { op: "set", path: "vendor.name", value: "Quest Diagnostics" },
        { op: "unset", path: "patient.mrn" },
        { op: "set", path: "specimen.collected_at", value: "2024-09-01T08:30:00" }
      ]
    };

    const response = await fetch(`${API_BASE}/results/${TEST_RESULT_ID}/corrections`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newFormatPayload)
    });

    if (response.ok) {
      console.log('   ✅ New format corrections saved successfully');
    } else {
      const error = await response.text();
      console.log(`   ❌ New format failed: ${response.status} ${error}`);
    }
  } catch (error) {
    console.log(`   ❌ New format error: ${error.message}`);
  }

  // Test 2: Legacy line-based corrections (backward compatibility)
  console.log('\n2️⃣ Testing legacy line-based corrections...');
  try {
    const legacyFormatPayload = {
      corrections: [
        { line_number: 5, field: "test_name", new_value: "Glucose", old_value: "GLU" },
        { line_number: 6, field: "result_value", new_value: "95", old_value: "94" }
      ]
    };

    const response = await fetch(`${API_BASE}/results/${TEST_RESULT_ID}/corrections`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(legacyFormatPayload)
    });

    if (response.ok) {
      console.log('   ✅ Legacy format corrections saved successfully');
    } else {
      const error = await response.text();
      console.log(`   ❌ Legacy format failed: ${response.status} ${error}`);
    }
  } catch (error) {
    console.log(`   ❌ Legacy format error: ${error.message}`);
  }

  // Test 3: Retrieve corrections
  console.log('\n3️⃣ Testing corrections retrieval...');
  try {
    const response = await fetch(`${API_BASE}/results/${TEST_RESULT_ID}/corrections`);
    
    if (response.ok) {
      const data = await response.json();
      console.log('   ✅ Corrections retrieved successfully');
      console.log(`   📄 Format: ${Array.isArray(data) ? 'Legacy array' : 'New object with items'}`);
      
      if (Array.isArray(data)) {
        console.log(`   📊 Count: ${data.length} corrections`);
      } else if (data.items) {
        console.log(`   📊 Count: ${data.items.length} corrections`);
        console.log(`   📋 Schema version: ${data.schema_version || 'undefined'}`);
      }
    } else {
      const error = await response.text();
      console.log(`   ❌ Retrieval failed: ${response.status} ${error}`);
    }
  } catch (error) {
    console.log(`   ❌ Retrieval error: ${error.message}`);
  }

  // Test 4: Backward compatibility - mixed format  
  console.log('\n4️⃣ Testing mixed format (items without op)...');
  try {
    const mixedFormatPayload = {
      items: [
        { path: "patient.last_name", value: "Smith" }, // no op, should default to "set"
        { op: "set", path: "patient.dob", value: "1985-03-15" }
      ]
    };

    const response = await fetch(`${API_BASE}/results/${TEST_RESULT_ID}/corrections`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(mixedFormatPayload)
    });

    if (response.ok) {
      console.log('   ✅ Mixed format (backward compatible) saved successfully');
    } else {
      const error = await response.text();
      console.log(`   ❌ Mixed format failed: ${response.status} ${error}`);
    }
  } catch (error) {
    console.log(`   ❌ Mixed format error: ${error.message}`);
  }

  console.log('\n🎉 Test completed!');
  console.log('\nUsage: node test-enhanced-corrections.js [result-id]');
  console.log('Example: node test-enhanced-corrections.js abc123');
}

if (require.main === module) {
  testCorrections();
}

module.exports = { testCorrections };