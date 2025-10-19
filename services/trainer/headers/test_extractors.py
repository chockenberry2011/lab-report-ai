#!/usr/bin/env python3
"""
Test suite for header extractors

Comprehensive testing of patient and specimen information extraction.
"""

import unittest
import json
from datetime import datetime
from typing import Dict, List

from header_extractors import (
    HeaderExtractorLibrary, PatientExtractor, SpecimenExtractor,
    PatientInfo, SpecimenInfo,
    extract_patient_name_and_sex, extract_specimen_dates
)


class TestPatientExtractor(unittest.TestCase):
    """Test patient information extraction"""
    
    def setUp(self):
        self.extractor = PatientExtractor()
    
    def test_basic_name_extraction(self):
        """Test basic name patterns"""
        test_cases = [
            ("Patient: Smith, John", "Smith, John", None),
            ("Name: Doe, Jane", "Doe, Jane", None),
            ("Patient Name: Robert Johnson", "Robert Johnson", None),
            ("Dr. Williams, Sarah", "Williams, Sarah", None),
        ]
        
        for text, expected_name, expected_sex in test_cases:
            with self.subTest(text=text):
                result = self.extractor.extract(text)
                self.assertEqual(result.patient_name, expected_name)
                self.assertEqual(result.sex, expected_sex)
                self.assertGreater(result.confidence, 0)
    
    def test_sex_extraction(self):
        """Test sex/gender extraction"""
        test_cases = [
            ("Patient: Smith, John (Male)", "Smith, John", "M"),
            ("Name: Doe, Jane F", "Doe, Jane", "F"),
            ("Johnson, Robert Male", "Johnson, Robert", "M"),
            ("Sex: Female Patient: Wilson, Mary", "Wilson, Mary", "F"),
            ("Patient: Brown, David (M)", "Brown, David", "M"),
        ]
        
        for text, expected_name, expected_sex in test_cases:
            with self.subTest(text=text):
                result = self.extractor.extract(text)
                self.assertEqual(result.patient_name, expected_name)
                self.assertEqual(result.sex, expected_sex)
    
    def test_edge_cases(self):
        """Test edge cases and error conditions"""
        edge_cases = [
            "",  # Empty string
            "Patient:",  # Label only
            "123456",  # Numbers only
            "Hospital Name: General Hospital",  # False positive
        ]
        
        for text in edge_cases:
            with self.subTest(text=text):
                result = self.extractor.extract(text)
                # Should not crash, may have no extractions
                self.assertIsInstance(result, PatientInfo)
    
    def test_name_cleaning(self):
        """Test name cleaning and normalization"""
        test_cases = [
            ("patient: SMITH,   JOHN", "Smith, John"),
            ("Name:    doe,jane", "Doe, Jane"),
            ("Patient: O'CONNOR, PATRICK", "O'Connor, Patrick"),
        ]
        
        for text, expected_name in test_cases:
            with self.subTest(text=text):
                result = self.extractor.extract(text)
                self.assertEqual(result.patient_name, expected_name)


