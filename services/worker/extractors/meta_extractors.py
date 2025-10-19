"""
Meta extraction functions for structured lab report data
"""

import re
from typing import Dict, List, Any, Optional
from .normalize import normalize_date, normalize_phone, split_address, parse_ref_range_text


def extract_vendor(lines: List[Dict], roles: Dict[str, Any]) -> Dict[str, Any]:
    """Extract vendor/lab company information
    
    Args:
        lines: List of extracted text lines with metadata
        roles: Role classification results
        
    Returns:
        Dict matching Vendor schema fields
    """
    # NEW: Extract vendor information from page headers and lab info
    vendor_data = {
        'name': None,
        'account_number': None,
        'address': None,
        'phone': None,
        'fax': None
    }
    
    # Prioritize PAGE_HEADER and lab-related lines
    priority_roles = ['PAGE_HEADER', 'HEADER_LAB', 'SECTION_PANEL']
    
    for line in lines:
        role = line.get('role', line.get('predicted_role', 'JUNK'))
        text = line.get('text', '').strip()
        
        if not text or role not in priority_roles:
            continue
        
        # Extract lab name (look for "laboratory", "lab", "medical center")
        if not vendor_data['name']:
            lab_patterns = [
                r'([A-Z][a-z]+ (?:Laboratory|Lab|Medical Center|Health)(?:\s+[A-Z][a-z]+)*)',
                r'([A-Z][A-Z\s]+(?:LABORATORY|LAB|MEDICAL)(?:\s+[A-Z]+)*)',
                r'(Quest Diagnostics|LabCorp|BioReference|ARUP|Mayo)',
            ]
            for pattern in lab_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    vendor_data['name'] = match.group(1).strip()
                    break
        
        # Extract account number
        if not vendor_data['account_number']:
            acct_match = re.search(r'(?:Account|Acct|Client)[\s#:]*([A-Z0-9-]+)', text, re.IGNORECASE)
            if acct_match:
                vendor_data['account_number'] = acct_match.group(1)
        
        # Extract phone/fax numbers
        phone_pattern = r'(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})'
        
        if 'phone' in text.lower() and not vendor_data['phone']:
            phone_match = re.search(phone_pattern, text)
            if phone_match:
                vendor_data['phone'] = normalize_phone(phone_match.group(1))
        
        if 'fax' in text.lower() and not vendor_data['fax']:
            fax_match = re.search(phone_pattern, text)
            if fax_match:
                vendor_data['fax'] = normalize_phone(fax_match.group(1))
    
    # Extract address from multi-line context
    address_lines = []
    for line in lines:
        role = line.get('role', line.get('predicted_role', 'JUNK'))
        text = line.get('text', '').strip()
        
        if role in priority_roles and text:
            # Look for address indicators
            if re.search(r'\d+\s+\w+\s+(street|st|avenue|ave|road|rd|drive|dr|blvd)', text, re.IGNORECASE):
                address_lines.append(text)
            elif re.search(r'[A-Z]{2}\s+\d{5}', text):  # State ZIP
                address_lines.append(text)
    
    if address_lines:
        address_block = ' '.join(address_lines)
        address_parts = split_address(address_block)
        if any(address_parts.values()):
            vendor_data['address'] = address_parts
    
    return vendor_data


