"""
Entity labels for document-level NER.

Defines all the field types we want to extract from lab documents.
"""

# Core entity types for comprehensive document extraction
DOCUMENT_ENTITY_LABELS = [
    # Base label
    'O',  # Outside any entity

    # Patient entities (matches review form exactly)
    'B-PATIENT_LAST_NAME', 'I-PATIENT_LAST_NAME',
    'B-PATIENT_FIRST_NAME', 'I-PATIENT_FIRST_NAME',
    'B-PATIENT_MIDDLE_NAME', 'I-PATIENT_MIDDLE_NAME',
    'B-PATIENT_DOB', 'I-PATIENT_DOB',
    'B-PATIENT_SEX', 'I-PATIENT_SEX',
    'B-PATIENT_MRN', 'I-PATIENT_MRN',
    'B-PATIENT_ADDRESS_STREET', 'I-PATIENT_ADDRESS_STREET',
    'B-PATIENT_ADDRESS_CITY', 'I-PATIENT_ADDRESS_CITY',
    'B-PATIENT_ADDRESS_STATE', 'I-PATIENT_ADDRESS_STATE',
    'B-PATIENT_ADDRESS_ZIP', 'I-PATIENT_ADDRESS_ZIP',
    'B-PATIENT_PHONE', 'I-PATIENT_PHONE',
    'B-PATIENT_AGE', 'I-PATIENT_AGE',

    # Provider entities (matches review form)
    'B-ORDERING_PROVIDER_NAME', 'I-ORDERING_PROVIDER_NAME',
    'B-PROVIDER_NPI', 'I-PROVIDER_NPI',
    'B-ORDERING_CLINIC_NAME', 'I-ORDERING_CLINIC_NAME',
    'B-ORDERING_CLINIC_ADDRESS', 'I-ORDERING_CLINIC_ADDRESS',
    'B-ORDERING_CLINIC_PHONE', 'I-ORDERING_CLINIC_PHONE',

    # Specimen entities
    'B-SPECIMEN_ID', 'I-SPECIMEN_ID',
    'B-ACCESSION_NUMBER', 'I-ACCESSION_NUMBER',
    'B-COLLECTION_DATE', 'I-COLLECTION_DATE',
    'B-COLLECTION_TIME', 'I-COLLECTION_TIME',
    'B-RECEIVED_DATE', 'I-RECEIVED_DATE',
    'B-RECEIVED_TIME', 'I-RECEIVED_TIME',
    'B-REPORTED_DATE', 'I-REPORTED_DATE',
    'B-REPORTED_TIME', 'I-REPORTED_TIME',
    'B-SPECIMEN_TYPE', 'I-SPECIMEN_TYPE',
    'B-SPECIMEN_SOURCE', 'I-SPECIMEN_SOURCE',

    # Performing lab entities
    'B-PERFORMING_LAB', 'I-PERFORMING_LAB',
    'B-LAB_CLIA', 'I-LAB_CLIA',
    'B-LAB_ADDRESS', 'I-LAB_ADDRESS',
    'B-LAB_PHONE', 'I-LAB_PHONE',
    'B-LAB_FAX', 'I-LAB_FAX',
    'B-LAB_DIRECTOR', 'I-LAB_DIRECTOR',

    # Report metadata entities
    'B-REPORT_ID', 'I-REPORT_ID',
    'B-REPORT_DATE', 'I-REPORT_DATE',
    'B-REPORT_TIME', 'I-REPORT_TIME',
    'B-PAGE_NUMBER', 'I-PAGE_NUMBER',
    'B-CLINICAL_INFO', 'I-CLINICAL_INFO',
    'B-VENDOR_ACCOUNT', 'I-VENDOR_ACCOUNT',

    # Test entities (for completeness, though we have separate model for these)
    'B-TEST_NAME', 'I-TEST_NAME',
    'B-TEST_VALUE', 'I-TEST_VALUE',
    'B-TEST_UNIT', 'I-TEST_UNIT',
    'B-TEST_REF_RANGE', 'I-TEST_REF_RANGE',
    'B-TEST_FLAG', 'I-TEST_FLAG',
    'B-PANEL_NAME', 'I-PANEL_NAME',
]

# Group entities by category for easier processing
ENTITY_CATEGORIES = {
    'patient': [
        'PATIENT_LAST_NAME', 'PATIENT_FIRST_NAME', 'PATIENT_MIDDLE_NAME',
        'PATIENT_DOB', 'PATIENT_SEX', 'PATIENT_MRN',
        'PATIENT_ADDRESS_STREET', 'PATIENT_ADDRESS_CITY', 'PATIENT_ADDRESS_STATE', 'PATIENT_ADDRESS_ZIP',
        'PATIENT_PHONE', 'PATIENT_AGE'
    ],
    'provider': [
        'ORDERING_PROVIDER_NAME', 'PROVIDER_NPI', 'ORDERING_CLINIC_NAME',
        'ORDERING_CLINIC_ADDRESS', 'ORDERING_CLINIC_PHONE'
    ],
    'specimen': [
        'SPECIMEN_ID', 'ACCESSION_NUMBER', 'COLLECTION_DATE', 'COLLECTION_TIME',
        'RECEIVED_DATE', 'RECEIVED_TIME', 'REPORTED_DATE', 'REPORTED_TIME',
        'SPECIMEN_TYPE', 'SPECIMEN_SOURCE'
    ],
    'lab': [
        'PERFORMING_LAB', 'LAB_CLIA', 'LAB_ADDRESS', 'LAB_PHONE',
        'LAB_FAX', 'LAB_DIRECTOR'
    ],
    'report': [
        'REPORT_ID', 'REPORT_DATE', 'REPORT_TIME', 'PAGE_NUMBER',
        'CLINICAL_INFO', 'VENDOR_ACCOUNT'
    ],
    'test': [
        'TEST_NAME', 'TEST_VALUE', 'TEST_UNIT', 'TEST_REF_RANGE',
        'TEST_FLAG', 'PANEL_NAME'
    ]
}

def get_entity_type(label: str) -> str:
    """Extract the entity type from a BIO label (e.g., 'B-PATIENT_NAME' -> 'PATIENT_NAME')"""
    if label == 'O':
        return 'O'
    return label[2:]  # Remove 'B-' or 'I-' prefix

def get_bio_prefix(label: str) -> str:
    """Extract the BIO prefix from a label (e.g., 'B-PATIENT_NAME' -> 'B')"""
    if label == 'O':
        return 'O'
    return label[0]  # Return 'B' or 'I'

def is_begin_label(label: str) -> bool:
    """Check if label is a begin label (B-*)"""
    return label.startswith('B-')

def is_inside_label(label: str) -> bool:
    """Check if label is an inside label (I-*)"""
    return label.startswith('I-')

def get_entity_category(entity_type: str) -> str:
    """Get the category (patient, provider, etc.) for an entity type"""
    for category, entities in ENTITY_CATEGORIES.items():
        if entity_type in entities:
            return category
    return 'unknown'