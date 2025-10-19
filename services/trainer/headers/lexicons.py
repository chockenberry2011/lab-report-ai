"""
Lexicons and vocabularies for header extraction

Medical terminology, common names, and validation data for improved accuracy.
"""

import json
import re
from typing import Set, List, Dict, Optional
from pathlib import Path


class NameLexicon:
    """Lexicon for patient name validation and enhancement"""
    
    def __init__(self):
        # Common first names (subset for validation)
        self.common_first_names = {
            # Male names
            'james', 'john', 'robert', 'michael', 'william', 'david', 'richard', 'joseph',
            'thomas', 'christopher', 'charles', 'daniel', 'matthew', 'anthony', 'mark',
            'donald', 'steven', 'paul', 'andrew', 'joshua', 'kenneth', 'kevin', 'brian',
            'george', 'timothy', 'ronald', 'jason', 'edward', 'jeffrey', 'ryan', 'jacob',
            
            # Female names  
            'mary', 'patricia', 'jennifer', 'linda', 'elizabeth', 'barbara', 'susan',
            'jessica', 'sarah', 'karen', 'nancy', 'lisa', 'betty', 'helen', 'sandra',
            'donna', 'carol', 'ruth', 'sharon', 'michelle', 'laura', 'sarah', 'kimberly',
            'deborah', 'dorothy', 'lisa', 'nancy', 'karen', 'betty', 'helen', 'sandra',
            
            # Common variations and nicknames
            'mike', 'dave', 'steve', 'chris', 'bob', 'bill', 'tom', 'jim', 'joe',
            'sue', 'beth', 'liz', 'kate', 'ann', 'lynn', 'pat', 'jan', 'kim'
        }
        
        # Common last name patterns and prefixes
        self.last_name_prefixes = {
            'mc', 'mac', 'o\'', 'de', 'la', 'le', 'van', 'von', 'del', 'el',
            'san', 'st', 'saint'
        }
        
        # Name suffixes
        self.name_suffixes = {
            'jr', 'sr', 'ii', 'iii', 'iv', 'v', 'md', 'phd', 'rn', 'do'
        }
        
        # Common false positive patterns for names
        self.false_positive_patterns = {
            r'patient\s*(?:name|id|number)',
            r'medical\s*record',
            r'date\s*of\s*birth',
            r'hospital\s*name',
            r'doctor\s*name',
            r'physician\s*name',
            r'lab\s*name',
            r'test\s*name'
        }
        
        self.compiled_false_positives = [re.compile(p, re.IGNORECASE) 
                                       for p in self.false_positive_patterns]
    
    def is_likely_first_name(self, name: str) -> bool:
        """Check if a name is likely a first name"""
        name_lower = name.lower().strip()
        return name_lower in self.common_first_names
    
    def has_name_suffix(self, name: str) -> bool:
        """Check if name has a common suffix"""
        words = name.lower().split()
        return any(word.rstrip('.') in self.name_suffixes for word in words)
    
    def is_false_positive(self, text: str) -> bool:
        """Check if text matches common false positive patterns"""
        return any(pattern.search(text) for pattern in self.compiled_false_positives)
    
    def validate_name_structure(self, name: str) -> Dict[str, float]:
        """Validate name structure and return confidence factors"""
        factors = {}
        
        # Check for comma (Last, First format)
        if ',' in name:
            factors['comma_format'] = 0.3
            
            parts = name.split(',')
            if len(parts) == 2:
                last_part = parts[0].strip()
                first_part = parts[1].strip()
                
                # Validate first name
                if self.is_likely_first_name(first_part.split()[0]):
                    factors['known_first_name'] = 0.4
                
                # Check last name length (reasonable surnames)
                if 2 <= len(last_part) <= 20:
                    factors['reasonable_lastname'] = 0.2
        
        # Check for title patterns
        if re.match(r'(mr|ms|mrs|dr|prof)\.?\s+', name, re.IGNORECASE):
            factors['has_title'] = 0.2
        
        # Check for name suffixes
        if self.has_name_suffix(name):
            factors['has_suffix'] = 0.1
        
        # Penalize if looks like false positive
        if self.is_false_positive(name):
            factors['false_positive_penalty'] = -0.5
        
        return factors


