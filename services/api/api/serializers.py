# services/api/api/serializers.py
"""
Enhanced serializers for lab data with backward compatibility.

Exposes expanded fields for manual review UI while maintaining legacy compatibility.
"""

from typing import Optional, Dict, Any, List, Union
from pydantic import BaseModel, Field
import json
import re
from pathlib import Path

class ReferenceRange(BaseModel):
    """Reference range with structured and legacy fields."""
    # Legacy field (backward compatibility)
    reference_range: Optional[str] = None
    # New structured fields
    reference_range_text: Optional[str] = None
    reference_range_low: Optional[float] = None
    reference_range_high: Optional[float] = None

class TestCodes(BaseModel):
    """Test codes (LOINC, CPT, etc.)."""
    loinc: Optional[str] = None
    cpt: Optional[str] = None

class Address(BaseModel):
    """Address structure."""
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None

class Vendor(BaseModel):
    """Vendor/lab information."""
    name: Optional[str] = None
    account_number: Optional[str] = None
    address: Optional[Address] = None
    phone: Optional[str] = None
    fax: Optional[str] = None

class PerformingLab(BaseModel):
    """Performing laboratory information."""
    name: Optional[str] = None
    clia: Optional[str] = None
    director: Optional[str] = None
    address: Optional[Address] = None

class Patient(BaseModel):
    """Patient information."""
    last_name: Optional[str] = None
    first_name: Optional[str] = None
    middle: Optional[str] = None
    dob: Optional[str] = None
    sex: Optional[str] = None
    mrn: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[Address] = None
    age_at_collection: Optional[int] = None

class OrderingLocation(BaseModel):
    """Ordering location information."""
    name: Optional[str] = None
    address: Optional[Address] = None

class Ordering(BaseModel):
    """Ordering provider information."""
    provider_name: Optional[str] = None
    npi: Optional[str] = None
    location: Optional[OrderingLocation] = None

class Specimen(BaseModel):
    """Specimen information."""
    id: Optional[str] = None
    control_id: Optional[str] = None
    type: Optional[str] = None
    collected_at: Optional[str] = None
    received_at: Optional[str] = None
    entered_at: Optional[str] = None
    reported_at: Optional[str] = None

class Report(BaseModel):
    """Report metadata."""
    id: Optional[str] = None
    page_count: Optional[int] = None
    clinical_info: Optional[str] = None
    comments: Optional[str] = None
    ordered_items: Optional[List[str]] = None

class DocumentInfo(BaseModel):
    """Enhanced document information with structured header data."""
    vendor: Optional[Vendor] = None
    performing_lab: Optional[PerformingLab] = None
    patient: Optional[Patient] = None
    ordering: Optional[Ordering] = None
    specimen: Optional[Specimen] = None
    report: Optional[Report] = None

class EnhancedTestRow(BaseModel):
    """Enhanced test row with legacy and new fields."""
    # Original fields
    line_number: int
    text: str
    confidence: Optional[float] = None
    test_name: Optional[str] = None
    result_value: Optional[str] = None
    units: Optional[str] = None
    
    # Reference range fields (both legacy and structured)
    reference_range: Optional[str] = None  # Legacy
    reference_range_text: Optional[str] = None
    reference_range_low: Optional[float] = None
    reference_range_high: Optional[float] = None
    
    # Enhanced fields
    flag: Optional[str] = None
    flag_norm: Optional[str] = None  # Normalized flag (H/L/CRIT/ABN)
    comments: Optional[str] = None
    methodology: Optional[str] = None
    observed_at: Optional[str] = None
    codes: Optional[TestCodes] = None
    
    # Additional metadata
    page: Optional[int] = None
    y_norm: Optional[float] = None
    field_confidences: Optional[Dict[str, Any]] = None

class EnhancedPanel(BaseModel):
    """Enhanced panel with test rows."""
    id: str
    name: str
    started_at_page: Optional[int] = None
    started_at_line: Optional[int] = None
    continuity_score: Optional[float] = None
    open: Optional[bool] = None
    panel_type: Optional[str] = None
    collected_date: Optional[str] = None
    reference_lab: Optional[str] = None
    test_count: Optional[int] = None
    coherence_score: Optional[float] = None
    panel_score: Optional[float] = None
    needs_review: Optional[bool] = None
    review_reasons: Optional[List[str]] = None
    test_rows: List[EnhancedTestRow]

