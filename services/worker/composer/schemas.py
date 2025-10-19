"""
Data schemas for the composer module
"""

from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
from datetime import datetime
import json


@dataclass
class TestRow:
    """Represents a single test result row"""
    text: str
    page: int
    line_number: int
    y_norm: float
    test_name: Optional[str] = None
    result_value: Optional[str] = None
    units: Optional[str] = None
    reference_range: Optional[str] = None
    flag: Optional[str] = None
    confidence: float = 1.0
    field_confidences: Optional[Dict[str, float]] = None
    repaired_split: bool = False  # True if this row was repaired by merging split fields
    # NEW: Enhanced test row fields
    codes: Optional[Dict[str, str]] = None  # {'loinc': 'xxx', 'cpt': 'yyy'}
    methodology: Optional[str] = None
    comments: Optional[str] = None
    observed_at: Optional[str] = None  # Observation time
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        # Include field confidences if available
        if self.field_confidences:
            result['field_confidences'] = self.field_confidences
        return result


@dataclass
class Panel:
    """Represents a lab panel with associated test rows"""
    id: str
    name: str
    started_at_page: int
    started_at_line: int
    continuity_score: float
    open: bool
    test_rows: List[TestRow]
    
    # Panel metadata
    panel_type: Optional[str] = None
    collected_date: Optional[str] = None
    reference_lab: Optional[str] = None
    # NEW: Enhanced panel fields
    panel_code: Optional[str] = None  # LOINC/CPT code for the panel
    comments: Optional[str] = None  # Panel-level comments and footnotes
    
    # Scoring information
    panel_score: Optional[float] = None
    needs_review: bool = False
    review_reasons: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.review_reasons is None:
            self.review_reasons = []

    def test_count(self) -> int:
        """Safe accessor for number of tests without breaking JSON serialization."""
        try:
            return len(self.test_rows or [])
        except Exception:
            # Extremely defensive: fallback if structure is unexpected
            return 0
    
    def add_test_row(self, test_row: TestRow):
        """Add a test row to this panel"""
        self.test_rows.append(test_row)
        
    def close_panel(self):
        """Mark panel as closed"""
        self.open = False
        
    def calculate_coherence_score(self) -> float:
        """Calculate coherence score based on test patterns"""
        if not self.test_rows:
            return 0.0
            
        # Simple heuristic: more test rows with similar patterns = higher coherence
        has_units = sum(1 for row in self.test_rows if row.units)
        has_ranges = sum(1 for row in self.test_rows if row.reference_range)
        
        coherence = (has_units + has_ranges) / (len(self.test_rows) * 2)
        return min(coherence, 1.0)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = {
            'id': self.id,
            'name': self.name,
            'started_at_page': self.started_at_page,
            'started_at_line': self.started_at_line,
            'continuity_score': self.continuity_score,
            'open': self.open,
            'panel_type': self.panel_type,
            'collected_date': self.collected_date,
            'reference_lab': self.reference_lab,
            'test_count': len(self.test_rows),
            'coherence_score': self.calculate_coherence_score(),
            'panel_score': self.panel_score,
            'needs_review': self.needs_review,
            'review_reasons': self.review_reasons or [],
            'test_rows': [row.to_dict() for row in self.test_rows]
        }
        # NEW: Include enhanced panel fields if present
        if self.panel_code:
            result['panel_code'] = self.panel_code
        if self.comments:
            result['comments'] = self.comments
        return result


@dataclass
class ComposerResult:
    """Result of the composition process"""
    panels: List[Panel]
    total_lines_processed: int
    total_test_rows: int
    page_breaks_handled: int
    repairs_made: int
    processing_time: float
    
    # Metadata
    source_document: Optional[str] = None
    processed_at: Optional[str] = None
    
    # Document-level scoring
    document_score: Optional[float] = None
    needs_review: bool = False
    review_reasons: Optional[List[str]] = None
    confidence_distribution: Optional[Dict[str, float]] = None
    
    # Debug information
    panels_seen: Optional[List[Dict]] = None
    
    def __post_init__(self):
        if self.processed_at is None:
            self.processed_at = datetime.now().isoformat()
        if self.review_reasons is None:
            self.review_reasons = []
    
    def to_ehr_json(self) -> str:
        """Convert to EHR-ready JSON format"""
        ehr_data = {
            'document_info': {
                'source': self.source_document,
                'processed_at': self.processed_at,
                'total_panels': len(self.panels),
                'total_tests': self.total_test_rows,
                'document_score': self.document_score,
                'needs_review': self.needs_review,
                'review_reasons': self.review_reasons or [],
                'confidence_distribution': self.confidence_distribution,
                'processing_stats': {
                    'lines_processed': self.total_lines_processed,
                    'page_breaks_handled': self.page_breaks_handled,
                    'repairs_made': self.repairs_made,
                    'processing_time_seconds': self.processing_time,
                    'panels_seen': self.panels_seen or []
                }
            },
            'lab_panels': [panel.to_dict() for panel in self.panels]
        }
        
        return json.dumps(ehr_data, indent=2, ensure_ascii=False)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get processing summary"""
        return {
            'total_panels': len(self.panels),
            'total_test_rows': self.total_test_rows,
            'avg_tests_per_panel': self.total_test_rows / len(self.panels) if self.panels else 0,
            'processing_time': self.processing_time,
            'efficiency_score': self.total_test_rows / self.processing_time if self.processing_time > 0 else 0
        }
