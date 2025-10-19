"""
Header Extractors Package

Scoped extractors for medical document headers:
- Patient information (name, sex) from HEADER_PATIENT lines
- Specimen information (number, dates) from HEADER_SPECIMEN lines

Enhanced with medical lexicons for improved accuracy.
"""

from .header_extractors import (
    HeaderExtractorLibrary, PatientExtractor, SpecimenExtractor,
    PatientInfo, SpecimenInfo,
    extract_patient_name_and_sex, extract_specimen_dates,
    load_header_library
)

from .enhanced_extractors import (
    EnhancedHeaderExtractorLibrary, EnhancedPatientExtractor, EnhancedSpecimenExtractor,
    EnhancedExtractionResult, create_extraction_report,
    load_enhanced_library
)

from .lexicons import (
    LexiconManager, NameLexicon, MedicalLexicon, DateLexicon,
    load_lexicon_manager
)

from .worker_integration import (
    HeaderExtractionService, create_header_service,
    extract_headers_from_classified_lines, get_patient_and_specimen_summary,
    process_document_for_worker, validate_header_extractions
)

__version__ = "1.0.0"
__all__ = [
    # Core extractors
    "HeaderExtractorLibrary", "PatientExtractor", "SpecimenExtractor",
    "PatientInfo", "SpecimenInfo",
    "extract_patient_name_and_sex", "extract_specimen_dates",
    "load_header_library",
    
    # Enhanced extractors
    "EnhancedHeaderExtractorLibrary", "EnhancedPatientExtractor", "EnhancedSpecimenExtractor", 
    "EnhancedExtractionResult", "create_extraction_report",
    "load_enhanced_library",
    
    # Lexicons
    "LexiconManager", "NameLexicon", "MedicalLexicon", "DateLexicon",
    "load_lexicon_manager",
    
    # Worker integration
    "HeaderExtractionService", "create_header_service",
    "extract_headers_from_classified_lines", "get_patient_and_specimen_summary", 
    "process_document_for_worker", "validate_header_extractions"
]