def extract_patient(lines: List[Dict], roles: Dict[str, Any]) -> Dict[str, Any]:
    """Extract patient demographic information
    
    Args:
        lines: List of extracted text lines
        roles: Role classification results
        
    Returns:
        Dict matching Patient schema fields
    """
    # NEW: Extract patient demographics from header sections
    patient_data = {
        'last_name': None,
        'first_name': None,
        'middle': None,
        'dob': None,
        'sex': None,
        'mrn': None,
        'phone': None,
        'address': None
    }
    
    # Focus on patient-related roles
    patient_roles = ['HEADER_PATIENT', 'PATIENT_INFO', 'DEMOGRAPHICS']
    
    for line in lines:
        role = line.get('role', line.get('predicted_role', 'JUNK'))
        text = line.get('text', '').strip()
        
        if not text:
            continue
        
        # Patient name patterns
        if role in patient_roles or 'patient' in text.lower():
            # Pattern: "Patient: Last, First Middle"
            name_match = re.search(r'(?:Patient|Name)[\s:]*([A-Z][a-z]+),\s*([A-Z][a-z]+)(?:\s+([A-Z][a-z]+))?', text, re.IGNORECASE)
            if name_match and not patient_data['last_name']:
                patient_data['last_name'] = name_match.group(1)
                patient_data['first_name'] = name_match.group(2)
                if name_match.group(3):
                    patient_data['middle'] = name_match.group(3)
            
            # Pattern: "First Last" or "First Middle Last"
            elif not patient_data['first_name']:
                simple_name = re.search(r'(?:Patient|Name)[\s:]*([A-Z][a-z]+)\s+(?:([A-Z][a-z]+)\s+)?([A-Z][a-z]+)', text, re.IGNORECASE)
                if simple_name:
                    patient_data['first_name'] = simple_name.group(1)
                    if simple_name.group(2) and simple_name.group(3):
                        patient_data['middle'] = simple_name.group(2)
                        patient_data['last_name'] = simple_name.group(3)
                    else:
                        patient_data['last_name'] = simple_name.group(3) or simple_name.group(2)
        
        # Date of birth
        if not patient_data['dob']:
            dob_match = re.search(r'(?:DOB|Date of Birth|Born)[\s:]*([^,\n]+)', text, re.IGNORECASE)
            if dob_match:
                normalized_dob = normalize_date(dob_match.group(1))
                if normalized_dob:
                    patient_data['dob'] = normalized_dob
        
        # Sex/Gender
        if not patient_data['sex']:
            sex_match = re.search(r'(?:Sex|Gender)[\s:]*([MF]|Male|Female)', text, re.IGNORECASE)
            if sex_match:
                sex_value = sex_match.group(1).upper()
                if sex_value in ['MALE', 'M']:
                    patient_data['sex'] = 'M'
                elif sex_value in ['FEMALE', 'F']:
                    patient_data['sex'] = 'F'
        
        # MRN/Patient ID
        if not patient_data['mrn']:
            mrn_patterns = [
                r'(?:MRN|Medical Record|Patient ID|ID)[\s#:]*([A-Z0-9-]+)',
                r'(?:Account|Acct)[\s#:]*([0-9-]+)',
            ]
            for pattern in mrn_patterns:
                mrn_match = re.search(pattern, text, re.IGNORECASE)
                if mrn_match:
                    patient_data['mrn'] = mrn_match.group(1)
                    break
        
        # Phone number
        if not patient_data['phone'] and ('phone' in text.lower() or role in patient_roles):
            phone_match = re.search(r'(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})', text)
            if phone_match:
                patient_data['phone'] = normalize_phone(phone_match.group(1))
    
    # Extract patient address
    address_lines = []
    for line in lines:
        role = line.get('role', line.get('predicted_role', 'JUNK'))
        text = line.get('text', '').strip()
        
        if role in patient_roles and text:
            # Look for address patterns in patient context
            if re.search(r'\d+\s+\w+\s+(street|st|avenue|ave|road|rd)', text, re.IGNORECASE):
                address_lines.append(text)
            elif re.search(r'[A-Z]{2}\s+\d{5}', text):
                address_lines.append(text)
    
    if address_lines:
        address_block = ' '.join(address_lines)
        address_parts = split_address(address_block)
        if any(address_parts.values()):
            patient_data['address'] = address_parts
    
    return patient_data


