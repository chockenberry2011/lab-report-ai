"""
Scoring module for evaluating confidence in parsed lab data
"""

import re
import math
from typing import List, Dict, Set, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from statistics import mean, median

from .schemas import Panel, TestRow

# Export list for debugging
__all__ = [
    'FieldConfidence',
    'PanelScore', 
    'DocumentScore',
    'LabDataScorer',
    '_lookup_line_proba'  # For debugging classifier probability issues
]

# Must reflect the trained model's label order saved in metadata (fallback default):
DEFAULT_ROLE_LABELS = [
    "JUNK", "HEADER_SPECIMEN", "HEADER_PATIENT",
    "PAGE_HEADER", "SECTION_PANEL", "TEST_ROW", "PAGE_FOOTER"
]




def _normalize_role_proba(payload, label_order=None, predicted_label=None):
    """
    Accepts:
      - dict {label: prob}
      - list/ndarray ordered by label_order
      - float -> assign to predicted_label if provided
    Returns dict {label: prob} or {}.
    """
    if payload is None:
        return {}

    # dict of label->prob
    if isinstance(payload, dict):
        # Might be nested in {'distribution': {...}}
        if 'distribution' in payload and isinstance(payload['distribution'], dict):
            return {k: float(v) for k, v in payload['distribution'].items()}
        # Or already {label: prob}
        return {k: float(v) for k, v in payload.items() if isinstance(v, (int, float))}

    # list-like with order
    try:
        import numpy as np
        is_listlike = isinstance(payload, (list, tuple)) or (hasattr(payload, 'shape') and hasattr(payload, '__array__'))
    except Exception:
        is_listlike = isinstance(payload, (list, tuple))

    if is_listlike:
        labels = label_order or DEFAULT_ROLE_LABELS
        return {labels[i]: float(payload[i]) for i in range(min(len(payload), len(labels)))}

    # single float -> slap onto predicted label
    if isinstance(payload, (int, float)) and predicted_label:
        return {predicted_label: float(payload)}

    return {}


def _lookup_line_proba(prob, line_number: int, label: str = "TEST_ROW") -> Optional[float]:
    """
    Look up the probability for a given label on a given line number.

    Supports shapes:
      - dict: { line_no -> {label: p, ...} } or { line_no -> {'distribution': {...}} }
      - aligned list: [ {label: p, ...} or None, ... ] where index == line_no
      - list of objects: [ { 'line_number': n, 'distribution': {...} }, ... ]

    Returns None when not found or malformed.
    """
    try:
        if prob is None or line_number is None:
            return None

        # Mapping by line number
        if isinstance(prob, dict):
            entry = prob.get(line_number)
            if entry is None:
                return None
            # Entry may be a distribution dict or wrapper {'distribution': {...}}
            if isinstance(entry, dict):
                dist = entry.get('distribution') if 'distribution' in entry and isinstance(entry.get('distribution'), dict) else entry
                val = dist.get(label) if isinstance(dist, dict) else None
                return float(val) if isinstance(val, (int, float)) else None
            if isinstance(entry, (int, float)):
                return float(entry)
            return None

        # List forms
        if isinstance(prob, list):
            # List of objects: each has line_number and distribution
            if prob and isinstance(prob[0], dict) and 'line_number' in prob[0]:
                for item in prob:
                    if not isinstance(item, dict):
                        continue
                    if item.get('line_number') == line_number:
                        # Prefer an explicit distribution field
                        dist = item.get('distribution')
                        if isinstance(dist, dict):
                            val = dist.get(label)
                            return float(val) if isinstance(val, (int, float)) else None
                        # Support direct probabilities on the item itself
                        if isinstance(item, dict):
                            direct_val = item.get(label)
                            if isinstance(direct_val, (int, float)):
                                return float(direct_val)
                        # allow direct numeric
                        if isinstance(dist, (int, float)):
                            return float(dist)
                        return None
                return None
            # Aligned by index (allow None gaps)
            if 0 <= line_number < len(prob):
                entry = prob[line_number]
                if entry is None:
                    return None
                if isinstance(entry, dict):
                    val = entry.get(label)
                    return float(val) if isinstance(val, (int, float)) else None
                if isinstance(entry, (int, float)):
                    return float(entry)
                return None

        return None
    except Exception:
        return None


@dataclass
class FieldConfidence:
    """Confidence scores for individual fields"""
    value_parse: float = 0.0
    unit_validity: float = 0.0
    reference_range: float = 0.0
    test_name_clarity: float = 0.0
    classifier_proba: float = 0.5  # Default confidence for role classification
    overall: float = 0.0
    
    def to_dict(self) -> Dict[str, float]:
        return asdict(self)


