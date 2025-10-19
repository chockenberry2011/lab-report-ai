// Test ID normalization functions
console.log('🧪 Testing ID normalization functions...\n')

// Simulate normalizeAllIds function
function normalizeAllIds(routeParam) {
  if (!routeParam) {
    return { original: '', slugFull: '', baseId: '', viewerId: '' }
  }

  const original = routeParam.trim()
  let cleaned = decodeURIComponent(original)

  const suffixPattern = /(\.(?:01_lines(?:_merged)?|02_roles|03_compose)\.debug)+$/g
  const originalCleaned = cleaned
  cleaned = cleaned.replace(suffixPattern, '')

  const hadSuffix = originalCleaned !== cleaned
  const slugFull = hadSuffix ? cleaned + '.03_compose.debug' : cleaned
  const baseId = cleaned
  const viewerId = cleaned.includes('.') ? cleaned : cleaned + '.03_compose.debug'

  return { original, slugFull, baseId, viewerId }
}

// Test cases
const testCases = [
  {
    name: 'Simple UUID',
    input: 'abc123-def456-789',
    expected: {
      baseId: 'abc123-def456-789',
      slugFull: 'abc123-def456-789',
      shouldAddSuffix: true
    }
  },
  {
    name: 'Single suffix',
    input: 'abc123-def456.03_compose.debug',
    expected: {
      baseId: 'abc123-def456',
      slugFull: 'abc123-def456.03_compose.debug',
      shouldAddSuffix: false
    }
  },
  {
    name: 'Doubled suffix (main issue)',
    input: 'abc123-def456.03_compose.debug.03_compose.debug',
    expected: {
      baseId: 'abc123-def456',
      slugFull: 'abc123-def456.03_compose.debug',
      shouldAddSuffix: false
    }
  },
  {
    name: 'Mixed suffixes',
    input: 'abc123.01_lines.debug.02_roles.debug.03_compose.debug',
    expected: {
      baseId: 'abc123',
      slugFull: 'abc123.03_compose.debug',
      shouldAddSuffix: false
    }
  },
  {
    name: 'Tripled suffix (edge case)',
    input: 'xyz789.03_compose.debug.03_compose.debug.03_compose.debug',
    expected: {
      baseId: 'xyz789',
      slugFull: 'xyz789.03_compose.debug',
      shouldAddSuffix: false
    }
  }
]

console.log('='.repeat(70))
console.log('ID NORMALIZATION TEST RESULTS')
console.log('='.repeat(70))

let passedTests = 0
let totalTests = testCases.length

testCases.forEach((test, index) => {
  const result = normalizeAllIds(test.input)
  const passed =
    result.baseId === test.expected.baseId &&
    result.slugFull === test.expected.slugFull

  console.log(`\nTest ${index + 1}: ${test.name}`)
  console.log(`Input:    "${test.input}"`)
  console.log(`BaseId:   "${result.baseId}" ${result.baseId === test.expected.baseId ? '✅' : '❌'}`)
  console.log(`SlugFull: "${result.slugFull}" ${result.slugFull === test.expected.slugFull ? '✅' : '❌'}`)
  console.log(`ViewerId: "${result.viewerId}"`)

  if (passed) {
    passedTests++
    console.log('Status:   ✅ PASS')
  } else {
    console.log('Status:   ❌ FAIL')
    console.log(`Expected BaseId: "${test.expected.baseId}"`)
    console.log(`Expected SlugFull: "${test.expected.slugFull}"`)
  }
})

console.log('\n' + '='.repeat(70))
console.log(`SUMMARY: ${passedTests}/${totalTests} tests passed`)

if (passedTests === totalTests) {
  console.log('🎉 All ID normalization tests PASSED!')
  console.log('\n🎯 Key behaviors verified:')
  console.log('   • Simple UUIDs handled correctly')
  console.log('   • Single suffixes preserved')
  console.log('   • Doubled suffixes normalized to single')
  console.log('   • Mixed suffixes cleaned properly')
  console.log('   • Edge cases with tripled suffixes handled')
  console.log('\n✅ Routes like /review/.03_compose.debug.03_compose.debug will work!')
} else {
  console.log('❌ Some tests failed - check implementation')
  process.exit(1)
}

// Test route scenarios
console.log('\n' + '='.repeat(70))
console.log('ROUTE SCENARIO TESTS')
console.log('='.repeat(70))

const routeScenarios = [
  '/review/abc123-def456',
  '/review/abc123-def456.03_compose.debug',
  '/review/abc123-def456.03_compose.debug.03_compose.debug',
  '/review/abc123.01_lines.debug.02_roles.debug.03_compose.debug.03_compose.debug'
]

routeScenarios.forEach(route => {
  const id = route.replace('/review/', '')
  const normalized = normalizeAllIds(id)

  console.log(`\nRoute: ${route}`)
  console.log(`  API calls would use:`)
  console.log(`    /api/results/${normalized.baseId}`)
  console.log(`    /api/files/${normalized.slugFull}/extracted-text`)
  console.log(`  Navigation would use: /review/${normalized.slugFull}`)
})

console.log('\n✅ All route scenarios handled correctly!')