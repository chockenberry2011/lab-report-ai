"""
Rule-based fallback splitter for TEST_ROW lines

Provides heuristic parsing when NER model is unavailable or low-confidence.
"""

import re
from typing import List, Dict, Tuple, Optional, NamedTuple
from dataclasses import dataclass

# Common test name patterns
TEST_NAME_PATTERNS = [
    # Standard test names
    r'^([A-Za-z][A-Za-z0-9\s\-,\(\)]+?)\s*(?=\d|<|>|\*)',  # Name before number/flag
    r'^([A-Za-z][A-Za-z\s\-,\(\)]+?)\s+(?=\d)',  # Name before digits
    r'^([A-Za-z]+(?:\s+[A-Za-z]+)*)\s*(?=\d)',   # Multiple words before digits
]

# Value patterns (numbers, ranges, qualitative results)
VALUE_PATTERNS = [
    r'(\d+\.?\d*)',           # Basic numbers (123, 12.5)
    r'(<\s*\d+\.?\d*)',       # Less than values (<5)
    r'(>\s*\d+\.?\d*)',       # Greater than values (>100)
    r'(\d+\.?\d*\s*-\s*\d+\.?\d*)',  # Ranges (1.0-2.0)
    r'(NEGATIVE|POSITIVE|NEG|POS)',   # Qualitative
    r'(NORMAL|ABNORMAL|HIGH|LOW)',    # Status values
    r'(DETECTED|NOT\s+DETECTED)',     # Detection results
]

# Unit patterns
UNIT_PATTERNS = [
    r'\b(mg/dL|g/dL|mmol/L|mEq/L|U/L|IU/L|ng/mL|pg/mL|μg/dL|mcg/dL)',
    r'\b(K/uL|M/uL|cells/uL|/uL)',
    r'\b(mm/hr|mmHg|bpm|%|ratio)',
    r'\b(mg|g|mL|L|units|IU)',
]

# Reference range patterns
REF_RANGE_PATTERNS = [
    r'(\d+\.?\d*\s*-\s*\d+\.?\d*)',           # 1.0-5.0
    r'(<\s*\d+\.?\d*)',                       # <5
    r'(>\s*\d+\.?\d*)',                       # >100
    r'(\d+\.?\d*\s*-\s*\d+\.?\d*\s+[A-Za-z/]+)',  # With units
    r'(NEGATIVE|NOT\s+DETECTED)',             # Qualitative ranges
]

# Flag patterns
FLAG_PATTERNS = [
    r'(\*+)',                    # Asterisks
    r'\b(HIGH|LOW|H|L)\b',      # Status flags
    r'\b(CRITICAL|PANIC)\b',     # Severity flags
    r'\b(ABNORMAL|ABN)\b',       # Abnormal flags
    r'(\!+)',                    # Exclamation marks
]


@dataclass
class ParsedComponent:
    """A parsed component of a test row"""
    text: str
    label: str
    start: int
    end: int
    confidence: float = 1.0