@dataclass
class PanelScore:
    """Scoring information for a panel"""
    continuity_score: float
    coherence_score: float
    avg_field_confidence: float
    test_count: int
    overall_score: float
    needs_review: bool
    review_reasons: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'continuity_score': self.continuity_score,
            'coherence_score': self.coherence_score,
            'avg_field_confidence': self.avg_field_confidence,
            'test_count': self.test_count,
            'overall_score': self.overall_score,
            'needs_review': self.needs_review,
            'review_reasons': self.review_reasons
        }


@dataclass
class DocumentScore:
    """Overall document scoring"""
    total_panels: int
    total_tests: int
    avg_panel_score: float
    confidence_distribution: Dict[str, float]
    overall_score: float
    needs_review: bool
    review_reasons: List[str]
    high_confidence_panels: int
    low_confidence_panels: int
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class LabDataScorer:
    """
    Comprehensive scoring system for lab data quality assessment.
    
    This module provides multi-level confidence scoring:
    
    FIELD-LEVEL SCORING:
    - VALUE: Numeric parse success (patterns: integer, decimal, scientific, ranges, qualitative)
    - UNIT: Unit validity against medical unit whitelist (concentration, blood count, etc.)  
    - REF_RANGE: Reference range well-formedness (numeric ranges, qualitative, boundaries)
    - TEST_NAME: Test name clarity based on length, medical terminology, formatting
    - CLASSIFIER: Role classification probability from ML model
    
    PANEL-LEVEL SCORING:
    - Panel continuity across page breaks
    - Panel coherence (consistency of test patterns)
    - Average field confidence across all tests
    - Critical field failure detection
    
    DOCUMENT-LEVEL SCORING:
    - Overall confidence distribution statistics
    - High/low confidence panel classification
    - Structural quality assessment
    
    REVIEW FLAGGING:
    - Configurable thresholds for each scoring dimension
    - Automatic needsReview flagging when scores fall below thresholds
    - Detailed reasons[] array explaining why review is needed
    
    All confidence scores and review flags are persisted in the final JSON output.
    """
    
    def __init__(self, 
                 value_parse_threshold: float = 0.7,
                 unit_validity_threshold: float = 0.8,
                 ref_range_threshold: float = 0.6,
                 panel_score_threshold: float = 0.7,
                 document_score_threshold: float = 0.75):
        """
        Initialize scorer with thresholds
        
        Args:
            value_parse_threshold: Minimum score for value parsing
            unit_validity_threshold: Minimum score for unit validity
            ref_range_threshold: Minimum score for reference range
            panel_score_threshold: Minimum panel score to avoid review
            document_score_threshold: Minimum document score to avoid review
        """
        self.value_parse_threshold = value_parse_threshold
        self.unit_validity_threshold = unit_validity_threshold
        self.ref_range_threshold = ref_range_threshold
        self.panel_score_threshold = panel_score_threshold
        self.document_score_threshold = document_score_threshold
        
        # Store label order for probability normalization
        self.label_order = DEFAULT_ROLE_LABELS
        
        # Unit whitelists by category
        self.valid_units = self._build_unit_whitelist()
        # Flattened lowercase set for quick membership
        self._all_units_lower = {u.lower() for cat in self.valid_units.values() for u in cat}
        
        # Value parsing patterns
        self.numeric_patterns = {
            'integer': re.compile(r'^\d+$'),
            'decimal': re.compile(r'^\d+\.\d+$'),
            'scientific': re.compile(r'^\d+\.?\d*[eE][+-]?\d+$'),
            'range': re.compile(r'^\d+\.?\d*\s*-\s*\d+\.?\d*$'),
            'less_than': re.compile(r'^<\s*\d+\.?\d*$'),
            'greater_than': re.compile(r'^>\s*\d+\.?\d*$'),
            'approximate': re.compile(r'^~?\s*\d+\.?\d*$')
        }
        
        # Reference range patterns
        self.ref_range_patterns = {
            'numeric_range': re.compile(r'^\d+\.?\d*\s*-\s*\d+\.?\d*$'),
            'less_than': re.compile(r'^<\s*\d+\.?\d*$'),
            'greater_than': re.compile(r'^>\s*\d+\.?\d*$'),
            'normal_abnormal': re.compile(r'^(NORMAL|ABNORMAL)$', re.IGNORECASE),
            'pos_neg': re.compile(r'^(POSITIVE|NEGATIVE)$', re.IGNORECASE),
            'qualitative': re.compile(r'^(HIGH|LOW|CRITICAL|BORDERLINE)$', re.IGNORECASE)
        }
        # Simple entire-cell reference range regex (for scoring lower bound)
        self._simple_ref_range_re = re.compile(r'^\s*[<>]?\d+(\.\d+)?\s*[-–]\s*[<>]?\d+(\.\d+)?\s*$', re.UNICODE)
    
    def _build_unit_whitelist(self) -> Dict[str, Set[str]]:
        """Build comprehensive unit whitelist organized by category"""
        return {
            'concentration': {
                'mg/dL', 'g/dL', 'g/L', 'mg/L', 'mcg/dL', 'mcg/L', 'ng/mL', 'pg/mL',
                'mmol/L', 'umol/L', 'nmol/L', 'pmol/L', 'mEq/L', 'IU/L', 'U/L',
                'mU/L', 'uU/mL', 'mIU/L'
            },
            'blood_count': {
                'K/uL', 'M/uL', 'cells/uL', '10^3/uL', '10^6/uL', '10^9/L',
                'x10^3/uL', 'x10^6/uL', 'thou/uL', 'mill/uL'
            },
            'percentage': {
                '%', 'percent'
            },
            'time': {
                'sec', 'seconds', 'min', 'minutes', 'hr', 'hours', 'day', 'days'
            },
            'pressure': {
                'mmHg', 'cmH2O', 'kPa'
            },
            'temperature': {
                'C', '°C', 'F', '°F'
            },
            'volume': {
                'mL', 'L', 'uL', 'dL'
            },
            'mass': {
                'g', 'kg', 'mg', 'ug', 'ng', 'pg'
            },
            'activity': {
                'IU', 'U', 'mU', 'uU', 'KU', 'MU'
            },
            'dimensionless': {
                'ratio', 'index', 'score', 'units'
            }
        }
    
    def score_test_row(self, test_row: TestRow, classifier_probabilities=None) -> FieldConfidence:
        """
        Score individual test row fields
        
        Each field is scored independently:
        - VALUE: Numeric parse success (0.0-1.0)
        - UNIT: Unit validity against whitelist (0.0-1.0) 
        - REF_RANGE: Reference range well-formedness (0.0-1.0)
        - TEST_NAME: Name clarity and medical terminology (0.0-1.0)
        - CLASSIFIER: Role classification probability (0.0-1.0)
        
        Args:
            test_row: TestRow object to score
            classifier_probabilities: Optional dict/list with classifier probabilities
            
        Returns:
            FieldConfidence with individual field scores
        """
        confidence = FieldConfidence()
        
        # Score value parsing
        confidence.value_parse = self._score_value_parse(test_row.result_value)
        
        # Score unit validity
        confidence.unit_validity = self._score_unit_validity(test_row.units)
        # Boost if unit was found via repair and is valid
        try:
            if getattr(test_row, 'unit_repaired', False) and test_row.units and str(test_row.units).lower() in self._all_units_lower:
                confidence.unit_validity = min(1.0, confidence.unit_validity + 0.3)
        except Exception:
            pass
        
        # Score reference range
        confidence.reference_range = self._score_reference_range(test_row.reference_range)
        # Ensure a reasonable floor for simple numeric ranges
        try:
            rr = (test_row.reference_range or '').strip()
            if rr and self._simple_ref_range_re.match(rr):
                confidence.reference_range = max(confidence.reference_range, 0.5)
        except Exception:
            pass
        
        # Score test name clarity
        confidence.test_name_clarity = self._score_test_name_clarity(test_row.test_name)
        
        # Set classifier probability using robust lookup
        line_no = getattr(test_row, 'line_number', None)
        if line_no is None:
            line_no = getattr(test_row, 'line_idx', None)
        p = _lookup_line_proba(classifier_probabilities, line_no, "TEST_ROW")
        if p is not None:
            confidence.classifier_proba = float(p)
        
        # Calculate overall confidence
        weights = {
            'value_parse': 0.3,
            'unit_validity': 0.25,
            'reference_range': 0.2,
            'test_name_clarity': 0.15,
            'classifier_proba': 0.1
        }
        
        confidence.overall = (
            confidence.value_parse * weights['value_parse'] +
            confidence.unit_validity * weights['unit_validity'] +
            confidence.reference_range * weights['reference_range'] +
            confidence.test_name_clarity * weights['test_name_clarity'] +
            confidence.classifier_proba * weights['classifier_proba']
        )
        
        # NEW: Small bonuses for enhanced fields (additive, not in main scoring)
        bonus = 0.0
        
        # Codes bonus: presence of LOINC/CPT codes adds small bonus
        if hasattr(test_row, 'codes') and test_row.codes:
            if test_row.codes.get('loinc') or test_row.codes.get('cpt'):
                bonus += 0.02  # Small bonus for having codes
        
        # Methodology bonus: presence of methodology adds small bonus
        if hasattr(test_row, 'methodology') and test_row.methodology:
            if len(test_row.methodology.strip()) > 3:
                bonus += 0.01  # Small bonus for methodology
        
        # Comments bonus: no penalty for missing comments, small bonus if present
        if hasattr(test_row, 'comments') and test_row.comments:
            if len(test_row.comments.strip()) > 5:
                bonus += 0.01  # Small bonus for comments
        
        # Observation time bonus
        if hasattr(test_row, 'observed_at') and test_row.observed_at:
            bonus += 0.01  # Small bonus for time info
        
        # Apply bonus (cap at 1.0)
        confidence.overall = min(1.0, confidence.overall + bonus)
        
        return confidence
    
    def _score_value_parse(self, value: Optional[str]) -> float:
        """Score the success of numeric value parsing"""
        if not value or not value.strip():
            return 0.0
        
        value = value.strip()
        
        # Perfect score for clean numeric patterns
        for pattern_name, pattern in self.numeric_patterns.items():
            if pattern.match(value):
                if pattern_name in ['integer', 'decimal']:
                    return 1.0
                elif pattern_name in ['scientific', 'range']:
                    return 0.9
                elif pattern_name in ['less_than', 'greater_than', 'approximate']:
                    return 0.8
        
        # Partial score for text values that might be valid
        text_patterns = {
            'NEGATIVE': 0.9,
            'POSITIVE': 0.9,
            'NORMAL': 0.8,
            'ABNORMAL': 0.8,
            'HIGH': 0.7,
            'LOW': 0.7,
            'CRITICAL': 0.7,
            'DETECTED': 0.6,
            'NOT DETECTED': 0.6
        }
        
        value_upper = value.upper()
        for pattern, score in text_patterns.items():
            if pattern in value_upper:
                return score
        
        # Check if contains any numbers (partial parsing success)
        if re.search(r'\d', value):
            return 0.4
        
        # No recognizable value pattern
        return 0.1
    
    def _score_unit_validity(self, units: Optional[str]) -> float:
        """Score unit validity against whitelist"""
        if not units or not units.strip():
            return 0.0
        
        units = units.strip()
        
        # Check against whitelist
        for category, unit_set in self.valid_units.items():
            if units in unit_set:
                return 1.0
        
        # Check for common variations
        units_lower = units.lower()
        units_normalized = units.replace('/', ' per ').replace('^', '').replace('*', 'x')
        
        for category, unit_set in self.valid_units.items():
            for valid_unit in unit_set:
                if (units_lower == valid_unit.lower() or 
                    units_normalized.lower() == valid_unit.lower().replace('/', ' per ').replace('^', '')):
                    return 0.9
        
        # Partial matches for common patterns
        if re.match(r'^[a-zA-Z]+/[a-zA-Z]+$', units):  # Something/Something format
            return 0.6
        elif re.match(r'^[a-zA-Z%]+$', units):  # Letters or % only
            return 0.4
        elif re.search(r'\d', units):  # Contains numbers (might be valid)
            return 0.3
        
        return 0.1
    
    def _score_reference_range(self, ref_range: Optional[str]) -> float:
        """Score reference range well-formedness"""
        if not ref_range or not ref_range.strip():
            return 0.0
        
        ref_range = ref_range.strip()
        
        # Check against reference range patterns
        for pattern_name, pattern in self.ref_range_patterns.items():
            if pattern.match(ref_range):
                if pattern_name == 'numeric_range':
                    return 1.0
                elif pattern_name in ['less_than', 'greater_than']:
                    return 0.9
                elif pattern_name in ['normal_abnormal', 'pos_neg']:
                    return 0.8
                elif pattern_name == 'qualitative':
                    return 0.7
        
        # Check for multiple ranges or complex patterns
        if re.search(r'\d+\.?\d*\s*-\s*\d+\.?\d*', ref_range):
            return 0.8
        elif re.search(r'[<>]\s*\d+\.?\d*', ref_range):
            return 0.7
        elif re.search(r'\d+\.?\d*', ref_range):  # Contains numbers
            return 0.5
        
        # Text-only ranges
        text_indicators = ['normal', 'abnormal', 'high', 'low', 'positive', 'negative', 'detected']
        if any(indicator in ref_range.lower() for indicator in text_indicators):
            return 0.4
        
        return 0.1
    
    def _score_test_name_clarity(self, test_name: Optional[str]) -> float:
        """Score test name clarity and completeness"""
        if not test_name or not test_name.strip():
            return 0.0
        
        test_name = test_name.strip()
        
        # Length-based scoring
        length_score = min(len(test_name) / 20.0, 1.0)  # Optimal around 20 chars
        if len(test_name) < 3:
            length_score *= 0.5
        
        # Content quality indicators
        quality_score = 0.5  # Base score
        
        # Bonus for medical terminology
        medical_terms = [
            'glucose', 'sodium', 'potassium', 'chloride', 'cholesterol', 'triglyceride',
            'hemoglobin', 'hematocrit', 'platelet', 'white', 'red', 'cell', 'count',
            'protein', 'albumin', 'globulin', 'bilirubin', 'creatinine', 'urea',
            'enzyme', 'hormone', 'vitamin', 'mineral', 'electrolyte', 'lipid'
        ]
        
        test_lower = test_name.lower()
        medical_matches = sum(1 for term in medical_terms if term in test_lower)
        quality_score += min(medical_matches * 0.1, 0.3)
        
        # Penalty for unclear patterns
        if re.search(r'[^\w\s\-/()]', test_name):  # Special chars
            quality_score -= 0.1
        if test_name.isupper() and len(test_name) > 10:  # ALL CAPS
            quality_score -= 0.05
        if re.search(r'\d{3,}', test_name):  # Large numbers (codes)
            quality_score -= 0.1
        
        # Bonus for proper capitalization
        if test_name.istitle() or (test_name[0].isupper() and not test_name.isupper()):
            quality_score += 0.05
        
        return min(length_score * quality_score, 1.0)
    
    def score_panel(self, panel: Panel, classifier_probabilities: Optional[Dict[int, float]] = None) -> PanelScore:
        """
        Score an entire panel
        
        Args:
            panel: Panel object to score
            classifier_probabilities: Dict mapping line numbers to classifier probabilities
            
        Returns:
            PanelScore with panel-level metrics
        """
        classifier_probabilities = classifier_probabilities or {}
        
        # Score individual test rows
        field_confidences = []
        review_reasons = []
        
        for test_row in panel.test_rows:
            confidence = self.score_test_row(test_row, classifier_probabilities)
            field_confidences.append(confidence)
            
            # Update test row with confidence scores
            test_row.confidence = confidence.overall
        
        # Calculate panel metrics
        if field_confidences:
            avg_field_confidence = mean(conf.overall for conf in field_confidences)
            
            # Check for critical field failures
            low_value_parse = sum(1 for conf in field_confidences 
                                 if conf.value_parse < self.value_parse_threshold)
            low_unit_validity = sum(1 for conf in field_confidences 
                                  if conf.unit_validity < self.unit_validity_threshold)
            low_ref_range = sum(1 for conf in field_confidences 
                               if conf.reference_range < self.ref_range_threshold)
            
            if low_value_parse > len(field_confidences) * 0.3:
                review_reasons.append(f"Poor value parsing in {low_value_parse}/{len(field_confidences)} tests")
            if low_unit_validity > len(field_confidences) * 0.4:
                review_reasons.append(f"Invalid units in {low_unit_validity}/{len(field_confidences)} tests")
            if low_ref_range > len(field_confidences) * 0.5:
                review_reasons.append(f"Malformed reference ranges in {low_ref_range}/{len(field_confidences)} tests")
        else:
            avg_field_confidence = 0.0
            review_reasons.append("No test rows found in panel")
        
        # Panel continuity and coherence scores
        continuity_score = panel.continuity_score
        coherence_score = panel.calculate_coherence_score()
        
        if continuity_score < 0.5:
            review_reasons.append(f"Low continuity score: {continuity_score:.2f}")
        if coherence_score < 0.6:
            review_reasons.append(f"Low coherence score: {coherence_score:.2f}")
        
        # Overall panel score
        overall_score = (
            avg_field_confidence * 0.5 +
            continuity_score * 0.25 +
            coherence_score * 0.25
        )
        
        # NEW: Small bonuses for enhanced panel fields
        panel_bonus = 0.0
        
        # Panel code bonus
        if hasattr(panel, 'panel_code') and panel.panel_code:
            if len(panel.panel_code.strip()) > 2:
                panel_bonus += 0.01  # Small bonus for panel codes
        
        # Panel comments bonus
        if hasattr(panel, 'comments') and panel.comments:
            if len(panel.comments.strip()) > 10:
                panel_bonus += 0.01  # Small bonus for meaningful comments
        
        # Apply panel bonus (cap at 1.0)
        overall_score = min(1.0, overall_score + panel_bonus)
        
        # Determine if review is needed
        needs_review = (overall_score < self.panel_score_threshold or 
                       len(review_reasons) > 0)
        
        return PanelScore(
            continuity_score=continuity_score,
            coherence_score=coherence_score,
            avg_field_confidence=avg_field_confidence,
            test_count=len(panel.test_rows),
            overall_score=overall_score,
            needs_review=needs_review,
            review_reasons=review_reasons
        )
    
    def score_document(self, panels: List[Panel], 
                      classifier_probabilities: Optional[Dict[int, float]] = None) -> Tuple[DocumentScore, List[PanelScore]]:
        """
        Score entire document
        
        Args:
            panels: List of Panel objects
            classifier_probabilities: Dict mapping line numbers to probabilities
            
        Returns:
            Tuple of (DocumentScore, List of PanelScore)
        """
        if not panels:
            return DocumentScore(
                total_panels=0,
                total_tests=0,
                avg_panel_score=0.0,
                confidence_distribution={},
                overall_score=0.0,
                needs_review=True,
                review_reasons=["No panels found"],
                high_confidence_panels=0,
                low_confidence_panels=0
            ), []
        
        # Score individual panels
        panel_scores = []
        for panel in panels:
            panel_score = self.score_panel(panel, classifier_probabilities)
            panel_scores.append(panel_score)
        
        # Document-level metrics
        total_tests = sum(len(panel.test_rows) for panel in panels)
        avg_panel_score = mean(score.overall_score for score in panel_scores)
        
        # Confidence distribution
        all_confidences = []
        for panel in panels:
            for test_row in panel.test_rows:
                if hasattr(test_row, 'confidence'):
                    all_confidences.append(test_row.confidence)
        
        confidence_distribution = {}
        if all_confidences:
            confidence_distribution = {
                'mean': mean(all_confidences),
                'median': median(all_confidences),
                'min': min(all_confidences),
                'max': max(all_confidences),
                'std': math.sqrt(sum((x - mean(all_confidences))**2 for x in all_confidences) / len(all_confidences))
            }
        
        # Panel quality classification
        high_confidence_panels = sum(1 for score in panel_scores if score.overall_score >= 0.8)
        low_confidence_panels = sum(1 for score in panel_scores if score.overall_score < 0.5)
        
        # Document review reasons
        review_reasons = []
        panels_needing_review = sum(1 for score in panel_scores if score.needs_review)
        
        if panels_needing_review > len(panels) * 0.3:
            review_reasons.append(f"{panels_needing_review}/{len(panels)} panels need review")
        if avg_panel_score < 0.6:
            review_reasons.append(f"Low average panel score: {avg_panel_score:.2f}")
        if low_confidence_panels > 0:
            review_reasons.append(f"{low_confidence_panels} panels have very low confidence")
        if total_tests < 5:
            review_reasons.append(f"Very few tests found: {total_tests}")
        
        # Overall document score
        panel_score_weight = 0.6
        distribution_weight = 0.3
        structure_weight = 0.1
        
        distribution_score = confidence_distribution.get('mean', 0.0) if confidence_distribution else 0.0
        structure_score = min(len(panels) / 5.0, 1.0)  # Reward having multiple panels
        
        overall_score = (
            avg_panel_score * panel_score_weight +
            distribution_score * distribution_weight +
            structure_score * structure_weight
        )
        
        needs_review = (overall_score < self.document_score_threshold or 
                       len(review_reasons) > 0)
        
        document_score = DocumentScore(
            total_panels=len(panels),
            total_tests=total_tests,
            avg_panel_score=avg_panel_score,
            confidence_distribution=confidence_distribution,
            overall_score=overall_score,
            needs_review=needs_review,
            review_reasons=review_reasons,
            high_confidence_panels=high_confidence_panels,
            low_confidence_panels=low_confidence_panels
        )
        
        return document_score, panel_scores