class EnhancedLabResult(BaseModel):
    """Enhanced lab result with structured document info and test rows."""
    document_info: DocumentInfo
    lab_panels: List[EnhancedPanel]
    processing_summary: Optional[Dict[str, Any]] = None


def normalize_flag(flag: Optional[str]) -> Dict[str, Optional[str]]:
    """Normalize flag values to standard format."""
    if not flag:
        return {"flag": None, "flag_norm": None}
    
    flag_clean = flag.strip().upper()
    flag_norm = None
    
    # Normalize common flag patterns
    if flag_clean in ["H", "HIGH", "HI"]:
        flag_norm = "H"
    elif flag_clean in ["L", "LOW", "LO"]:
        flag_norm = "L"
    elif flag_clean in ["CRIT", "CRITICAL", "PANIC"]:
        flag_norm = "CRIT"
    elif flag_clean in ["ABN", "ABNORMAL", "A"]:
        flag_norm = "ABN"
    else:
        flag_norm = flag_clean[:10]  # Limit length
    
    return {"flag": flag, "flag_norm": flag_norm}


def parse_reference_range(ref_range: Any) -> ReferenceRange:
    """Parse reference range from various formats."""
    if not ref_range:
        return ReferenceRange()
    
    # Handle string format
    if isinstance(ref_range, str):
        return ReferenceRange(
            reference_range=ref_range,
            reference_range_text=ref_range
        )
    
    # Handle structured format from EHR payload
    if isinstance(ref_range, dict):
        text = ref_range.get("text")
        low = ref_range.get("low")
        high = ref_range.get("high")
        
        return ReferenceRange(
            reference_range=text,  # Legacy field
            reference_range_text=text,
            reference_range_low=low,
            reference_range_high=high
        )
    
    # Fallback
    return ReferenceRange(reference_range=str(ref_range))


def parse_address(addr_data: Any) -> Optional[Address]:
    """Parse address from various formats."""
    if not addr_data:
        return None
    
    if isinstance(addr_data, dict):
        return Address(**{k: v for k, v in addr_data.items() if v is not None})
    
    # If it's a string, put it all in street
    if isinstance(addr_data, str):
        return Address(street=addr_data)
    
    return None


def serialize_test_row(row_data: Dict[str, Any]) -> EnhancedTestRow:
    """Serialize a test row with enhanced fields."""
    # Parse reference range
    ref_range = parse_reference_range(row_data.get("reference_range"))
    
    # Normalize flag
    flag_info = normalize_flag(row_data.get("flag"))
    
    # Parse codes
    codes = None
    codes_data = row_data.get("codes")
    if codes_data and isinstance(codes_data, dict):
        codes = TestCodes(**codes_data)
    
    return EnhancedTestRow(
        line_number=row_data.get("line_number", 0),
        text=row_data.get("text", ""),
        confidence=row_data.get("confidence"),
        test_name=row_data.get("test_name"),
        result_value=row_data.get("result_value"),
        units=row_data.get("units"),
        
        # Reference range fields
        reference_range=ref_range.reference_range,
        reference_range_text=ref_range.reference_range_text,
        reference_range_low=ref_range.reference_range_low,
        reference_range_high=ref_range.reference_range_high,
        
        # Enhanced fields
        flag=flag_info["flag"],
        flag_norm=flag_info["flag_norm"],
        comments=row_data.get("comments"),
        methodology=row_data.get("methodology"),
        observed_at=row_data.get("observed_at"),
        codes=codes,
        
        # Additional metadata
        page=row_data.get("page"),
        y_norm=row_data.get("y_norm"),
        field_confidences=row_data.get("field_confidences")
    )