class RuleBasedSplitter:
    """Rule-based parser for TEST_ROW lines"""
    
    def __init__(self):
        self.test_name_patterns = [re.compile(p, re.IGNORECASE) for p in TEST_NAME_PATTERNS]
        self.value_patterns = [re.compile(p, re.IGNORECASE) for p in VALUE_PATTERNS]
        self.unit_patterns = [re.compile(p, re.IGNORECASE) for p in UNIT_PATTERNS]
        self.ref_range_patterns = [re.compile(p, re.IGNORECASE) for p in REF_RANGE_PATTERNS]
        self.flag_patterns = [re.compile(p, re.IGNORECASE) for p in FLAG_PATTERNS]
    
    def parse(self, text: str) -> List[ParsedComponent]:
        """Parse a TEST_ROW line into components"""
        text = text.strip()
        components = []
        used_positions = set()
        
        # 1. Find test name (usually at beginning)
        test_name = self._find_test_name(text, used_positions)
        if test_name:
            components.append(test_name)
            used_positions.update(range(test_name.start, test_name.end))
        
        # 2. Find flags (often marked with * or keywords)
        flags = self._find_flags(text, used_positions)
        for flag in flags:
            components.append(flag)
            used_positions.update(range(flag.start, flag.end))
        
        # 3. Find values (numbers, qualitative results)
        values = self._find_values(text, used_positions)
        for value in values:
            components.append(value)
            used_positions.update(range(value.start, value.end))
        
        # 4. Find units (adjacent to values)
        units = self._find_units(text, used_positions)
        for unit in units:
            components.append(unit)
            used_positions.update(range(unit.start, unit.end))
        
        # 5. Find reference ranges (patterns like 1.0-5.0)
        ref_ranges = self._find_reference_ranges(text, used_positions)
        for ref_range in ref_ranges:
            components.append(ref_range)
            used_positions.update(range(ref_range.start, ref_range.end))
        
        # 6. Mark remaining significant text as OTHER/O
        remaining = self._mark_remaining_text(text, used_positions)
        components.extend(remaining)
        
        # Sort by position
        components.sort(key=lambda x: x.start)
        
        return components
    
    def _find_test_name(self, text: str, used_positions: set) -> Optional[ParsedComponent]:
        """Find test name (usually at the beginning)"""
        for pattern in self.test_name_patterns:
            match = pattern.search(text)
            if match and not self._overlaps(match.span(), used_positions):
                return ParsedComponent(
                    text=match.group(1).strip(),
                    label='TEST_NAME',
                    start=match.start(1),
                    end=match.end(1),
                    confidence=0.8
                )
        
        # Fallback: take first few words if they look like a test name
        words = text.split()
        if len(words) >= 2 and words[0].isalpha():
            # Check if first 1-3 words could be a test name
            for i in range(min(3, len(words))):
                candidate = ' '.join(words[:i+1])
                end_pos = text.find(candidate) + len(candidate)
                
                if not self._overlaps((0, end_pos), used_positions):
                    # Check if followed by number or typical value
                    remaining = text[end_pos:].strip()
                    if remaining and (remaining[0].isdigit() or remaining.startswith('<') or remaining.startswith('>')):
                        return ParsedComponent(
                            text=candidate,
                            label='TEST_NAME',
                            start=0,
                            end=end_pos,
                            confidence=0.6
                        )
        
        return None
    
    def _find_values(self, text: str, used_positions: set) -> List[ParsedComponent]:
        """Find numerical and qualitative values"""
        values = []
        
        for pattern in self.value_patterns:
            for match in pattern.finditer(text):
                if not self._overlaps(match.span(), used_positions):
                    values.append(ParsedComponent(
                        text=match.group().strip(),
                        label='VALUE',
                        start=match.start(),
                        end=match.end(),
                        confidence=0.9
                    ))
        
        return values
    
    def _find_units(self, text: str, used_positions: set) -> List[ParsedComponent]:
        """Find measurement units"""
        units = []
        
        for pattern in self.unit_patterns:
            for match in pattern.finditer(text):
                if not self._overlaps(match.span(), used_positions):
                    units.append(ParsedComponent(
                        text=match.group().strip(),
                        label='UNIT',
                        start=match.start(),
                        end=match.end(),
                        confidence=0.85
                    ))
        
        return units
    
    def _find_reference_ranges(self, text: str, used_positions: set) -> List[ParsedComponent]:
        """Find reference ranges"""
        ranges = []
        
        for pattern in self.ref_range_patterns:
            for match in pattern.finditer(text):
                if not self._overlaps(match.span(), used_positions):
                    # Avoid marking single values that are already tagged as VALUE
                    match_text = match.group().strip()
                    
                    # Must be a range (contains -, <, > or qualitative)
                    if '-' in match_text or '<' in match_text or '>' in match_text or any(
                        qual in match_text.upper() for qual in ['NEGATIVE', 'POSITIVE', 'NOT DETECTED']
                    ):
                        ranges.append(ParsedComponent(
                            text=match_text,
                            label='REF_RANGE',
                            start=match.start(),
                            end=match.end(),
                            confidence=0.8
                        ))
        
        return ranges
    
    def _find_flags(self, text: str, used_positions: set) -> List[ParsedComponent]:
        """Find abnormal flags"""
        flags = []
        
        for pattern in self.flag_patterns:
            for match in pattern.finditer(text):
                if not self._overlaps(match.span(), used_positions):
                    flags.append(ParsedComponent(
                        text=match.group().strip(),
                        label='FLAG',
                        start=match.start(),
                        end=match.end(),
                        confidence=0.9
                    ))
        
        return flags
    
    def _mark_remaining_text(self, text: str, used_positions: set) -> List[ParsedComponent]:
        """Mark remaining text as OTHER"""
        remaining = []
        current_start = None
        
        for i, char in enumerate(text):
            if i not in used_positions:
                if current_start is None:
                    current_start = i
            else:
                if current_start is not None:
                    # End of unused sequence
                    remaining_text = text[current_start:i].strip()
                    if remaining_text and not remaining_text.isspace():
                        remaining.append(ParsedComponent(
                            text=remaining_text,
                            label='O',
                            start=current_start,
                            end=i,
                            confidence=0.5
                        ))
                    current_start = None
        
        # Handle remaining text at end
        if current_start is not None:
            remaining_text = text[current_start:].strip()
            if remaining_text and not remaining_text.isspace():
                remaining.append(ParsedComponent(
                    text=remaining_text,
                    label='O',
                    start=current_start,
                    end=len(text),
                    confidence=0.5
                ))
        
        return remaining
    
    def _overlaps(self, span: Tuple[int, int], used_positions: set) -> bool:
        """Check if span overlaps with used positions"""
        start, end = span
        return any(pos in used_positions for pos in range(start, end))
    
    def parse_to_bio_labels(self, text: str) -> List[str]:
        """Parse text and return BIO labels for each token"""
        words = text.split()
        components = self.parse(text)
        
        # Create word-level labels
        labels = ['O'] * len(words)
        word_positions = []
        
        # Calculate word positions
        current_pos = 0
        for i, word in enumerate(words):
            start = text.find(word, current_pos)
            end = start + len(word)
            word_positions.append((start, end))
            current_pos = end
        
        # Assign labels based on components
        for component in components:
            if component.label == 'O':
                continue
            
            # Find overlapping words
            for i, (word_start, word_end) in enumerate(word_positions):
                if self._spans_overlap((component.start, component.end), (word_start, word_end)):
                    if labels[i] == 'O':  # Only assign if not already assigned
                        # First word gets B-, subsequent get I-
                        if any(labels[j] == f'B-{component.label}' for j in range(i)):
                            # Already have a B- for this label, use I-
                            labels[i] = f'I-{component.label}'
                        else:
                            # First occurrence, use B-
                            labels[i] = f'B-{component.label}'
                            # Mark subsequent overlapping words as I-
                            for j in range(i + 1, len(word_positions)):
                                word_start_j, word_end_j = word_positions[j]
                                if self._spans_overlap((component.start, component.end), (word_start_j, word_end_j)):
                                    if labels[j] == 'O':
                                        labels[j] = f'I-{component.label}'
        
        return labels
    
    def _spans_overlap(self, span1: Tuple[int, int], span2: Tuple[int, int]) -> bool:
        """Check if two spans overlap"""
        start1, end1 = span1
        start2, end2 = span2
        return not (end1 <= start2 or end2 <= start1)


def test_rule_splitter():
    """Test the rule-based splitter with common patterns"""
    splitter = RuleBasedSplitter()
    
    test_cases = [
        "Glucose                    95        mg/dL       70-100",
        "Hemoglobin A1c             7.2       %           <7.0",
        "White Blood Cell Count     12.5 *    K/uL        4.0-11.0",
        "Cholesterol, Total         220 H     mg/dL       <200",
        "Creatinine                 1.8 *     mg/dL       0.7-1.3",
        "Thyroid Stimulating Hormone 2.5      mIU/L       0.4-4.0",
        "Hepatitis B Surface Antigen NEGATIVE             NEGATIVE",
    ]
    
    print("Testing Rule-Based Splitter:")
    print("=" * 50)
    
    for text in test_cases:
        print(f"\nText: {text}")
        components = splitter.parse(text)
        
        print("Components:")
        for comp in components:
            print(f"  {comp.label}: '{comp.text}' ({comp.start}-{comp.end}, conf={comp.confidence:.2f})")
        
        labels = splitter.parse_to_bio_labels(text)
        words = text.split()
        print("BIO Labels:")
        for word, label in zip(words, labels):
            print(f"  {word} -> {label}")


if __name__ == '__main__':
    test_rule_splitter()