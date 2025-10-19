"""
Scoped header extractors for medical documents

Extract specific fields from HEADER_PATIENT and HEADER_SPECIMEN lines.
"""

import re
import json
from datetime import datetime, date
from typing import Dict, List, Optional, Union, Any, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import warnings


@dataclass
class PatientInfo:
    """Extracted patient information"""
    patient_name: Optional[str] = None
    sex: Optional[str] = None
    raw_text: str = ""
    confidence: float = 0.0
    extraction_method: str = "pattern"


@dataclass
class SpecimenInfo:
    """Extracted specimen information"""
    specimen_number: Optional[str] = None
    date_collected: Optional[str] = None
    date_received: Optional[str] = None
    date_entered: Optional[str] = None
    date_reported: Optional[str] = None
    raw_text: str = ""
    confidence: float = 0.0
    extraction_method: str = "pattern"


class PatientExtractor:
    """Extract patient information from HEADER_PATIENT lines"""
    
    def __init__(self):
        # Name patterns - handle various formats
        self.name_patterns = [
            # "Patient: Last, First" or "Name: Last, First"
            r'(?:patient|name)\s*:\s*([A-Za-z\-\'\s]+,\s*[A-Za-z\-\'\s]+)',
            
            # "Patient Name: First Last" 
            r'patient\s+name\s*:\s*([A-Za-z\-\'\s]+)',
            
            # Just "Last, First" at start
            r'^([A-Za-z\-\'\s]+,\s*[A-Za-z\-\'\s]+)',
            
            # "First Last" pattern (more risky, lower confidence)
            r'^([A-Z][a-z]+\s+[A-Z][a-z\-\']+(?:\s+[A-Z][a-z\-\']+)?)',
            
            # Handle titles: "Mr. Last, First" or "Ms. Smith, Jane"
            r'(?:mr|ms|mrs|dr|prof)\.?\s+([A-Za-z\-\'\s]+,\s*[A-Za-z\-\'\s]+)',
        ]
        
        # Sex/Gender patterns
        self.sex_patterns = [
            # Explicit labels
            r'(?:sex|gender)\s*:\s*(male|female|m|f|man|woman)',
            
            # Standalone in parentheses
            r'\(\s*(male|female|m|f)\s*\)',
            
            # After name
            r'[A-Za-z\-\'\s]+,\s*[A-Za-z\-\'\s]+\s+(male|female|m|f)',
            
            # Common abbreviations
            r'\b(male|female|m|f)\b(?:\s|$)',
        ]
        
        # Sex normalization
        self.sex_mapping = {
            'male': 'M', 'm': 'M', 'man': 'M',
            'female': 'F', 'f': 'F', 'woman': 'F'
        }
        
        # Compile patterns
        self.compiled_name_patterns = [re.compile(p, re.IGNORECASE) for p in self.name_patterns]
        self.compiled_sex_patterns = [re.compile(p, re.IGNORECASE) for p in self.sex_patterns]
    
    def extract(self, text: str) -> PatientInfo:
        """Extract patient information from header text"""
        text = text.strip()
        
        # Initialize result
        result = PatientInfo(raw_text=text)
        
        # Extract name
        name_result = self._extract_name(text)
        if name_result:
            result.patient_name = name_result[0]
            result.confidence += name_result[1]
        
        # Extract sex
        sex_result = self._extract_sex(text)
        if sex_result:
            result.sex = sex_result[0]
            result.confidence += sex_result[1]
        
        # Normalize confidence (0-1 scale)
        result.confidence = min(result.confidence, 1.0)
        
        return result
    
    def _extract_name(self, text: str) -> Optional[Tuple[str, float]]:
        """Extract patient name with confidence score"""
        for i, pattern in enumerate(self.compiled_name_patterns):
            match = pattern.search(text)
            if match:
                name = match.group(1).strip()
                
                # Clean up the name
                name = self._clean_name(name)
                
                if self._is_valid_name(name):
                    # Higher confidence for more specific patterns
                    confidence = 0.9 - (i * 0.1)  # First pattern = 0.9, last = 0.5
                    return (name, max(confidence, 0.5))
        
        return None
    
    def _extract_sex(self, text: str) -> Optional[Tuple[str, float]]:
        """Extract sex/gender with confidence score"""
        for i, pattern in enumerate(self.compiled_sex_patterns):
            match = pattern.search(text)
            if match:
                sex = match.group(1).lower()
                normalized_sex = self.sex_mapping.get(sex, sex.upper())
                
                # Higher confidence for explicit patterns
                confidence = 0.8 - (i * 0.1)
                return (normalized_sex, max(confidence, 0.6))
        
        return None
    
    def _clean_name(self, name: str) -> str:
        """Clean and normalize name format"""
        # Remove extra whitespace
        name = ' '.join(name.split())
        
        # Capitalize properly
        parts = name.split(',')
        if len(parts) == 2:
            # "Last, First" format
            last = parts[0].strip().title()
            first = parts[1].strip().title()
            return f"{last}, {first}"
        else:
            # Single part, assume "First Last"
            return name.title()
    
    def _is_valid_name(self, name: str) -> bool:
        """Validate that extracted text looks like a name"""
        # Basic validation rules
        if len(name) < 2 or len(name) > 100:
            return False
        
        # Should contain letters
        if not re.search(r'[A-Za-z]', name):
            return False
        
        # Shouldn't be all numbers
        if name.replace(' ', '').replace(',', '').replace('-', '').replace("'", '').isdigit():
            return False
        
        # Common false positives
        false_positives = {
            'patient', 'name', 'male', 'female', 'date', 'time',
            'hospital', 'clinic', 'doctor', 'physician'
        }
        
        if name.lower().strip(',') in false_positives:
            return False
        
        return True


