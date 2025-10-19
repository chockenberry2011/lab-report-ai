"""
Enhanced header extractors with lexicon integration

Improved accuracy using medical lexicons and validation.
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

from header_extractors import (
    PatientExtractor, SpecimenExtractor, HeaderExtractorLibrary,
    PatientInfo, SpecimenInfo
)
from lexicons import LexiconManager


@dataclass
class EnhancedExtractionResult:
    """Enhanced extraction result with lexicon validation"""
    raw_result: Any  # PatientInfo or SpecimenInfo
    lexicon_confidence: float
    validation_flags: List[str]
    suggestions: List[str]
    final_confidence: float


class EnhancedPatientExtractor(PatientExtractor):
    """Patient extractor enhanced with lexicon validation"""
    
    def __init__(self):
        super().__init__()
        self.lexicon_manager = LexiconManager()
    
    def extract_enhanced(self, text: str) -> EnhancedExtractionResult:
        """Extract with lexicon enhancement and validation"""
        # Get base extraction
        base_result = super().extract(text)
        
        validation_flags = []
        suggestions = []
        lexicon_confidence = base_result.confidence
        
        # Enhance name confidence if extracted
        if base_result.patient_name:
            enhanced_name_conf = self.lexicon_manager.enhance_name_confidence(
                base_result.patient_name, base_result.confidence
            )
            
            if enhanced_name_conf > base_result.confidence:
                validation_flags.append("lexicon_enhanced_name")
                lexicon_confidence = enhanced_name_conf
            elif enhanced_name_conf < base_result.confidence:
                validation_flags.append("lexicon_warning_name")
                suggestions.append("Name may be false positive based on pattern")
        
        # Validate context
        if not self.lexicon_manager.validate_extraction_context(text, 'patient'):
            validation_flags.append("context_mismatch")
            suggestions.append("Text doesn't appear to be patient-related")
            lexicon_confidence *= 0.8  # Reduce confidence
        
        # Check for missing extractions
        extraction_suggestions = self.lexicon_manager.get_extraction_suggestions(text)
        if extraction_suggestions['patient_likely'] and not base_result.patient_name:
            suggestions.extend(extraction_suggestions['patient_likely'])
            suggestions.append("Consider re-examining text for patient information")
        
        # Final confidence is weighted average
        final_confidence = (base_result.confidence * 0.6 + lexicon_confidence * 0.4)
        
        return EnhancedExtractionResult(
            raw_result=base_result,
            lexicon_confidence=lexicon_confidence,
            validation_flags=validation_flags,
            suggestions=suggestions,
            final_confidence=final_confidence
        )


class EnhancedSpecimenExtractor(SpecimenExtractor):
    """Specimen extractor enhanced with lexicon validation"""
    
    def __init__(self):
        super().__init__()
        self.lexicon_manager = LexiconManager()
    
    def extract_enhanced(self, text: str) -> EnhancedExtractionResult:
        """Extract with lexicon enhancement and validation"""
        # Get base extraction
        base_result = super().extract(text)
        
        validation_flags = []
        suggestions = []
        lexicon_confidence = base_result.confidence
        
        # Enhance specimen number confidence if extracted
        if base_result.specimen_number:
            enhanced_spec_conf = self.lexicon_manager.enhance_specimen_confidence(
                base_result.specimen_number, base_result.confidence
            )
            
            if enhanced_spec_conf > base_result.confidence:
                validation_flags.append("lexicon_enhanced_specimen")
                lexicon_confidence = enhanced_spec_conf
            elif enhanced_spec_conf < base_result.confidence:
                validation_flags.append("lexicon_warning_specimen")
                suggestions.append("Specimen ID may not follow standard format")
        
        # Validate date extractions using lexicon
        date_fields = [base_result.date_collected, base_result.date_received,
                      base_result.date_entered, base_result.date_reported]
        
        if any(date_fields):
            if self.lexicon_manager.dates.has_time_component(text):
                validation_flags.append("has_time_component")
            
            if not self.lexicon_manager.dates.validate_date_context(text):
                validation_flags.append("weak_date_context")
                suggestions.append("Date context may be unclear")
        
        # Validate context
        if not self.lexicon_manager.validate_extraction_context(text, 'specimen'):
            validation_flags.append("context_mismatch")
            suggestions.append("Text doesn't appear to be specimen-related")
            lexicon_confidence *= 0.8
        
        # Check for missing extractions
        extraction_suggestions = self.lexicon_manager.get_extraction_suggestions(text)
        if extraction_suggestions['specimen_likely'] and not base_result.specimen_number:
            suggestions.extend(extraction_suggestions['specimen_likely'])
        if extraction_suggestions['date_likely'] and not any(date_fields):
            suggestions.extend(extraction_suggestions['date_likely'])
        
        # Final confidence calculation
        final_confidence = (base_result.confidence * 0.6 + lexicon_confidence * 0.4)
        
        return EnhancedExtractionResult(
            raw_result=base_result,
            lexicon_confidence=lexicon_confidence,
            validation_flags=validation_flags,
            suggestions=suggestions,
            final_confidence=final_confidence
        )


class EnhancedHeaderExtractorLibrary(HeaderExtractorLibrary):
    """Enhanced header extractor library with lexicon integration"""
    
    def __init__(self):
        super().__init__()
        self.enhanced_patient_extractor = EnhancedPatientExtractor()
        self.enhanced_specimen_extractor = EnhancedSpecimenExtractor()
        self.lexicon_manager = LexiconManager()
    
    def extract_patient_info_enhanced(self, text: str) -> EnhancedExtractionResult:
        """Extract patient info with lexicon enhancement"""
        return self.enhanced_patient_extractor.extract_enhanced(text)
    
    def extract_specimen_info_enhanced(self, text: str) -> EnhancedExtractionResult:
        """Extract specimen info with lexicon enhancement"""
        return self.enhanced_specimen_extractor.extract_enhanced(text)
    
    def extract_from_lines_enhanced(self, lines: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Enhanced extraction from lines with validation and suggestions"""
        results = {
            'patient_info': [],
            'specimen_info': [],
            'validation_summary': {
                'total_extractions': 0,
                'high_confidence': 0,
                'medium_confidence': 0,
                'low_confidence': 0,
                'warnings': [],
                'suggestions': []
            }
        }
        
        for line in lines:
            role = line.get('predicted_role', line.get('role', ''))
            text = line.get('text', '')
            
            if role == 'HEADER_PATIENT' and text.strip():
                enhanced_result = self.extract_patient_info_enhanced(text)
                
                if enhanced_result.raw_result.patient_name or enhanced_result.raw_result.sex:
                    patient_data = {
                        'patient_name': enhanced_result.raw_result.patient_name,
                        'sex': enhanced_result.raw_result.sex,
                        'raw_text': enhanced_result.raw_result.raw_text,
                        'confidence': enhanced_result.final_confidence,
                        'lexicon_confidence': enhanced_result.lexicon_confidence,
                        'validation_flags': enhanced_result.validation_flags,
                        'suggestions': enhanced_result.suggestions
                    }
                    results['patient_info'].append(patient_data)
                    self._update_validation_summary(results['validation_summary'], enhanced_result)
            
            elif role == 'HEADER_SPECIMEN' and text.strip():
                enhanced_result = self.extract_specimen_info_enhanced(text)
                
                if any([enhanced_result.raw_result.specimen_number,
                       enhanced_result.raw_result.date_collected,
                       enhanced_result.raw_result.date_received,
                       enhanced_result.raw_result.date_entered,
                       enhanced_result.raw_result.date_reported]):
                    
                    specimen_data = {
                        'specimen_number': enhanced_result.raw_result.specimen_number,
                        'date_collected': enhanced_result.raw_result.date_collected,
                        'date_received': enhanced_result.raw_result.date_received,
                        'date_entered': enhanced_result.raw_result.date_entered,
                        'date_reported': enhanced_result.raw_result.date_reported,
                        'raw_text': enhanced_result.raw_result.raw_text,
                        'confidence': enhanced_result.final_confidence,
                        'lexicon_confidence': enhanced_result.lexicon_confidence,
                        'validation_flags': enhanced_result.validation_flags,
                        'suggestions': enhanced_result.suggestions
                    }
                    results['specimen_info'].append(specimen_data)
                    self._update_validation_summary(results['validation_summary'], enhanced_result)
        
        return results
    
    def _update_validation_summary(self, summary: Dict[str, Any], 
                                 result: EnhancedExtractionResult):
        """Update validation summary with extraction result"""
        summary['total_extractions'] += 1
        
        # Categorize by confidence
        if result.final_confidence >= 0.8:
            summary['high_confidence'] += 1
        elif result.final_confidence >= 0.6:
            summary['medium_confidence'] += 1
        else:
            summary['low_confidence'] += 1
        
        # Collect warnings and suggestions
        for flag in result.validation_flags:
            if 'warning' in flag:
                summary['warnings'].append(flag)
        
        summary['suggestions'].extend(result.suggestions)
    
    def validate_extraction_quality(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Validate overall extraction quality and provide recommendations"""
        summary = results.get('validation_summary', {})
        
        quality_metrics = {
            'overall_quality': 'unknown',
            'confidence_distribution': {
                'high': summary.get('high_confidence', 0),
                'medium': summary.get('medium_confidence', 0),
                'low': summary.get('low_confidence', 0)
            },
            'recommendations': [],
            'quality_score': 0.0
        }
        
        total = summary.get('total_extractions', 0)
        if total == 0:
            return quality_metrics
        
        # Calculate quality score
        high_ratio = summary.get('high_confidence', 0) / total
        medium_ratio = summary.get('medium_confidence', 0) / total
        low_ratio = summary.get('low_confidence', 0) / total
        
        quality_score = (high_ratio * 1.0 + medium_ratio * 0.6 + low_ratio * 0.2)
        quality_metrics['quality_score'] = quality_score
        
        # Determine overall quality
        if quality_score >= 0.8:
            quality_metrics['overall_quality'] = 'high'
        elif quality_score >= 0.6:
            quality_metrics['overall_quality'] = 'medium'
        else:
            quality_metrics['overall_quality'] = 'low'
        
        # Generate recommendations
        if low_ratio > 0.3:
            quality_metrics['recommendations'].append(
                "High proportion of low-confidence extractions - consider data quality review"
            )
        
        warning_count = len(summary.get('warnings', []))
        if warning_count > total * 0.2:
            quality_metrics['recommendations'].append(
                "Many validation warnings - check text formatting and patterns"
            )
        
        if 'context_mismatch' in summary.get('warnings', []):
            quality_metrics['recommendations'].append(
                "Context mismatches detected - verify role classification accuracy"
            )
        
        return quality_metrics


def create_extraction_report(results: Dict[str, Any]) -> str:
    """Create a human-readable extraction report"""
    report_lines = []
    
    # Header
    report_lines.append("=== Header Extraction Report ===")
    report_lines.append("")
    
    # Patient Information
    patient_infos = results.get('patient_info', [])
    report_lines.append(f"Patient Information ({len(patient_infos)} extractions):")
    
    for i, patient in enumerate(patient_infos, 1):
        report_lines.append(f"  {i}. Name: {patient.get('patient_name', 'N/A')}")
        report_lines.append(f"     Sex: {patient.get('sex', 'N/A')}")
        report_lines.append(f"     Confidence: {patient.get('confidence', 0):.3f}")
        
        if patient.get('validation_flags'):
            report_lines.append(f"     Flags: {', '.join(patient['validation_flags'])}")
        
        report_lines.append("")
    
    # Specimen Information
    specimen_infos = results.get('specimen_info', [])
    report_lines.append(f"Specimen Information ({len(specimen_infos)} extractions):")
    
    for i, specimen in enumerate(specimen_infos, 1):
        report_lines.append(f"  {i}. Number: {specimen.get('specimen_number', 'N/A')}")
        report_lines.append(f"     Collected: {specimen.get('date_collected', 'N/A')}")
        report_lines.append(f"     Received: {specimen.get('date_received', 'N/A')}")
        report_lines.append(f"     Confidence: {specimen.get('confidence', 0):.3f}")
        
        if specimen.get('validation_flags'):
            report_lines.append(f"     Flags: {', '.join(specimen['validation_flags'])}")
        
        report_lines.append("")
    
    # Validation Summary
    validation_summary = results.get('validation_summary', {})
    if validation_summary:
        report_lines.append("Validation Summary:")
        report_lines.append(f"  Total Extractions: {validation_summary.get('total_extractions', 0)}")
        report_lines.append(f"  High Confidence: {validation_summary.get('high_confidence', 0)}")
        report_lines.append(f"  Medium Confidence: {validation_summary.get('medium_confidence', 0)}")
        report_lines.append(f"  Low Confidence: {validation_summary.get('low_confidence', 0)}")
        
        warnings = validation_summary.get('warnings', [])
        if warnings:
            report_lines.append(f"  Warnings: {len(warnings)}")
            for warning in warnings[:5]:  # Show first 5
                report_lines.append(f"    - {warning}")
    
    return "\n".join(report_lines)


def load_enhanced_library() -> EnhancedHeaderExtractorLibrary:
    """Factory function to create enhanced library"""
    return EnhancedHeaderExtractorLibrary()


if __name__ == '__main__':
    # Test enhanced extractors
    library = EnhancedHeaderExtractorLibrary()
    
    # Test data
    test_lines = [
        {'text': 'Patient: Johnson, Sarah (Female)', 'predicted_role': 'HEADER_PATIENT'},
        {'text': 'DOB: 08/23/1992 MRN: 123456789', 'predicted_role': 'HEADER_PATIENT'},
        {'text': 'Specimen ID: LAB2024005678', 'predicted_role': 'HEADER_SPECIMEN'},
        {'text': 'Collection: 03/20/2024 10:30 AM Received: 03/20/2024 2:15 PM', 'predicted_role': 'HEADER_SPECIMEN'},
        {'text': 'Patient Name: Invalid', 'predicted_role': 'HEADER_PATIENT'},  # Should trigger warnings
    ]
    
    print("=== Enhanced Header Extraction Test ===")
    
    # Extract with enhancement
    results = library.extract_from_lines_enhanced(test_lines)
    
    # Create and print report
    report = create_extraction_report(results)
    print(report)
    
    # Quality validation
    quality_metrics = library.validate_extraction_quality(results)
    print("\n=== Quality Metrics ===")
    print(f"Overall Quality: {quality_metrics['overall_quality']}")
    print(f"Quality Score: {quality_metrics['quality_score']:.3f}")
    
    if quality_metrics['recommendations']:
        print("\nRecommendations:")
        for rec in quality_metrics['recommendations']:
            print(f"  - {rec}")