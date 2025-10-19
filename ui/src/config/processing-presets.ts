// Processing configuration presets
// This module contains no React imports or page references

import type { ProcessingConfig } from '@/types'

export const configPresets: Record<string, { name: string; description: string; config: ProcessingConfig }> = {
  default: {
    name: 'Default',
    description: 'Standard processing settings',
    config: {
      extraction: { dpi: 150, extract_images: false },
      composition: {
        scoring: {
          value_parse_threshold: 0.7,
          unit_validity_threshold: 0.8,
          panel_score_threshold: 0.7,
          document_score_threshold: 0.75,
        },
      },
    },
  },
  high_quality: {
    name: 'High Quality',
    description: 'Strict thresholds, high DPI',
    config: {
      extraction: { dpi: 200, extract_images: true },
      composition: {
        scoring: {
          value_parse_threshold: 0.9,
          unit_validity_threshold: 0.9,
          panel_score_threshold: 0.8,
          document_score_threshold: 0.85,
        },
      },
    },
  },
  fast: {
    name: 'Fast Processing',
    description: 'Lenient thresholds, optimized for speed',
    config: {
      extraction: { dpi: 120, extract_images: false },
      composition: {
        scoring: {
          value_parse_threshold: 0.5,
          unit_validity_threshold: 0.6,
          panel_score_threshold: 0.5,
          document_score_threshold: 0.6,
        },
      },
    },
  },
}