class SpecimenExtractor:
    """Extract specimen information from HEADER_SPECIMEN lines"""
    
    def __init__(self):
        # Date patterns with labels
        self.date_patterns = [
            # Explicit labels
            (r'collected\s*(?:date|on)?\s*:\s*([0-9\/\-\.\s]+)', 'collected'),
            (r'collection\s*(?:date|on)?\s*:\s*([0-9\/\-\.\s]+)', 'collected'),
            (r'received\s*(?:date|on)?\s*:\s*([0-9\/\-\.\s]+)', 'received'),
            (r'entered\s*(?:date|on)?\s*:\s*([0-9\/\-\.\s]+)', 'entered'),
            (r'reported\s*(?:date|on)?\s*:\s*([0-9\/\-\.\s]+)', 'reported'),
            
            # Time patterns
            (r'collected\s*:\s*([0-9\/\-\.\s]+\s+[0-9:]+\s*(?:AM|PM)?)', 'collected'),
            (r'received\s*:\s*([0-9\/\-\.\s]+\s+[0-9:]+\s*(?:AM|PM)?)', 'received'),
        ]
        
        # Specimen number patterns
        self.specimen_patterns = [
            r'specimen\s*(?:number|#|no\.?|id)\s*:\s*([A-Za-z0-9\-_]+)',
            r'accession\s*(?:number|#|no\.?|id)?\s*:\s*([A-Za-z0-9\-_]+)',
            r'lab\s*(?:number|#|no\.?|id)\s*:\s*([A-Za-z0-9\-_]+)',
            r'sample\s*(?:number|#|no\.?|id)\s*:\s*([A-Za-z0-9\-_]+)',
            r'^\s*([A-Za-z0-9\-_]{6,})\s*$',  # Standalone specimen ID
        ]
        
        # Date format patterns for parsing
        self.date_formats = [
            '%m/%d/%Y', '%m/%d/%y',     # MM/DD/YYYY, MM/DD/YY
            '%m-%d-%Y', '%m-%d-%y',     # MM-DD-YYYY, MM-DD-YY
            '%Y-%m-%d',                 # YYYY-MM-DD (ISO)
            '%d/%m/%Y', '%d/%m/%y',     # DD/MM/YYYY, DD/MM/YY
            '%m.%d.%Y', '%m.%d.%y',     # MM.DD.YYYY, MM.DD.YY
            '%B %d, %Y',                # January 1, 2024
            '%b %d, %Y',                # Jan 1, 2024
            '%d %B %Y',                 # 1 January 2024
            '%d %b %Y',                 # 1 Jan 2024
        ]
        
        # Compile patterns
        self.compiled_date_patterns = [(re.compile(p, re.IGNORECASE), label) 
                                     for p, label in self.date_patterns]
        self.compiled_specimen_patterns = [re.compile(p, re.IGNORECASE) 
                                         for p in self.specimen_patterns]
    
    def extract(self, text: str) -> SpecimenInfo:
        """Extract specimen information from header text"""
        text = text.strip()
        
        # Initialize result
        result = SpecimenInfo(raw_text=text)
        
        # Extract specimen number
        specimen_result = self._extract_specimen_number(text)
        if specimen_result:
            result.specimen_number = specimen_result[0]
            result.confidence += specimen_result[1]
        
        # Extract dates
        dates = self._extract_dates(text)
        for date_type, date_value, confidence in dates:
            if date_type == 'collected':
                result.date_collected = date_value
                result.confidence += confidence
            elif date_type == 'received':
                result.date_received = date_value
                result.confidence += confidence
            elif date_type == 'entered':
                result.date_entered = date_value
                result.confidence += confidence
            elif date_type == 'reported':
                result.date_reported = date_value
                result.confidence += confidence
        
        # Normalize confidence
        result.confidence = min(result.confidence, 1.0)
        
        return result
    
    def _extract_specimen_number(self, text: str) -> Optional[Tuple[str, float]]:
        """Extract specimen number with confidence"""
        for i, pattern in enumerate(self.compiled_specimen_patterns):
            match = pattern.search(text)
            if match:
                specimen_id = match.group(1).strip()
                
                # Validate specimen ID
                if self._is_valid_specimen_id(specimen_id):
                    confidence = 0.9 - (i * 0.1)  # Higher confidence for more specific patterns
                    return (specimen_id, max(confidence, 0.5))
        
        return None
    
    def _extract_dates(self, text: str) -> List[Tuple[str, str, float]]:
        """Extract all dates with their types"""
        dates = []
        
        for pattern, date_type in self.compiled_date_patterns:
            for match in pattern.finditer(text):
                date_string = match.group(1).strip()
                
                # Parse and normalize the date
                normalized_date = self._parse_date(date_string)
                if normalized_date:
                    dates.append((date_type, normalized_date, 0.8))
        
        return dates
    
    def _parse_date(self, date_string: str) -> Optional[str]:
        """Parse date string into normalized format (YYYY-MM-DD)"""
        date_string = date_string.strip()
        
        # Remove common time components for date-only parsing
        date_part = re.sub(r'\s+[0-9]{1,2}:[0-9]{2}(?::[0-9]{2})?\s*(?:AM|PM)?.*', '', date_string)
        
        # Try each format
        for fmt in self.date_formats:
            try:
                parsed_date = datetime.strptime(date_part.strip(), fmt)
                return parsed_date.strftime('%Y-%m-%d')
            except ValueError:
                continue
        
        # Try partial matching for flexible parsing
        # Look for MM/DD/YYYY or similar patterns
        date_match = re.search(r'(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{2,4})', date_string)
        if date_match:
            month, day, year = date_match.groups()
            
            # Handle 2-digit years
            year = int(year)
            if year < 50:
                year += 2000
            elif year < 100:
                year += 1900
            
            try:
                parsed_date = date(year, int(month), int(day))
                return parsed_date.strftime('%Y-%m-%d')
            except ValueError:
                # Try day/month swap
                try:
                    parsed_date = date(year, int(day), int(month))
                    return parsed_date.strftime('%Y-%m-%d')
                except ValueError:
                    pass
        
        return None
    
    def _is_valid_specimen_id(self, specimen_id: str) -> bool:
        """Validate specimen ID"""
        # Basic validation
        if len(specimen_id) < 3 or len(specimen_id) > 50:
            return False
        
        # Should contain alphanumeric characters
        if not re.match(r'^[A-Za-z0-9\-_]+$', specimen_id):
            return False
        
        # Common false positives
        false_positives = {
            'specimen', 'sample', 'number', 'accession', 
            'lab', 'test', 'blood', 'urine'
        }
        
        if specimen_id.lower() in false_positives:
            return False
        
        return True