def serialize_ehr_payload(ehr_data: Dict[str, Any]) -> DocumentInfo:
    """Serialize EHR payload into structured document info."""
    if not ehr_data:
        return DocumentInfo()
    
    # Parse vendor
    vendor = None
    vendor_data = ehr_data.get("vendor")
    if vendor_data:
        vendor = Vendor(
            name=vendor_data.get("name"),
            account_number=vendor_data.get("account_number"),
            address=parse_address(vendor_data.get("address")),
            phone=vendor_data.get("phone"),
            fax=vendor_data.get("fax")
        )
    
    # Parse performing lab
    performing_lab = None
    lab_data = ehr_data.get("performing_lab")
    if lab_data:
        performing_lab = PerformingLab(
            name=lab_data.get("name"),
            clia=lab_data.get("clia"),
            director=lab_data.get("director"),
            address=parse_address(lab_data.get("address"))
        )
    
    # Parse patient
    patient = None
    patient_data = ehr_data.get("patient")
    if patient_data:
        patient = Patient(
            last_name=patient_data.get("last_name"),
            first_name=patient_data.get("first_name"),
            middle=patient_data.get("middle"),
            dob=patient_data.get("dob"),
            sex=patient_data.get("sex"),
            mrn=patient_data.get("mrn"),
            phone=patient_data.get("phone"),
            address=parse_address(patient_data.get("address")),
            age_at_collection=patient_data.get("age_at_collection")
        )
    
    # Parse ordering
    ordering = None
    ordering_data = ehr_data.get("ordering")
    if ordering_data:
        location = None
        location_data = ordering_data.get("location")
        if location_data:
            location = OrderingLocation(
                name=location_data.get("name"),
                address=parse_address(location_data.get("address"))
            )
        
        ordering = Ordering(
            provider_name=ordering_data.get("provider_name"),
            npi=ordering_data.get("npi"),
            location=location
        )
    
    # Parse specimen
    specimen = None
    specimen_data = ehr_data.get("specimen")
    if specimen_data:
        specimen = Specimen(**specimen_data)
    
    # Parse report
    report = None
    report_data = ehr_data.get("report")
    if report_data:
        report = Report(**report_data)
    
    return DocumentInfo(
        vendor=vendor,
        performing_lab=performing_lab,
        patient=patient,
        ordering=ordering,
        specimen=specimen,
        report=report
    )


def merge_document_data(data: Dict[str, Any], base_document_info: DocumentInfo) -> DocumentInfo:
    """
    Merge data from flat document_info fields and top-level objects into structured DocumentInfo.

    This handles the legacy format where:
    - Patient data might be in document_info.patient_first_name, patient_last_name, etc.
    - Patient data might also be in top-level 'patient' object
    - Similar for vendor, ordering, specimen, etc.
    """
    doc_info = data.get("document_info", {})

    # Start with base document info from EHR payload (if any)
    result_data = {
        "vendor": base_document_info.vendor.dict() if base_document_info.vendor else None,
        "performing_lab": base_document_info.performing_lab.dict() if base_document_info.performing_lab else None,
        "patient": base_document_info.patient.dict() if base_document_info.patient else None,
        "ordering": base_document_info.ordering.dict() if base_document_info.ordering else None,
        "specimen": base_document_info.specimen.dict() if base_document_info.specimen else None,
        "report": base_document_info.report.dict() if base_document_info.report else None,
    }

    # Merge patient data from multiple sources
    patient_data = result_data.get("patient") or {}

    # From flat document_info fields
    if doc_info.get("patient_first_name"):
        patient_data["first_name"] = doc_info["patient_first_name"]
    if doc_info.get("patient_last_name"):
        patient_data["last_name"] = doc_info["patient_last_name"]
    if doc_info.get("patient_middle_name"):
        patient_data["middle"] = doc_info["patient_middle_name"]
    if doc_info.get("patient_dob"):
        patient_data["dob"] = doc_info["patient_dob"]
    if doc_info.get("patient_sex"):
        patient_data["sex"] = doc_info["patient_sex"]
    if doc_info.get("patient_mrn"):
        patient_data["mrn"] = doc_info["patient_mrn"]

    # From top-level patient object
    top_level_patient = data.get("patient", {})
    if top_level_patient:
        # Merge, giving preference to non-null values
        for key, value in top_level_patient.items():
            if value is not None:
                patient_data[key] = value

        # Handle address specifically
        if top_level_patient.get("address"):
            patient_data["address"] = top_level_patient["address"]

    # Set patient data if we have any
    if patient_data:
        result_data["patient"] = patient_data

    # Merge vendor data from multiple sources
    vendor_data = result_data.get("vendor") or {}

    # From flat document_info fields
    if doc_info.get("vendor_name"):
        vendor_data["name"] = doc_info["vendor_name"]
    if doc_info.get("vendor_account_number"):
        vendor_data["account_number"] = doc_info["vendor_account_number"]
    if doc_info.get("vendor_phone"):
        vendor_data["phone"] = doc_info["vendor_phone"]
    if doc_info.get("vendor_fax"):
        vendor_data["fax"] = doc_info["vendor_fax"]

    # From top-level vendor object
    top_level_vendor = data.get("vendor", {})
    if top_level_vendor:
        for key, value in top_level_vendor.items():
            if value is not None:
                vendor_data[key] = value

        if top_level_vendor.get("address"):
            vendor_data["address"] = top_level_vendor["address"]

    if vendor_data:
        result_data["vendor"] = vendor_data

    # Merge ordering data from top-level object
    top_level_ordering = data.get("ordering", {})
    if top_level_ordering:
        ordering_data = result_data.get("ordering") or {}
        for key, value in top_level_ordering.items():
            if value is not None:
                ordering_data[key] = value
        result_data["ordering"] = ordering_data

    # Merge specimen data from top-level object
    top_level_specimen = data.get("specimen", {})
    if top_level_specimen:
        specimen_data = result_data.get("specimen") or {}
        for key, value in top_level_specimen.items():
            if value is not None:
                specimen_data[key] = value
        result_data["specimen"] = specimen_data

    # Merge report data from top-level object
    top_level_report = data.get("report", {})
    if top_level_report:
        report_data = result_data.get("report") or {}
        for key, value in top_level_report.items():
            if value is not None:
                report_data[key] = value
        result_data["report"] = report_data

    # Merge performing_lab data from document_info if available
    if doc_info.get("performing_lab_name"):
        performing_lab_data = result_data.get("performing_lab") or {}
        performing_lab_data["name"] = doc_info["performing_lab_name"]
        result_data["performing_lab"] = performing_lab_data

    # Convert back to Pydantic models with data cleaning
    def clean_model_data(model_class, data):
        """Clean data for Pydantic model creation, handling type conversions."""
        if not data:
            return None

        cleaned_data = data.copy()

        # Handle specific model field type conversions
        if model_class == Report:
            # Convert ordered_items string to list if needed
            if "ordered_items" in cleaned_data and isinstance(cleaned_data["ordered_items"], str):
                # Split comma-separated values or treat as single item
                items = cleaned_data["ordered_items"].strip()
                if ',' in items:
                    cleaned_data["ordered_items"] = [item.strip() for item in items.split(',')]
                else:
                    cleaned_data["ordered_items"] = [items] if items else []

        return cleaned_data

    return DocumentInfo(
        vendor=Vendor(**clean_model_data(Vendor, result_data.get("vendor"))) if result_data.get("vendor") else None,
        performing_lab=PerformingLab(**clean_model_data(PerformingLab, result_data.get("performing_lab"))) if result_data.get("performing_lab") else None,
        patient=Patient(**clean_model_data(Patient, result_data.get("patient"))) if result_data.get("patient") else None,
        ordering=Ordering(**clean_model_data(Ordering, result_data.get("ordering"))) if result_data.get("ordering") else None,
        specimen=Specimen(**clean_model_data(Specimen, result_data.get("specimen"))) if result_data.get("specimen") else None,
        report=Report(**clean_model_data(Report, result_data.get("report"))) if result_data.get("report") else None,
    )