class MedicalLexicon:
    """Medical terminology and specimen-related vocabularies"""
    
    def __init__(self):
        # Specimen types
        self.specimen_types = {
            'blood', 'serum', 'plasma', 'urine', 'stool', 'sputum', 'csf',
            'cerebrospinal fluid', 'saliva', 'swab', 'tissue', 'biopsy',
            'fluid', 'aspirate', 'lavage', 'washing'
        }
        
        # Collection methods/containers
        self.collection_containers = {
            'tube', 'vial', 'container', 'cup', 'bottle', 'bag', 'syringe',
            'capillary', 'microtainer', 'vacutainer', 'edta', 'heparin'
        }
        
        # Date/time keywords
        self.date_keywords = {
            'collected', 'collection', 'drawn', 'obtained', 'taken',
            'received', 'entered', 'processed', 'analyzed', 'reported',
            'completed', 'finalized', 'verified', 'reviewed'
        }
        
        # Common lab prefixes for specimen IDs
        self.lab_prefixes = {
            'lab', 'acc', 'accession', 'specimen', 'spec', 'sample', 'samp',
            'test', 'order', 'req', 'request', 'case', 'path', 'cyto', 'hist',
            'micro', 'chem', 'heme', 'coag', 'immuno', 'molec'
        }
        
        # Patient identifier keywords
        self.patient_keywords = {
            'patient', 'name', 'pt', 'ptnt', 'person', 'individual', 'client',
            'subject', 'case', 'record', 'mrn', 'medical record number',
            'account', 'id', 'identifier'
        }
        
        # Sex/gender terms
        self.sex_terms = {
            'sex', 'gender', 'male', 'female', 'man', 'woman', 'boy', 'girl',
            'm', 'f', 'masculine', 'feminine'
        }
    
    def is_specimen_related(self, text: str) -> bool:
        """Check if text is specimen-related"""
        text_lower = text.lower()
        return (any(spec_type in text_lower for spec_type in self.specimen_types) or
                any(container in text_lower for container in self.collection_containers) or
                any(keyword in text_lower for keyword in self.date_keywords))
    
    def is_patient_related(self, text: str) -> bool:
        """Check if text is patient-related"""
        text_lower = text.lower()
        return (any(keyword in text_lower for keyword in self.patient_keywords) or
                any(term in text_lower for term in self.sex_terms))
    
    def get_specimen_id_confidence(self, specimen_id: str) -> float:
        """Calculate confidence for specimen ID based on patterns"""
        confidence = 0.5  # Base confidence
        
        # Check for common prefixes
        id_lower = specimen_id.lower()
        if any(prefix in id_lower for prefix in self.lab_prefixes):
            confidence += 0.2
        
        # Check format patterns
        if re.match(r'^[A-Za-z]{2,6}\d{4,12}$', specimen_id):  # Letters + numbers
            confidence += 0.2
        elif re.match(r'^\d{6,15}$', specimen_id):  # All numbers, reasonable length
            confidence += 0.1
        elif re.match(r'^[A-Za-z0-9\-_]{8,20}$', specimen_id):  # Mixed with separators
            confidence += 0.15
        
        # Penalize very short or very long IDs
        if len(specimen_id) < 4:
            confidence -= 0.2
        elif len(specimen_id) > 25:
            confidence -= 0.1
        
        return min(confidence, 1.0)


class DateLexicon:
    """Enhanced date parsing and validation"""
    
    def __init__(self):
        # Month names and abbreviations
        self.month_names = {
            'january': 1, 'jan': 1, 'february': 2, 'feb': 2, 'march': 3, 'mar': 3,
            'april': 4, 'apr': 4, 'may': 5, 'june': 6, 'jun': 6,
            'july': 7, 'jul': 7, 'august': 8, 'aug': 8, 'september': 9, 'sep': 9, 'sept': 9,
            'october': 10, 'oct': 10, 'november': 11, 'nov': 11, 'december': 12, 'dec': 12
        }
        
        # Day suffixes
        self.day_suffixes = {'st', 'nd', 'rd', 'th'}
        
        # Time indicators
        self.time_indicators = {
            'am', 'pm', 'morning', 'afternoon', 'evening', 'night',
            'midnight', 'noon', 'o\'clock'
        }
        
        # Date context keywords
        self.date_contexts = {
            'on', 'at', 'date', 'time', 'dated', 'timestamp', 'when', 'during'
        }
    
    def extract_month_from_text(self, text: str) -> Optional[int]:
        """Extract month number from text containing month names"""
        text_lower = text.lower()
        for month_name, month_num in self.month_names.items():
            if month_name in text_lower:
                return month_num
        return None
    
    def has_time_component(self, text: str) -> bool:
        """Check if text contains time information"""
        text_lower = text.lower()
        return (any(indicator in text_lower for indicator in self.time_indicators) or
                bool(re.search(r'\d{1,2}:\d{2}', text)))
    
    def validate_date_context(self, text: str) -> bool:
        """Check if text has appropriate date context"""
        text_lower = text.lower()
        return any(context in text_lower for context in self.date_contexts)


