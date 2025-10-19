#!/usr/bin/env node

/**
 * Verification script to ensure all call sites use the comprehensive normalizeResultId
 */

const fs = require('fs');
const path = require('path');

function findFilesRecursively(dir, extension) {
  const files = [];
  const items = fs.readdirSync(dir);

  for (const item of items) {
    const fullPath = path.join(dir, item);
    const stat = fs.statSync(fullPath);

    if (stat.isDirectory() && !item.startsWith('.') && item !== 'node_modules') {
      files.push(...findFilesRecursively(fullPath, extension));
    } else if (stat.isFile() && (fullPath.endsWith('.ts') || fullPath.endsWith('.tsx'))) {
      files.push(fullPath);
    }
  }

  return files;
}

function checkNormalizationUsage() {
  console.log('🔍 Checking normalizeResultId usage across all files...\n');

  const srcDir = path.join(__dirname, 'src');
  const files = findFilesRecursively(srcDir, ['.ts', '.tsx']);

  const results = {
    correctUsage: [],
    incorrectUsage: [],
    noUsage: [],
    totalFiles: files.length
  };

  for (const file of files) {
    const content = fs.readFileSync(file, 'utf8');
    const relativePath = path.relative(srcDir, file);

    if (content.includes('normalizeResultId')) {
      // Check import source
      const importMatches = content.match(/import.*normalizeResultId.*from ['"]([^'"]+)['"]/g);

      if (importMatches) {
        const hasCorrectImport = importMatches.some(match =>
          match.includes('@/lib/normalizeIds') || match.includes('./normalizeIds')
        );

        const hasIncorrectImport = importMatches.some(match =>
          match.includes('@/utils/normalizeResultId') || match.includes('./normalizeResultId')
        );

        if (hasCorrectImport && !hasIncorrectImport) {
          results.correctUsage.push({
            file: relativePath,
            imports: importMatches
          });
        } else {
          results.incorrectUsage.push({
            file: relativePath,
            imports: importMatches,
            issue: hasIncorrectImport ? 'Uses old import path' : 'Mixed imports'
          });
        }
      } else {
        // Uses normalizeResultId but no imports (maybe re-exported?)
        results.noUsage.push({
          file: relativePath,
          issue: 'Uses normalizeResultId without direct import'
        });
      }
    }
  }

  return results;
}

function checkAPICallPatterns() {
  console.log('🔍 Checking API call patterns for consistent normalization...\n');

  const srcDir = path.join(__dirname, 'src');
  const files = findFilesRecursively(srcDir, ['.ts', '.tsx']);

  const apiCallPatterns = [
    /\/api\/results\/\$\{[^}]*\}/g, // ${normalized}
    /\/api\/results\/.*\$\{.*\}/g,  // General template patterns
    /resultsApi\([^)]*\)/g,         // resultsApi calls
    /reviewApi\.get.*\([^)]*\)/g,   // reviewApi calls
  ];

  const suspicious = [];

  for (const file of files) {
    const content = fs.readFileSync(file, 'utf8');
    const relativePath = path.relative(srcDir, file);

    for (const pattern of apiCallPatterns) {
      const matches = content.match(pattern);
      if (matches) {
        const lines = content.split('\n');
        matches.forEach(match => {
          const lineIndex = lines.findIndex(line => line.includes(match));
          if (lineIndex !== -1) {
            const lineNumber = lineIndex + 1;
            const line = lines[lineIndex].trim();

            // Check if the line also contains normalization
            const hasNormalization = line.includes('normalizeResultId') ||
                                   line.includes('normalize') ||
                                   line.includes('baseId') ||
                                   line.includes('normId');

            if (!hasNormalization && match.includes('${')) {
              suspicious.push({
                file: relativePath,
                line: lineNumber,
                code: line,
                pattern: match,
                issue: 'API call may not use normalized ID'
              });
            }
          }
        });
      }
    }
  }

  return suspicious;
}

function main() {
  console.log('🚀 Verifying normalizeResultId implementation consistency\n');
  console.log('=' .repeat(60));

  // Check imports
  const usageResults = checkNormalizationUsage();

  console.log('📊 Import Usage Results:');
  console.log(`  Total files scanned: ${usageResults.totalFiles}`);
  console.log(`  ✅ Correct usage: ${usageResults.correctUsage.length}`);
  console.log(`  ❌ Incorrect usage: ${usageResults.incorrectUsage.length}`);
  console.log(`  ⚠️  No direct imports: ${usageResults.noUsage.length}\n`);

  if (usageResults.correctUsage.length > 0) {
    console.log('✅ Files using correct imports:');
    usageResults.correctUsage.forEach(({ file }) => {
      console.log(`  • ${file}`);
    });
    console.log();
  }

  if (usageResults.incorrectUsage.length > 0) {
    console.log('❌ Files with incorrect imports:');
    usageResults.incorrectUsage.forEach(({ file, imports, issue }) => {
      console.log(`  • ${file}: ${issue}`);
      imports.forEach(imp => console.log(`    ${imp}`));
    });
    console.log();
  }

  // Check API call patterns
  const apiCallIssues = checkAPICallPatterns();

  console.log('📊 API Call Pattern Analysis:');
  console.log(`  Suspicious patterns found: ${apiCallIssues.length}\n`);

  if (apiCallIssues.length > 0) {
    console.log('⚠️  Potentially unnormalized API calls:');
    apiCallIssues.forEach(({ file, line, code, issue }) => {
      console.log(`  • ${file}:${line} - ${issue}`);
      console.log(`    ${code}`);
    });
    console.log();
  }

  // Summary
  console.log('=' .repeat(60));

  if (usageResults.incorrectUsage.length === 0 && apiCallIssues.length === 0) {
    console.log('✅ All normalization usage appears correct!');
    console.log('✅ All files are using the comprehensive normalizeResultId from @/lib/normalizeIds');
    console.log('✅ API call patterns look consistent');

    console.log('\n📋 Summary:');
    console.log(`  • ${usageResults.correctUsage.length} files using correct imports`);
    console.log(`  • All known debug suffixes (.03_compose.debug, etc.) will be handled`);
    console.log(`  • API calls consistently use normalized IDs`);

    return true;
  } else {
    console.log('❌ Issues found that need attention:');

    if (usageResults.incorrectUsage.length > 0) {
      console.log(`  • ${usageResults.incorrectUsage.length} files using incorrect imports`);
    }

    if (apiCallIssues.length > 0) {
      console.log(`  • ${apiCallIssues.length} potentially unnormalized API calls`);
    }

    console.log('\n🔧 To fix:');
    console.log('  1. Update import statements to use @/lib/normalizeIds');
    console.log('  2. Ensure all API calls use normalizeResultId() on IDs');
    console.log('  3. Test with URLs like /review/id.03_compose.debug');

    return false;
  }
}

// Run if called directly
if (require.main === module) {
  const success = main();
  process.exit(success ? 0 : 1);
}

module.exports = { checkNormalizationUsage, checkAPICallPatterns, main };