class HeaderExtractorLibrary:
    """Main library interface for header extraction"""
    
    def __init__(self):
        self.patient_extractor = PatientExtractor()
        self.specimen_extractor = SpecimenExtractor()
    
    def extract_patient_info(self, text: str) -> PatientInfo:
        """Extract patient information from HEADER_PATIENT text"""
        return self.patient_extractor.extract(text)
    
    def extract_specimen_info(self, text: str) -> SpecimenInfo:
        """Extract specimen information from HEADER_SPECIMEN text"""
        return self.specimen_extractor.extract(text)
    
    def extract_from_lines(self, lines: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract information from a list of lines with role labels"""
        results = {
            'patient_info': [],
            'specimen_info': []
        }
        
        for line in lines:
            role = line.get('predicted_role', line.get('role', ''))
            text = line.get('text', '')
            
            if role == 'HEADER_PATIENT' and text.strip():
                patient_info = self.extract_patient_info(text)
                if patient_info.patient_name or patient_info.sex:
                    results['patient_info'].append(asdict(patient_info))
            
            elif role == 'HEADER_SPECIMEN' and text.strip():
                specimen_info = self.extract_specimen_info(text)
                if any([specimen_info.specimen_number, specimen_info.date_collected,
                       specimen_info.date_received, specimen_info.date_entered,
                       specimen_info.date_reported]):
                    results['specimen_info'].append(asdict(specimen_info))
        
        return results
    
    def consolidate_patient_info(self, patient_infos: List[PatientInfo]) -> PatientInfo:
        """Consolidate multiple patient info extractions into best result"""
        if not patient_infos:
            return PatientInfo()
        
        # Find best name (highest confidence)
        best_name = None
        best_name_confidence = 0
        
        # Find best sex (highest confidence)
        best_sex = None
        best_sex_confidence = 0
        
        combined_text = []
        
        for info in patient_infos:
            combined_text.append(info.raw_text)
            
            if info.patient_name and info.confidence > best_name_confidence:
                best_name = info.patient_name
                best_name_confidence = info.confidence
            
            if info.sex and info.confidence > best_sex_confidence:
                best_sex = info.sex
                best_sex_confidence = info.confidence
        
        return PatientInfo(
            patient_name=best_name,
            sex=best_sex,
            raw_text='; '.join(combined_text),
            confidence=(best_name_confidence + best_sex_confidence) / 2 if best_name or best_sex else 0,
            extraction_method="consolidated"
        )
    
    def consolidate_specimen_info(self, specimen_infos: List[SpecimenInfo]) -> SpecimenInfo:
        """Consolidate multiple specimen info extractions into best result"""
        if not specimen_infos:
            return SpecimenInfo()
        
        # Combine all fields, preferring higher confidence values
        consolidated = SpecimenInfo(
            raw_text='; '.join([info.raw_text for info in specimen_infos]),
            extraction_method="consolidated"
        )
        
        field_confidences = {}
        
        for info in specimen_infos:
            for field in ['specimen_number', 'date_collected', 'date_received', 
                         'date_entered', 'date_reported']:
                value = getattr(info, field)
                if value:
                    if field not in field_confidences or info.confidence > field_confidences[field][1]:
                        field_confidences[field] = (value, info.confidence)
        
        # Set the best values
        for field, (value, confidence) in field_confidences.items():
            setattr(consolidated, field, value)
        
        # Average confidence
        if field_confidences:
            consolidated.confidence = sum(conf for _, conf in field_confidences.values()) / len(field_confidences)
        
        return consolidated


def load_header_library() -> HeaderExtractorLibrary:
    """Factory function to create header extractor library"""
    return HeaderExtractorLibrary()


# Convenience functions for direct usage
def extract_patient_name_and_sex(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Quick function to extract patient name and sex from text"""
    extractor = PatientExtractor()
    result = extractor.extract(text)
    return result.patient_name, result.sex


def extract_specimen_dates(text: str) -> Dict[str, Optional[str]]:
    """Quick function to extract specimen dates from text"""
    extractor = SpecimenExtractor()
    result = extractor.extract(text)
    
    return {
        'specimen_number': result.specimen_number,
        'date_collected': result.date_collected,
        'date_received': result.date_received,
        'date_entered': result.date_entered,
        'date_reported': result.date_reported
    }


if __name__ == '__main__':
    # Test the extractors
    library = HeaderExtractorLibrary()
    
    # Test patient extraction
    patient_examples = [
        "Patient: Smith, John (Male)",
        "Name: Doe, Jane F",
        "Mr. Johnson, Robert",
        "Patient Name: Sarah Williams Female"
    ]
    
    print("=== Patient Information Extraction ===")
    for text in patient_examples:
        result = library.extract_patient_info(text)
        print(f"Text: {text}")
        print(f"Name: {result.patient_name}, Sex: {result.sex}, Confidence: {result.confidence:.2f}")
        print()
    
    # Test specimen extraction
    specimen_examples = [
        "Specimen Number: LAB2024001234",
        "Collected: 03/14/2024 Received: 03/14/2024 2:30 PM",
        "Accession: ACC123456 Collection Date: 01/15/2024",
        "Specimen ID: SPEC789 Entered: 2024-01-16 Reported: 2024-01-17"
    ]
    
    print("=== Specimen Information Extraction ===")
    for text in specimen_examples:
        result = library.extract_specimen_info(text)
        print(f"Text: {text}")
        print(f"Specimen#: {result.specimen_number}")
        print(f"Collected: {result.date_collected}, Received: {result.date_received}")
        print(f"Entered: {result.date_entered}, Reported: {result.date_reported}")
        print(f"Confidence: {result.confidence:.2f}")
        print()