def extract_ordering(lines: List[Dict], roles: Dict[str, Any]) -> Dict[str, Any]:
    """Extract ordering provider information
    
    Args:
        lines: List of extracted text lines
        roles: Role classification results
        
    Returns:
        Dict matching OrderingProvider schema fields
    """
    # NEW: Extract ordering physician/provider information
    ordering_data = {
        'provider_name': None,
        'npi': None,
        'location': None
    }
    
    # Look for ordering provider sections
    ordering_roles = ['HEADER_PHYSICIAN', 'ORDERING_PROVIDER', 'PHYSICIAN_INFO']
    
    for line in lines:
        role = line.get('role', line.get('predicted_role', 'JUNK'))
        text = line.get('text', '').strip()
        
        if not text:
            continue
        
        # Provider name
        if not ordering_data['provider_name']:
            provider_patterns = [
                r'(?:Ordering|Referring|Physician|Provider|Dr|MD)[\s:]*([A-Z][a-z]+(?:,?\s+[A-Z][a-z.]+)*(?:\s+MD|DO)?)',
                r'(?:Ordered by|Referring)[\s:]*([A-Z][a-z]+\s+[A-Z][a-z]+)',
            ]
            for pattern in provider_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    ordering_data['provider_name'] = match.group(1).strip()
                    break
        
        # NPI number
        if not ordering_data['npi']:
            npi_match = re.search(r'\bNPI\s*[:#]?\s*(\d{10})\b', text, re.IGNORECASE)
            if npi_match:
                ordering_data['npi'] = npi_match.group(1)
    
    # Extract ordering location
    location_lines = []
    for line in lines:
        role = line.get('role', line.get('predicted_role', 'JUNK'))
        text = line.get('text', '').strip()
        
        if role in ordering_roles and text:
            # Look for clinic/hospital names
            if re.search(r'(clinic|hospital|medical center|health|practice)', text, re.IGNORECASE):
                location_lines.append(text)
            elif re.search(r'\d+\s+\w+\s+(street|st|avenue|ave)', text, re.IGNORECASE):
                location_lines.append(text)
    
    if location_lines:
        # Extract location name and address
        location_name = None
        address_lines = []
        
        for loc_text in location_lines:
            if re.search(r'(clinic|hospital|medical center|health|practice)', loc_text, re.IGNORECASE):
                if not location_name:
                    location_name = loc_text
            elif re.search(r'\d+\s+\w+', loc_text):
                address_lines.append(loc_text)
        
        location_data = {}
        if location_name:
            location_data['name'] = location_name
        
        if address_lines:
            address_block = ' '.join(address_lines)
            address_parts = split_address(address_block)
            if any(address_parts.values()):
                location_data['address'] = address_parts
        
        if location_data:
            ordering_data['location'] = location_data
    
    return ordering_data


def extract_specimen(lines: List[Dict], roles: Dict[str, Any]) -> Dict[str, Any]:
    """Extract specimen information
    
    Args:
        lines: List of extracted text lines
        roles: Role classification results
        
    Returns:
        Dict matching Specimen schema fields
    """
    # NEW: Extract specimen collection and processing information
    specimen_data = {
        'id': None,
        'control_id': None,
        'type': None,
        'collected_at': None,
        'received_at': None,
        'entered_at': None,
        'reported_at': None
    }
    
    # Focus on specimen-related roles
    specimen_roles = ['HEADER_SPECIMEN', 'SPECIMEN_INFO', 'COLLECTION_INFO']
    
    for line in lines:
        role = line.get('role', line.get('predicted_role', 'JUNK'))
        text = line.get('text', '').strip()
        
        if not text:
            continue
        
        # Specimen ID/Accession number
        if not specimen_data['id']:
            id_match = re.search(r'\b(Accession|Specimen(?:\s*ID)?)\s*[:#]\s*([A-Z0-9-]+)', text, re.IGNORECASE)
            if id_match:
                specimen_data['id'] = id_match.group(2)
        
        # Control ID
        if not specimen_data['control_id']:
            control_match = re.search(r'(?:Control|QC)[\s#:]*([A-Z0-9-]+)', text, re.IGNORECASE)
            if control_match:
                specimen_data['control_id'] = control_match.group(1)
        
        # Specimen type
        if not specimen_data['type']:
            type_patterns = [
                r'(?:Specimen|Sample)[\s:]*([A-Za-z\s]+?)(?:\s|$|,)',
                r'(Blood|Serum|Plasma|Urine|Stool|Sputum|CSF|Tissue)',
            ]
            for pattern in type_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    specimen_type = match.group(1).strip()
                    if specimen_type and len(specimen_type) < 50:  # Reasonable length
                        specimen_data['type'] = specimen_type
                        break
        
        # Collection date
        if not specimen_data['collected_at']:
            collected_match = re.search(r'(?:Collected|Collection)[\s:]*([^,\n]+)', text, re.IGNORECASE)
            if collected_match:
                normalized_date = normalize_date(collected_match.group(1))
                if normalized_date:
                    specimen_data['collected_at'] = normalized_date
        
        # Received date
        if not specimen_data['received_at']:
            received_match = re.search(r'(?:Received)[\s:]*([^,\n]+)', text, re.IGNORECASE)
            if received_match:
                normalized_date = normalize_date(received_match.group(1))
                if normalized_date:
                    specimen_data['received_at'] = normalized_date
        
        # Entered date
        if not specimen_data['entered_at']:
            entered_match = re.search(r'(?:Entered)[\s:]*([^,\n]+)', text, re.IGNORECASE)
            if entered_match:
                normalized_date = normalize_date(entered_match.group(1))
                if normalized_date:
                    specimen_data['entered_at'] = normalized_date
        
        # Reported date
        if not specimen_data['reported_at']:
            reported_patterns = [
                r'(?:Reported|Report Date)[\s:]*([^,\n]+)',
                r'(?:Final|Finalized)[\s:]*([^,\n]+)',
            ]
            for pattern in reported_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    normalized_date = normalize_date(match.group(1))
                    if normalized_date:
                        specimen_data['reported_at'] = normalized_date
                        break
    
    return specimen_data