def serialize_lab_result(data: Dict[str, Any]) -> EnhancedLabResult:
    """Serialize complete lab result with enhanced fields."""
    # First, try to parse from EHR payload (if available)
    ehr_payload = data.get("ehr_payload", {})
    document_info = serialize_ehr_payload(ehr_payload)

    # Then, merge with data from flat document_info fields and top-level objects
    document_info = merge_document_data(data, document_info)
    
    # Parse panels
    enhanced_panels = []
    for panel_data in data.get("lab_panels", []):
        # Serialize test rows
        enhanced_test_rows = []
        for row_data in panel_data.get("test_rows", []):
            enhanced_test_rows.append(serialize_test_row(row_data))
        
        # Create enhanced panel
        enhanced_panel = EnhancedPanel(
            id=panel_data.get("id", ""),
            name=panel_data.get("name", ""),
            started_at_page=panel_data.get("started_at_page"),
            started_at_line=panel_data.get("started_at_line"),
            continuity_score=panel_data.get("continuity_score"),
            open=panel_data.get("open"),
            panel_type=panel_data.get("panel_type"),
            collected_date=panel_data.get("collected_date"),
            reference_lab=panel_data.get("reference_lab"),
            test_count=panel_data.get("test_count"),
            coherence_score=panel_data.get("coherence_score"),
            panel_score=panel_data.get("panel_score"),
            needs_review=panel_data.get("needs_review"),
            review_reasons=panel_data.get("review_reasons"),
            test_rows=enhanced_test_rows
        )
        enhanced_panels.append(enhanced_panel)
    
    return EnhancedLabResult(
        document_info=document_info,
        lab_panels=enhanced_panels,
        processing_summary=data.get("processing_summary")
    )
