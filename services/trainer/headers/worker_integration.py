"""
Worker integration for header extractors

Library interface for worker service to use header extraction functionality.
"""

import json
import logging
from typing import Dict, List, Any, Optional, Union
from dataclasses import asdict

from header_extractors import (
    HeaderExtractorLibrary, PatientInfo, SpecimenInfo,
    extract_patient_name_and_sex, extract_specimen_dates
)
from enhanced_extractors import (
    EnhancedHeaderExtractorLibrary, create_extraction_report,
    load_enhanced_library
)


class HeaderExtractionService:
    """Service interface for header extraction in worker processes"""
    
    def __init__(self, use_enhanced: bool = True):
        """
        Initialize header extraction service
        
        Args:
            use_enhanced: Whether to use lexicon-enhanced extractors
        """
        if use_enhanced:
            self.library = load_enhanced_library()
            self.enhanced = True
        else:
            self.library = HeaderExtractorLibrary()
            self.enhanced = False
        
        self.logger = logging.getLogger(__name__)
    
    def process_document_lines(self, lines: List[Dict[str, Any]], 
                             include_validation: bool = True) -> Dict[str, Any]:
        """
        Process document lines and extract header information
        
        Args:
            lines: List of line dictionaries with text and role information
            include_validation: Whether to include validation metrics
        
        Returns:
            Dictionary with extracted patient and specimen information
        """
        try:
            if self.enhanced:
                results = self.library.extract_from_lines_enhanced(lines)
                
                if include_validation:
                    quality_metrics = self.library.validate_extraction_quality(results)
                    results['quality_metrics'] = quality_metrics
                
            else:
                results = self.library.extract_from_lines(lines)
                results['enhanced'] = False
            
            # Add processing metadata
            results['processing_info'] = {
                'total_lines_processed': len(lines),
                'header_lines_found': sum(1 for line in lines 
                                        if line.get('predicted_role', '').startswith('HEADER_')),
                'enhanced_processing': self.enhanced,
                'extraction_method': 'lexicon_enhanced' if self.enhanced else 'pattern_based'
            }
            
            return results
        
        except Exception as e:
            self.logger.error(f"Error processing document lines: {e}")
            return {
                'error': str(e),
                'patient_info': [],
                'specimen_info': [],
                'processing_info': {
                    'total_lines_processed': len(lines),
                    'enhanced_processing': self.enhanced,
                    'extraction_method': 'error'
                }
            }
    
    def extract_patient_summary(self, lines: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Extract consolidated patient summary from document lines
        
        Args:
            lines: Document lines
        
        Returns:
            Consolidated patient information or None if not found
        """
        try:
            results = self.process_document_lines(lines, include_validation=False)
            patient_infos = results.get('patient_info', [])
            
            if not patient_infos:
                return None
            
            # Consolidate multiple patient info extractions
            if self.enhanced:
                # For enhanced results, we already have dictionaries
                best_patient = max(patient_infos, key=lambda p: p.get('confidence', 0))
            else:
                # For basic results, convert to PatientInfo objects first
                patient_objects = []
                for info in patient_infos:
                    patient_obj = PatientInfo(**info)
                    patient_objects.append(patient_obj)
                
                consolidated = self.library.consolidate_patient_info(patient_objects)
                best_patient = asdict(consolidated)
            
            return best_patient
        
        except Exception as e:
            self.logger.error(f"Error extracting patient summary: {e}")
            return None
    
    def extract_specimen_summary(self, lines: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Extract consolidated specimen summary from document lines
        
        Args:
            lines: Document lines
            
        Returns:
            Consolidated specimen information or None if not found
        """
        try:
            results = self.process_document_lines(lines, include_validation=False)
            specimen_infos = results.get('specimen_info', [])
            
            if not specimen_infos:
                return None
            
            # Consolidate multiple specimen info extractions
            if self.enhanced:
                # For enhanced results, find best specimen info
                best_specimen = max(specimen_infos, key=lambda s: s.get('confidence', 0))
            else:
                # For basic results, convert and consolidate
                specimen_objects = []
                for info in specimen_infos:
                    specimen_obj = SpecimenInfo(**info)
                    specimen_objects.append(specimen_obj)
                
                consolidated = self.library.consolidate_specimen_info(specimen_objects)
                best_specimen = asdict(consolidated)
            
            return best_specimen
        
        except Exception as e:
            self.logger.error(f"Error extracting specimen summary: {e}")
            return None
    
    def quick_extract_patient_info(self, text: str) -> Dict[str, Optional[str]]:
        """
        Quick extraction of patient name and sex from single text
        
        Args:
            text: Header text to process
            
        Returns:
            Dictionary with patient_name and sex fields
        """
        try:
            name, sex = extract_patient_name_and_sex(text)
            return {'patient_name': name, 'sex': sex}
        except Exception as e:
            self.logger.error(f"Error in quick patient extraction: {e}")
            return {'patient_name': None, 'sex': None}
    
    def quick_extract_specimen_info(self, text: str) -> Dict[str, Optional[str]]:
        """
        Quick extraction of specimen information from single text
        
        Args:
            text: Header text to process
            
        Returns:
            Dictionary with specimen fields
        """
        try:
            return extract_specimen_dates(text)
        except Exception as e:
            self.logger.error(f"Error in quick specimen extraction: {e}")
            return {
                'specimen_number': None,
                'date_collected': None, 
                'date_received': None,
                'date_entered': None,
                'date_reported': None
            }
    
    def generate_extraction_report(self, lines: List[Dict[str, Any]]) -> str:
        """
        Generate human-readable extraction report
        
        Args:
            lines: Document lines to process
            
        Returns:
            Formatted text report
        """
        try:
            if self.enhanced:
                results = self.library.extract_from_lines_enhanced(lines)
                return create_extraction_report(results)
            else:
                results = self.library.extract_from_lines(lines)
                # Create basic report for non-enhanced results
                return self._create_basic_report(results)
        
        except Exception as e:
            self.logger.error(f"Error generating extraction report: {e}")
            return f"Error generating report: {e}"
    
    def _create_basic_report(self, results: Dict[str, Any]) -> str:
        """Create basic report for non-enhanced extraction"""
        report_lines = []
        
        report_lines.append("=== Basic Header Extraction Report ===")
        report_lines.append("")
        
        # Patient info
        patient_infos = results.get('patient_info', [])
        report_lines.append(f"Patient Information ({len(patient_infos)} extractions):")
        
        for i, patient in enumerate(patient_infos, 1):
            report_lines.append(f"  {i}. Name: {patient.get('patient_name', 'N/A')}")
            report_lines.append(f"     Sex: {patient.get('sex', 'N/A')}")
            report_lines.append(f"     Confidence: {patient.get('confidence', 0):.3f}")
            report_lines.append("")
        
        # Specimen info
        specimen_infos = results.get('specimen_info', [])
        report_lines.append(f"Specimen Information ({len(specimen_infos)} extractions):")
        
        for i, specimen in enumerate(specimen_infos, 1):
            report_lines.append(f"  {i}. Number: {specimen.get('specimen_number', 'N/A')}")
            report_lines.append(f"     Collected: {specimen.get('date_collected', 'N/A')}")
            report_lines.append(f"     Received: {specimen.get('date_received', 'N/A')}")
            report_lines.append(f"     Confidence: {specimen.get('confidence', 0):.3f}")
            report_lines.append("")
        
        return "\n".join(report_lines)


# Factory functions for easy worker integration
def create_header_service(enhanced: bool = True) -> HeaderExtractionService:
    """Create header extraction service for worker use"""
    return HeaderExtractionService(use_enhanced=enhanced)


def extract_headers_from_classified_lines(lines: List[Dict[str, Any]], 
                                         enhanced: bool = True) -> Dict[str, Any]:
    """
    Convenience function to extract headers from classified lines
    
    Args:
        lines: Lines with role classifications
        enhanced: Whether to use enhanced extraction
    
    Returns:
        Extraction results
    """
    service = create_header_service(enhanced=enhanced)
    return service.process_document_lines(lines)


def get_patient_and_specimen_summary(lines: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Get consolidated patient and specimen summary from lines
    
    Args:
        lines: Document lines with role classifications
        
    Returns:
        Dictionary with patient_summary and specimen_summary keys
    """
    service = create_header_service(enhanced=True)
    
    return {
        'patient_summary': service.extract_patient_summary(lines),
        'specimen_summary': service.extract_specimen_summary(lines)
    }


# Celery task helper functions
def process_document_for_worker(document_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process full document data for worker task
    
    Args:
        document_data: Document with lines and metadata
        
    Returns:
        Enhanced document data with header extractions
    """
    lines = document_data.get('lines', [])
    
    # Extract header information
    header_results = extract_headers_from_classified_lines(lines, enhanced=True)
    
    # Get summaries
    summaries = get_patient_and_specimen_summary(lines)
    
    # Combine results
    enhanced_document = document_data.copy()
    enhanced_document['header_extractions'] = header_results
    enhanced_document['patient_summary'] = summaries['patient_summary']
    enhanced_document['specimen_summary'] = summaries['specimen_summary']
    
    return enhanced_document


def validate_header_extractions(extractions: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate header extraction results for quality
    
    Args:
        extractions: Header extraction results
        
    Returns:
        Validation report
    """
    service = create_header_service(enhanced=True)
    
    if hasattr(service.library, 'validate_extraction_quality'):
        return service.library.validate_extraction_quality(extractions)
    else:
        return {'overall_quality': 'unknown', 'error': 'Enhanced validation not available'}


if __name__ == '__main__':
    # Test worker integration
    print("=== Testing Worker Integration ===")
    
    # Create service
    service = create_header_service(enhanced=True)
    
    # Test data
    test_document = {
        'source_file': '/data/test_document.pdf',
        'lines': [
            {'text': 'Patient: Wilson, David (Male)', 'predicted_role': 'HEADER_PATIENT'},
            {'text': 'DOB: 01/15/1985 MRN: 987654321', 'predicted_role': 'HEADER_PATIENT'},
            {'text': 'Specimen Number: LAB2024001234', 'predicted_role': 'HEADER_SPECIMEN'},
            {'text': 'Collected: 03/20/2024 8:30 AM', 'predicted_role': 'HEADER_SPECIMEN'},
            {'text': 'Received: 03/20/2024 11:15 AM', 'predicted_role': 'HEADER_SPECIMEN'},
            {'text': 'Glucose 95 mg/dL 70-100', 'predicted_role': 'TEST_ROW'},
        ]
    }
    
    # Test full document processing
    enhanced_doc = process_document_for_worker(test_document)
    
    print("Enhanced Document Keys:", list(enhanced_doc.keys()))
    
    # Test summaries
    print("\nPatient Summary:")
    patient_summary = enhanced_doc.get('patient_summary')
    if patient_summary:
        print(f"  Name: {patient_summary.get('patient_name')}")
        print(f"  Sex: {patient_summary.get('sex')}")
        print(f"  Confidence: {patient_summary.get('confidence', 0):.3f}")
    
    print("\nSpecimen Summary:")
    specimen_summary = enhanced_doc.get('specimen_summary')
    if specimen_summary:
        print(f"  Number: {specimen_summary.get('specimen_number')}")
        print(f"  Collected: {specimen_summary.get('date_collected')}")
        print(f"  Received: {specimen_summary.get('date_received')}")
        print(f"  Confidence: {specimen_summary.get('confidence', 0):.3f}")
    
    # Test report generation
    print("\n" + "="*50)
    report = service.generate_extraction_report(test_document['lines'])
    print(report)