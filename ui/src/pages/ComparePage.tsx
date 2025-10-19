import React, { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { ArrowLeft, Download, Upload, Check, X, AlertTriangle, FileText, GitCompare } from 'lucide-react';
import { toast } from 'react-hot-toast';
import { normalizeResultId, ensureViewerId } from '@/lib/normalizeIds';

interface CompareData {
  original: any;
  corrected: any;
  originalExists: boolean;
  correctedExists: boolean;
}

interface DiffItem {
  path: string;
  originalValue: any;
  correctedValue: any;
  type: 'added' | 'removed' | 'modified' | 'unchanged';
}

export default function ComparePage() {
  const { jobId: paramId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();

  // Normalize the IDs
  const viewerId = paramId ? ensureViewerId(paramId) : undefined
  const baseId = paramId ? normalizeResultId(paramId) : undefined
  const jobId = baseId // Use baseId for API calls that expect the normalized ID
  
  const [compareData, setCompareData] = useState<CompareData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [promoting, setPromoting] = useState(false);
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (jobId) {
      loadCompareData(jobId);
    }
  }, [jobId]);

  const loadCompareData = async (jobId: string) => {
    setLoading(true);
    setError(null);

    const viewerId = ensureViewerId(jobId)
    const baseId = normalizeResultId(jobId)

    try {
      // Load both files - try viewer ID first, fallback to base ID
      const [originalResponse, correctedResponse] = await Promise.allSettled([
        // Try viewer-friendly URL first, fallback to base ID
        fetch(`/api/files/outbox/${viewerId}.json`).catch(() =>
          fetch(`/api/files/outbox/${baseId}.json`)
        ),
        fetch(`/api/files/expected/${viewerId}.json`).catch(() =>
          fetch(`/api/files/expected/${baseId}.json`)
        )
      ]);

      const compareData: CompareData = {
        original: null,
        corrected: null,
        originalExists: false,
        correctedExists: false
      };

      // Process original file
      if (originalResponse.status === 'fulfilled' && originalResponse.value.ok) {
        compareData.original = await originalResponse.value.json();
        compareData.originalExists = true;
      } else if (originalResponse.status === 'fulfilled' && originalResponse.value.status !== 404) {
        console.warn('Error loading original file:', originalResponse.value.statusText);
      }

      // Process corrected file
      if (correctedResponse.status === 'fulfilled' && correctedResponse.value.ok) {
        compareData.corrected = await correctedResponse.value.json();
        compareData.correctedExists = true;
      } else if (correctedResponse.status === 'fulfilled' && correctedResponse.value.status !== 404) {
        console.warn('Error loading corrected file:', correctedResponse.value.statusText);
      }

      if (!compareData.originalExists && !compareData.correctedExists) {
        setError(`No files found for job ${jobId}. Check that the job exists and has results.`);
      } else {
        setCompareData(compareData);
      }

    } catch (err) {
      console.error('Error loading compare data:', err);
      setError('Failed to load comparison data. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const computeDiff = (original: any, corrected: any, path = ''): DiffItem[] => {
    const diffs: DiffItem[] = [];

    if (original === null || original === undefined) {
      if (corrected !== null && corrected !== undefined) {
        diffs.push({
          path,
          originalValue: original,
          correctedValue: corrected,
          type: 'added'
        });
      }
      return diffs;
    }

    if (corrected === null || corrected === undefined) {
      diffs.push({
        path,
        originalValue: original,
        correctedValue: corrected,
        type: 'removed'
      });
      return diffs;
    }

    if (typeof original !== typeof corrected) {
      diffs.push({
        path,
        originalValue: original,
        correctedValue: corrected,
        type: 'modified'
      });
      return diffs;
    }

    if (Array.isArray(original) && Array.isArray(corrected)) {
      const maxLength = Math.max(original.length, corrected.length);
      for (let i = 0; i < maxLength; i++) {
        const itemPath = `${path}[${i}]`;
        if (i >= original.length) {
          diffs.push({
            path: itemPath,
            originalValue: undefined,
            correctedValue: corrected[i],
            type: 'added'
          });
        } else if (i >= corrected.length) {
          diffs.push({
            path: itemPath,
            originalValue: original[i],
            correctedValue: undefined,
            type: 'removed'
          });
        } else {
          diffs.push(...computeDiff(original[i], corrected[i], itemPath));
        }
      }
      return diffs;
    }

    if (typeof original === 'object' && typeof corrected === 'object') {
      const allKeys = new Set([...Object.keys(original), ...Object.keys(corrected)]);
      
      for (const key of allKeys) {
        const keyPath = path ? `${path}.${key}` : key;
        
        if (!(key in original)) {
          diffs.push({
            path: keyPath,
            originalValue: undefined,
            correctedValue: corrected[key],
            type: 'added'
          });
        } else if (!(key in corrected)) {
          diffs.push({
            path: keyPath,
            originalValue: original[key],
            correctedValue: undefined,
            type: 'removed'
          });
        } else {
          diffs.push(...computeDiff(original[key], corrected[key], keyPath));
        }
      }
      return diffs;
    }

    // Primitive values
    if (original === corrected) {
      diffs.push({
        path,
        originalValue: original,
        correctedValue: corrected,
        type: 'unchanged'
      });
    } else {
      diffs.push({
        path,
        originalValue: original,
        correctedValue: corrected,
        type: 'modified'
      });
    }

    return diffs;
  };

  const diffItems = useMemo(() => {
    if (!compareData) return [];
    
    const original = compareData.original || {};
    const corrected = compareData.corrected || {};
    
    return computeDiff(original, corrected);
  }, [compareData]);

  const diffStats = useMemo(() => {
    const stats = {
      added: 0,
      removed: 0,
      modified: 0,
      unchanged: 0
    };

    diffItems.forEach(item => {
      stats[item.type]++;
    });

    return stats;
  }, [diffItems]);

  const promoteToGolden = async () => {
    if (!jobId || !compareData?.correctedExists) return;

    setPromoting(true);
    try {
      const response = await fetch(`/api/golden/promote/${jobId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        toast.success('✅ Corrections promoted to golden set!');
        // Reload data to show updated state
        await loadCompareData(jobId);
      } else {
        const error = await response.text();
        toast.error(`Failed to promote corrections: ${error}`);
      }
    } catch (err) {
      console.error('Error promoting corrections:', err);
      toast.error('Failed to promote corrections. Please try again.');
    } finally {
      setPromoting(false);
    }
  };

  const downloadFile = (data: any, filename: string) => {
    const blob = new Blob([JSON.stringify(data, null, 2)], { 
      type: 'application/json' 
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const toggleExpanded = (path: string) => {
    const newExpanded = new Set(expandedPaths);
    if (newExpanded.has(path)) {
      newExpanded.delete(path);
    } else {
      newExpanded.add(path);
    }
    setExpandedPaths(newExpanded);
  };

  const formatValue = (value: any): string => {
    if (value === null) return 'null';
    if (value === undefined) return 'undefined';
    if (typeof value === 'string') return `"${value}"`;
    if (typeof value === 'object') return JSON.stringify(value, null, 2);
    return String(value);
  };

  const getDiffIcon = (type: string) => {
    switch (type) {
      case 'added': return <span className="text-green-600">+</span>;
      case 'removed': return <span className="text-red-600">-</span>;
      case 'modified': return <span className="text-yellow-600">~</span>;
      default: return <span className="text-gray-400">=</span>;
    }
  };

  const getDiffColor = (type: string) => {
    switch (type) {
      case 'added': return 'bg-green-50 border-l-green-500';
      case 'removed': return 'bg-red-50 border-l-red-500';
      case 'modified': return 'bg-yellow-50 border-l-yellow-500';
      default: return 'bg-gray-50 border-l-gray-300';
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading comparison data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 p-6">
        <div className="max-w-4xl mx-auto">
          <div className="bg-red-50 border border-red-200 rounded-lg p-6">
            <div className="flex items-center">
              <AlertTriangle className="h-6 w-6 text-red-600 mr-3" />
              <div>
                <h2 className="text-lg font-semibold text-red-800">Error Loading Comparison</h2>
                <p className="text-red-700 mt-1">{error}</p>
              </div>
            </div>
            <div className="mt-4">
              <Link
                to="/processed"
                className="inline-flex items-center px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
              >
                <ArrowLeft className="h-4 w-4 mr-2" />
                Back to Processed Results
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <button
                onClick={() => navigate('/processed')}
                className="mr-4 p-2 text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <ArrowLeft className="h-5 w-5" />
              </button>
              <div>
                <h1 className="text-2xl font-bold text-gray-900 flex items-center">
                  <GitCompare className="h-6 w-6 mr-3 text-blue-600" />
                  Compare Results
                </h1>
                <p className="text-gray-600">Job ID: {jobId}</p>
              </div>
            </div>
            
            <div className="flex items-center space-x-3">
              {compareData?.originalExists && (
                <button
                  onClick={() => downloadFile(compareData.original, `${jobId}_original.json`)}
                  className="flex items-center px-3 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
                >
                  <Download className="h-4 w-4 mr-2" />
                  Original
                </button>
              )}
              
              {compareData?.correctedExists && (
                <button
                  onClick={() => downloadFile(compareData.corrected, `${jobId}_corrected.json`)}
                  className="flex items-center px-3 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
                >
                  <Download className="h-4 w-4 mr-2" />
                  Corrected
                </button>
              )}

              {compareData?.correctedExists && (
                <button
                  onClick={promoteToGolden}
                  disabled={promoting}
                  className="flex items-center px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {promoting ? (
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                  ) : (
                    <Upload className="h-4 w-4 mr-2" />
                  )}
                  Promote to Golden
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6">
        {/* Stats Summary */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-white rounded-lg p-4 border border-gray-200">
            <div className="flex items-center">
              <div className="w-3 h-3 bg-green-500 rounded-full mr-2"></div>
              <span className="text-sm font-medium text-gray-600">Added</span>
            </div>
            <div className="text-2xl font-bold text-gray-900">{diffStats.added}</div>
          </div>
          
          <div className="bg-white rounded-lg p-4 border border-gray-200">
            <div className="flex items-center">
              <div className="w-3 h-3 bg-red-500 rounded-full mr-2"></div>
              <span className="text-sm font-medium text-gray-600">Removed</span>
            </div>
            <div className="text-2xl font-bold text-gray-900">{diffStats.removed}</div>
          </div>
          
          <div className="bg-white rounded-lg p-4 border border-gray-200">
            <div className="flex items-center">
              <div className="w-3 h-3 bg-yellow-500 rounded-full mr-2"></div>
              <span className="text-sm font-medium text-gray-600">Modified</span>
            </div>
            <div className="text-2xl font-bold text-gray-900">{diffStats.modified}</div>
          </div>
          
          <div className="bg-white rounded-lg p-4 border border-gray-200">
            <div className="flex items-center">
              <div className="w-3 h-3 bg-gray-400 rounded-full mr-2"></div>
              <span className="text-sm font-medium text-gray-600">Unchanged</span>
            </div>
            <div className="text-2xl font-bold text-gray-900">{diffStats.unchanged}</div>
          </div>
        </div>

        {/* File Status */}
        <div className="bg-white rounded-lg border border-gray-200 mb-6 p-4">
          <h3 className="text-lg font-semibold text-gray-900 mb-3">File Status</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="flex items-center">
              <FileText className="h-5 w-5 text-blue-600 mr-3" />
              <div>
                <div className="font-medium text-gray-900">Original (outbox)</div>
                <div className="text-sm text-gray-600">
                  {compareData?.originalExists ? (
                    <span className="flex items-center text-green-600">
                      <Check className="h-4 w-4 mr-1" />
                      Available
                    </span>
                  ) : (
                    <span className="flex items-center text-red-600">
                      <X className="h-4 w-4 mr-1" />
                      Not found
                    </span>
                  )}
                </div>
              </div>
            </div>
            
            <div className="flex items-center">
              <FileText className="h-5 w-5 text-green-600 mr-3" />
              <div>
                <div className="font-medium text-gray-900">Corrected (expected)</div>
                <div className="text-sm text-gray-600">
                  {compareData?.correctedExists ? (
                    <span className="flex items-center text-green-600">
                      <Check className="h-4 w-4 mr-1" />
                      Available
                    </span>
                  ) : (
                    <span className="flex items-center text-red-600">
                      <X className="h-4 w-4 mr-1" />
                      Not found
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Diff Viewer */}
        <div className="bg-white rounded-lg border border-gray-200">
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-lg font-semibold text-gray-900">Differences</h3>
            <p className="text-sm text-gray-600">
              Showing changes between original and corrected versions
            </p>
          </div>
          
          <div className="divide-y divide-gray-200">
            {diffItems.length === 0 ? (
              <div className="p-6 text-center text-gray-500">
                No data to compare
              </div>
            ) : (
              diffItems.filter(item => item.type !== 'unchanged').map((item, index) => (
                <div key={index} className={`p-4 border-l-4 ${getDiffColor(item.type)}`}>
                  <div className="flex items-start">
                    <div className="flex-shrink-0 mr-3 mt-1">
                      {getDiffIcon(item.type)}
                    </div>
                    <div className="flex-grow min-w-0">
                      <div className="font-mono text-sm font-medium text-gray-900 mb-2">
                        {item.path || '<root>'}
                      </div>
                      
                      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                        <div>
                          <div className="text-xs font-medium text-gray-600 uppercase tracking-wide mb-1">
                            Original
                          </div>
                          <pre className="text-sm bg-gray-100 p-3 rounded border overflow-x-auto">
                            {formatValue(item.originalValue)}
                          </pre>
                        </div>
                        
                        <div>
                          <div className="text-xs font-medium text-gray-600 uppercase tracking-wide mb-1">
                            Corrected
                          </div>
                          <pre className="text-sm bg-gray-100 p-3 rounded border overflow-x-auto">
                            {formatValue(item.correctedValue)}
                          </pre>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {diffStats.unchanged > 0 && (
          <div className="mt-6 bg-white rounded-lg border border-gray-200 p-4">
            <div className="text-center text-gray-500">
              <p>{diffStats.unchanged} unchanged fields not shown</p>
              <button
                onClick={() => {
                  // Toggle showing unchanged items
                  toast.info('Feature coming soon: Show/hide unchanged fields');
                }}
                className="text-blue-600 hover:text-blue-800 text-sm underline mt-1"
              >
                Show all fields
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}