class TestSpecimenExtractor(unittest.TestCase):
    """Test specimen information extraction"""
    
    def setUp(self):
        self.extractor = SpecimenExtractor()
    
    def test_specimen_number_extraction(self):
        """Test specimen number patterns"""
        test_cases = [
            ("Specimen Number: LAB2024001234", "LAB2024001234"),
            ("Accession: ACC123456", "ACC123456"),
            ("Lab ID: SPEC789", "SPEC789"),
            ("Sample No: S2024-0001", "S2024-0001"),
        ]
        
        for text, expected_number in test_cases:
            with self.subTest(text=text):
                result = self.extractor.extract(text)
                self.assertEqual(result.specimen_number, expected_number)
                self.assertGreater(result.confidence, 0)
    
    def test_date_extraction(self):
        """Test date extraction and parsing"""
        test_cases = [
            ("Collected: 03/14/2024", None, "2024-03-14", None, None, None),
            ("Received: 01/15/2024", None, None, "2024-01-15", None, None),
            ("Collection Date: 12/25/2023 Received: 12/26/2023", None, "2023-12-25", "2023-12-26", None, None),
            ("Entered: 2024-01-16 Reported: 2024-01-17", None, None, None, "2024-01-16", "2024-01-17"),
        ]
        
        for (text, exp_specimen, exp_collected, exp_received, 
             exp_entered, exp_reported) in test_cases:
            with self.subTest(text=text):
                result = self.extractor.extract(text)
                self.assertEqual(result.specimen_number, exp_specimen)
                self.assertEqual(result.date_collected, exp_collected)
                self.assertEqual(result.date_received, exp_received)
                self.assertEqual(result.date_entered, exp_entered)
                self.assertEqual(result.date_reported, exp_reported)
    
    def test_complex_specimen_info(self):
        """Test extraction from complex specimen lines"""
        complex_cases = [
            {
                'text': "Specimen ID: LAB2024001234 Collected: 03/14/2024 2:30 PM Received: 03/14/2024 4:15 PM",
                'expected': {
                    'specimen_number': 'LAB2024001234',
                    'date_collected': '2024-03-14',
                    'date_received': '2024-03-14'
                }
            },
            {
                'text': "Accession: ACC789 Collection: 01/15/2024 Entry: 01/16/2024 Report: 01/17/2024",
                'expected': {
                    'specimen_number': 'ACC789',
                    'date_collected': '2024-01-15',
                    'date_entered': '2024-01-16',
                    'date_reported': '2024-01-17'
                }
            }
        ]
        
        for case in complex_cases:
            with self.subTest(text=case['text']):
                result = self.extractor.extract(case['text'])
                
                for field, expected_value in case['expected'].items():
                    actual_value = getattr(result, field)
                    self.assertEqual(actual_value, expected_value, 
                                   f"Field {field}: expected {expected_value}, got {actual_value}")
    
    def test_date_format_parsing(self):
        """Test various date formats"""
        date_formats = [
            ("03/14/2024", "2024-03-14"),
            ("3/14/24", "2024-03-14"),
            ("03-14-2024", "2024-03-14"),
            ("2024-03-14", "2024-03-14"),
            ("March 14, 2024", "2024-03-14"),
            ("Mar 14, 2024", "2024-03-14"),
            ("14 March 2024", "2024-03-14"),
            ("14 Mar 2024", "2024-03-14"),
        ]
        
        for date_str, expected in date_formats:
            with self.subTest(date_str=date_str):
                test_text = f"Collected: {date_str}"
                result = self.extractor.extract(test_text)
                self.assertEqual(result.date_collected, expected)


class TestHeaderExtractorLibrary(unittest.TestCase):
    """Test the main library interface"""
    
    def setUp(self):
        self.library = HeaderExtractorLibrary()
    
    def test_extract_from_lines(self):
        """Test extraction from line data with role labels"""
        test_lines = [
            {
                'text': 'Patient: Smith, John (Male)',
                'predicted_role': 'HEADER_PATIENT'
            },
            {
                'text': 'Specimen ID: LAB123 Collected: 03/14/2024',
                'predicted_role': 'HEADER_SPECIMEN'
            },
            {
                'text': 'Glucose 95 mg/dL 70-100',
                'predicted_role': 'TEST_ROW'
            }
        ]
        
        results = self.library.extract_from_lines(test_lines)
        
        # Should have patient and specimen info
        self.assertEqual(len(results['patient_info']), 1)
        self.assertEqual(len(results['specimen_info']), 1)
        
        patient_info = results['patient_info'][0]
        self.assertEqual(patient_info['patient_name'], 'Smith, John')
        self.assertEqual(patient_info['sex'], 'M')
        
        specimen_info = results['specimen_info'][0]
        self.assertEqual(specimen_info['specimen_number'], 'LAB123')
        self.assertEqual(specimen_info['date_collected'], '2024-03-14')
    
    def test_consolidation(self):
        """Test consolidation of multiple extractions"""
        # Create multiple patient info objects
        patient_infos = [
            PatientInfo(patient_name="Smith, John", confidence=0.8),
            PatientInfo(sex="M", confidence=0.9),
            PatientInfo(patient_name="John Smith", confidence=0.6)  # Lower confidence
        ]
        
        consolidated = self.library.consolidate_patient_info(patient_infos)
        
        # Should take highest confidence name and sex
        self.assertEqual(consolidated.patient_name, "Smith, John")
        self.assertEqual(consolidated.sex, "M")
        self.assertGreater(consolidated.confidence, 0)