def extract_report_meta(lines: List[Dict], roles: Dict[str, Any]) -> Dict[str, Any]:
    """Extract report metadata and clinical information
    
    Args:
        lines: List of extracted text lines
        roles: Role classification results
        
    Returns:
        Dict matching ReportMeta schema fields
    """
    # NEW: Extract clinical info, comments, and ordered items
    meta_data = {
        'clinical_info': None,
        'comments': None,
        'ordered_items': []
    }
    
    # Look for clinical information sections
    clinical_roles = ['CLINICAL_INFO', 'COMMENTS', 'NOTES']
    
    clinical_lines = []
    comment_lines = []
    ordered_items = []
    
    for line in lines:
        role = line.get('role', line.get('predicted_role', 'JUNK'))
        text = line.get('text', '').strip()
        
        if not text:
            continue
        
        # Clinical information
        if re.search(r'clinical\s+information', text, re.IGNORECASE):
            # Start collecting clinical info
            clinical_lines.append(text)
        elif clinical_lines and role in ['CLINICAL_INFO', 'FREE_TEXT']:
            # Continue collecting if we started
            clinical_lines.append(text)
        
        # Comments
        if re.search(r'(?:comments|general\s+comments|notes)', text, re.IGNORECASE):
            comment_lines.append(text)
        elif comment_lines and role in ['COMMENTS', 'FREE_TEXT']:
            comment_lines.append(text)
        
        # Ordered items/tests
        if re.search(r'(?:ordered|requested|tests?\s+ordered)', text, re.IGNORECASE):
            # Extract test names from ordered section
            test_match = re.findall(r'([A-Z][A-Za-z\s]+(?:Panel|Test|Profile|Screen))', text)
            ordered_items.extend(test_match)
    
    # Process collected data
    if clinical_lines:
        # Clean up and join clinical info
        cleaned_lines = []
        for line in clinical_lines:
            # Remove "Clinical Information:" prefix if present
            cleaned = re.sub(r'^clinical\s+information[\s:]*', '', line, flags=re.IGNORECASE)
            if cleaned.strip():
                cleaned_lines.append(cleaned.strip())
        
        if cleaned_lines:
            meta_data['clinical_info'] = ' '.join(cleaned_lines)
    
    if comment_lines:
        # Clean up and join comments
        cleaned_lines = []
        for line in comment_lines:
            # Remove "Comments:" prefix if present
            cleaned = re.sub(r'^(?:comments|general\s+comments|notes)[\s:]*', '', line, flags=re.IGNORECASE)
            if cleaned.strip():
                cleaned_lines.append(cleaned.strip())
        
        if cleaned_lines:
            meta_data['comments'] = ' '.join(cleaned_lines)
    
    if ordered_items:
        # Remove duplicates and clean up
        unique_items = list(set(ordered_items))
        meta_data['ordered_items'] = [item.strip() for item in unique_items if item.strip()]
    
    return meta_data