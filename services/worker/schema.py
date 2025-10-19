"""
Lab AI Worker Output Schema - EHR-compatible dataclasses
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime


@dataclass
class Address:
    """Address information"""
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict, omitting None/empty fields"""
        result = {}
        for k, v in self.__dict__.items():
            if v is not None and v != "":
                result[k] = v
        return result


@dataclass
class Vendor:
    """Vendor/lab company information"""
    name: Optional[str] = None
    account_number: Optional[str] = None
    address: Optional[Address] = None
    phone: Optional[str] = None
    fax: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict, omitting None/empty fields
        
        >>> vendor = Vendor(name="LabCorp", phone="555-1234")
        >>> result = vendor.to_dict()
        >>> sorted(result.keys())
        ['name', 'phone']
        """
        result = {}
        for k, v in self.__dict__.items():
            if v is not None and v != "":
                if hasattr(v, 'to_dict'):
                    dict_val = v.to_dict()
                    if dict_val:  # Only include if not empty
                        result[k] = dict_val
                else:
                    result[k] = v
        return result


@dataclass
class ReportInfo:
    """Report document information"""
    id: Optional[str] = None
    page: Optional[int] = None
    page_count: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict, omitting None/empty fields"""
        result = {}
        for k, v in self.__dict__.items():
            if v is not None:
                result[k] = v
        return result


@dataclass
class PerformingLab:
    """Performing laboratory information"""
    name: Optional[str] = None
    clia: Optional[str] = None
    director: Optional[str] = None
    address: Optional[Address] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict, omitting None/empty fields"""
        result = {}
        for k, v in self.__dict__.items():
            if v is not None and v != "":
                if hasattr(v, 'to_dict'):
                    dict_val = v.to_dict()
                    if dict_val:
                        result[k] = dict_val
                else:
                    result[k] = v
        return result


@dataclass
class Patient:
    """Patient demographic information"""
    last_name: Optional[str] = None
    first_name: Optional[str] = None
    middle: Optional[str] = None
    dob: Optional[str] = None
    sex: Optional[str] = None
    mrn: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[Address] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict, omitting None/empty fields"""
        result = {}
        for k, v in self.__dict__.items():
            if v is not None and v != "":
                if hasattr(v, 'to_dict'):
                    dict_val = v.to_dict()
                    if dict_val:
                        result[k] = dict_val
                else:
                    result[k] = v
        return result


@dataclass
class OrderingLocation:
    """Ordering location information"""
    name: Optional[str] = None
    address: Optional[Address] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict, omitting None/empty fields"""
        result = {}
        for k, v in self.__dict__.items():
            if v is not None and v != "":
                if hasattr(v, 'to_dict'):
                    dict_val = v.to_dict()
                    if dict_val:
                        result[k] = dict_val
                else:
                    result[k] = v
        return result


@dataclass
class OrderingProvider:
    """Ordering provider information"""
    provider_name: Optional[str] = None
    npi: Optional[str] = None
    location: Optional[OrderingLocation] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict, omitting None/empty fields"""
        result = {}
        for k, v in self.__dict__.items():
            if v is not None and v != "":
                if hasattr(v, 'to_dict'):
                    dict_val = v.to_dict()
                    if dict_val:
                        result[k] = dict_val
                else:
                    result[k] = v
        return result


@dataclass
class Specimen:
    """Specimen information"""
    id: Optional[str] = None
    control_id: Optional[str] = None
    type: Optional[str] = None
    collected_at: Optional[str] = None
    received_at: Optional[str] = None
    entered_at: Optional[str] = None
    reported_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict, omitting None/empty fields"""
        result = {}
        for k, v in self.__dict__.items():
            if v is not None and v != "":
                result[k] = v
        return result


@dataclass
class ReportMeta:
    """Report metadata information"""
    clinical_info: Optional[str] = None
    comments: Optional[str] = None
    ordered_items: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict, omitting None/empty fields"""
        result = {}
        for k, v in self.__dict__.items():
            if v is not None and (not isinstance(v, (list, str)) or v):
                result[k] = v
        return result


@dataclass
class ReferenceRange:
    """Reference range for test values"""
    text: Optional[str] = None
    low: Optional[float] = None
    high: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict, omitting None/empty fields"""
        result = {}
        for k, v in self.__dict__.items():
            if v is not None:
                result[k] = v
        return result


@dataclass
class TestCode:
    """Test coding information"""
    loinc: Optional[str] = None
    cpt: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict, omitting None/empty fields"""
        result = {}
        for k, v in self.__dict__.items():
            if v is not None and v != "":
                result[k] = v
        return result


@dataclass
class TestRow:
    """Individual test result"""
    name: Optional[str] = None
    value: Optional[str] = None
    unit: Optional[str] = None
    reference_range: Optional[ReferenceRange] = None
    flag: Optional[str] = None
    code: Optional[TestCode] = None
    methodology: Optional[str] = None
    comments: Optional[str] = None
    observed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict, omitting None/empty fields"""
        result = {}
        for k, v in self.__dict__.items():
            if v is not None and v != "":
                if hasattr(v, 'to_dict'):
                    dict_val = v.to_dict()
                    if dict_val:
                        result[k] = dict_val
                else:
                    result[k] = v
        return result


@dataclass
class Panel:
    """Lab panel/test group"""
    name: Optional[str] = None
    code: Optional[str] = None
    comments: Optional[str] = None
    tests: List[TestRow] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict, omitting None/empty fields"""
        result = {}
        for k, v in self.__dict__.items():
            if v is not None and (not isinstance(v, (list, str)) or v):
                if k == 'tests':
                    result[k] = [test.to_dict() for test in v]
                else:
                    result[k] = v
        return result


@dataclass
class DiagnosticReport:
    """Root diagnostic report structure"""
    # NEW: EHR-compatible schema for lab reports
    vendor: Optional[Vendor] = None
    report: Optional[ReportInfo] = None
    performing_lab: Optional[PerformingLab] = None
    patient: Optional[Patient] = None
    ordering: Optional[OrderingProvider] = None
    specimen: Optional[Specimen] = None
    report_meta: Optional[ReportMeta] = None
    panels: List[Panel] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict, omitting None/empty fields
        
        Example usage:
        >>> from services.worker.schema import DiagnosticReport, Patient, Panel, TestRow
        >>> patient = Patient(first_name="John", last_name="Doe")
        >>> test = TestRow(name="Glucose", value="95", unit="mg/dL")
        >>> panel = Panel(name="Basic Metabolic Panel", tests=[test])
        >>> report = DiagnosticReport(patient=patient, panels=[panel])
        >>> result = report.to_dict()
        >>> 'patient' in result and 'panels' in result
        True
        >>> len(result['panels'][0]['tests'])
        1
        """
        result = {}
        for k, v in self.__dict__.items():
            if v is not None:
                if k == 'panels':
                    if v:  # Only include non-empty panels list
                        result[k] = [panel.to_dict() for panel in v]
                elif hasattr(v, 'to_dict'):
                    dict_val = v.to_dict()
                    if dict_val:  # Only include non-empty objects
                        result[k] = dict_val
                else:
                    result[k] = v
        return result