class TestConvenienceFunctions(unittest.TestCase):
    """Test convenience functions"""
    
    def test_extract_patient_name_and_sex(self):
        """Test quick patient extraction function"""
        name, sex = extract_patient_name_and_sex("Patient: Wilson, Mary Female")
        self.assertEqual(name, "Wilson, Mary")
        self.assertEqual(sex, "F")
    
    def test_extract_specimen_dates(self):
        """Test quick specimen extraction function"""
        dates = extract_specimen_dates("Specimen: LAB123 Collected: 03/14/2024 Received: 03/15/2024")
        
        self.assertEqual(dates['specimen_number'], 'LAB123')
        self.assertEqual(dates['date_collected'], '2024-03-14')
        self.assertEqual(dates['date_received'], '2024-03-15')


def create_test_dataset() -> List[Dict]:
    """Create a test dataset for evaluation"""
    return [
        {
            'text': 'Patient: Anderson, Michael (Male)',
            'expected_patient': {'name': 'Anderson, Michael', 'sex': 'M'}
        },
        {
            'text': 'Name: Rodriguez, Maria F DOB: 01/15/1985',
            'expected_patient': {'name': 'Rodriguez, Maria', 'sex': 'F'}
        },
        {
            'text': 'Specimen Number: LAB2024001234 Collected: 03/14/2024',
            'expected_specimen': {'number': 'LAB2024001234', 'collected': '2024-03-14'}
        },
        {
            'text': 'Accession: ACC789 Collection Date: 01/15/2024 2:30 PM Received: 01/15/2024 4:45 PM',
            'expected_specimen': {
                'number': 'ACC789',
                'collected': '2024-01-15',
                'received': '2024-01-15'
            }
        }
    ]


def run_performance_test():
    """Run performance test on extraction speed"""
    import time
    
    library = HeaderExtractorLibrary()
    test_texts = [
        "Patient: Smith, John (Male)",
        "Specimen ID: LAB123 Collected: 03/14/2024 Received: 03/15/2024"
    ] * 100  # 200 total extractions
    
    start_time = time.time()
    
    for text in test_texts:
        if 'Patient' in text:
            library.extract_patient_info(text)
        else:
            library.extract_specimen_info(text)
    
    end_time = time.time()
    elapsed = end_time - start_time
    
    print(f"Performance Test Results:")
    print(f"  Processed {len(test_texts)} extractions in {elapsed:.3f} seconds")
    print(f"  Rate: {len(test_texts) / elapsed:.1f} extractions/second")
    print(f"  Average: {elapsed / len(test_texts) * 1000:.2f} ms per extraction")


def main():
    """Run tests and demonstrations"""
    print("Running Header Extractor Tests...")
    
    # Run unit tests
    unittest.main(argv=[''], exit=False, verbosity=2)
    
    # Run performance test
    print("\n" + "="*50)
    run_performance_test()
    
    # Demonstrate functionality
    print("\n" + "="*50)
    print("Demonstration:")
    
    library = HeaderExtractorLibrary()
    
    demo_lines = [
        {'text': 'Patient: Johnson, Sarah (Female)', 'predicted_role': 'HEADER_PATIENT'},
        {'text': 'DOB: 08/23/1992 MRN: 123456789', 'predicted_role': 'HEADER_PATIENT'},
        {'text': 'Specimen ID: LAB2024005678 Collection: 03/20/2024 10:30 AM', 'predicted_role': 'HEADER_SPECIMEN'},
        {'text': 'Received: 03/20/2024 2:15 PM Entered: 03/20/2024 3:45 PM', 'predicted_role': 'HEADER_SPECIMEN'},
    ]
    
    results = library.extract_from_lines(demo_lines)
    
    print("Extracted Information:")
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()