class LexiconManager:
    """Manager for all lexicons with convenience methods"""
    
    def __init__(self):
        self.names = NameLexicon()
        self.medical = MedicalLexicon() 
        self.dates = DateLexicon()
    
    def enhance_name_confidence(self, name: str, base_confidence: float) -> float:
        """Enhance name confidence using lexicon validation"""
        factors = self.names.validate_name_structure(name)
        
        adjustment = sum(factors.values())
        enhanced_confidence = base_confidence + adjustment
        
        return max(0.0, min(enhanced_confidence, 1.0))
    
    def enhance_specimen_confidence(self, specimen_id: str, base_confidence: float) -> float:
        """Enhance specimen ID confidence using medical lexicon"""
        lexicon_confidence = self.medical.get_specimen_id_confidence(specimen_id)
        
        # Weighted average with slight preference for lexicon
        enhanced_confidence = (base_confidence * 0.6 + lexicon_confidence * 0.4)
        
        return min(enhanced_confidence, 1.0)
    
    def validate_extraction_context(self, text: str, extraction_type: str) -> bool:
        """Validate that extraction makes sense in context"""
        if extraction_type == 'patient':
            return self.medical.is_patient_related(text)
        elif extraction_type == 'specimen':
            return self.medical.is_specimen_related(text)
        elif extraction_type == 'date':
            return self.dates.validate_date_context(text)
        else:
            return True
    
    def get_extraction_suggestions(self, text: str) -> Dict[str, List[str]]:
        """Get suggestions for what to extract from text"""
        suggestions = {
            'patient_likely': [],
            'specimen_likely': [],
            'date_likely': []
        }
        
        if self.medical.is_patient_related(text):
            suggestions['patient_likely'].append('Contains patient-related keywords')
        
        if self.medical.is_specimen_related(text):
            suggestions['specimen_likely'].append('Contains specimen-related keywords')
        
        if self.dates.has_time_component(text):
            suggestions['date_likely'].append('Contains time information')
        
        # Look for patterns
        if re.search(r'[A-Za-z]+,\s*[A-Za-z]+', text):
            suggestions['patient_likely'].append('Has "Last, First" name pattern')
        
        if re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', text):
            suggestions['date_likely'].append('Has date pattern')
        
        if re.search(r'[A-Za-z]{2,6}\d{4,}', text):
            suggestions['specimen_likely'].append('Has alphanumeric ID pattern')
        
        return suggestions


def load_lexicon_manager() -> LexiconManager:
    """Factory function to create lexicon manager"""
    return LexiconManager()


def save_lexicons_to_json(output_dir: str):
    """Save lexicons to JSON files for external use"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    manager = LexiconManager()
    
    # Export lexicons
    lexicons = {
        'names': {
            'common_first_names': list(manager.names.common_first_names),
            'last_name_prefixes': list(manager.names.last_name_prefixes),
            'name_suffixes': list(manager.names.name_suffixes)
        },
        'medical': {
            'specimen_types': list(manager.medical.specimen_types),
            'collection_containers': list(manager.medical.collection_containers),
            'date_keywords': list(manager.medical.date_keywords),
            'lab_prefixes': list(manager.medical.lab_prefixes),
            'patient_keywords': list(manager.medical.patient_keywords),
            'sex_terms': list(manager.medical.sex_terms)
        },
        'dates': {
            'month_names': manager.dates.month_names,
            'day_suffixes': list(manager.dates.day_suffixes),
            'time_indicators': list(manager.dates.time_indicators),
            'date_contexts': list(manager.dates.date_contexts)
        }
    }
    
    for lexicon_name, lexicon_data in lexicons.items():
        output_file = output_dir / f"{lexicon_name}_lexicon.json"
        with open(output_file, 'w') as f:
            json.dump(lexicon_data, f, indent=2)
    
    print(f"Lexicons saved to {output_dir}")


if __name__ == '__main__':
    # Test lexicons
    manager = LexiconManager()
    
    # Test name enhancement
    test_names = [
        "Smith, John",
        "Dr. Johnson, Sarah",
        "Patient Name",  # Should be penalized
        "Mary Elizabeth Wilson Jr."
    ]
    
    print("=== Name Confidence Enhancement ===")
    for name in test_names:
        base_conf = 0.7
        enhanced_conf = manager.enhance_name_confidence(name, base_conf)
        print(f"{name}: {base_conf:.2f} -> {enhanced_conf:.2f}")
    
    # Test specimen ID enhancement
    test_specimens = [
        "LAB2024001234",
        "ACC123456", 
        "SPEC789",
        "123",  # Too short
        "VERYLONGSPECIMENIDENTIFIER123456"  # Too long
    ]
    
    print("\n=== Specimen ID Confidence Enhancement ===")
    for specimen_id in test_specimens:
        base_conf = 0.6
        enhanced_conf = manager.enhance_specimen_confidence(specimen_id, base_conf)
        print(f"{specimen_id}: {base_conf:.2f} -> {enhanced_conf:.2f}")
    
    # Test extraction suggestions
    test_texts = [
        "Patient: Anderson, Michael (Male)",
        "Specimen ID: LAB123 Collected: 03/14/2024",
        "Random text without clear patterns"
    ]
    
    print("\n=== Extraction Suggestions ===")
    for text in test_texts:
        suggestions = manager.get_extraction_suggestions(text)
        print(f"\nText: {text}")
        for category, hints in suggestions.items():
            if hints:
                print(f"  {category}: {', '.join(hints)}")
    
    # Save lexicons
    save_lexicons_to_json("/tmp/lexicons")