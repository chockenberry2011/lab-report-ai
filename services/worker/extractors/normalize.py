"""
Shared normalization utilities for meta extraction
"""

import re
from typing import Optional, Dict, Any
from datetime import datetime


def normalize_date(s: str) -> Optional[str]:
    """Normalize date string to ISO 8601 date or datetime format
    
    >>> normalize_date("01/15/2024")
    '2024-01-15'
    >>> normalize_date("Jan 15, 2024")
    '2024-01-15'
    >>> normalize_date("15-Jan-24")
    '2024-01-15'
    >>> normalize_date("2024-01-15 14:30:00")
    '2024-01-15T14:30:00'
    >>> normalize_date("01/15/2024 2:30 PM")
    '2024-01-15T14:30:00'
    >>> normalize_date("Dec 25, 2023 at 9:15 AM")
    '2023-12-25T09:15:00'
    >>> normalize_date("invalid")
    
    """
    if not s or not isinstance(s, str):
        return None
    
    s = s.strip()
    
    # First check for datetime patterns (date + time)
    datetime_result = _parse_datetime(s)
    if datetime_result:
        return datetime_result
    
    # Common date-only patterns to try
    patterns = [
        # MM/DD/YYYY or MM/DD/YY
        (r'(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})', lambda m: _parse_mdy(m.groups())),
        # DD/MM/YYYY (less common in US but try)
        (r'(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})', lambda m: _parse_dmy_if_makes_sense(m.groups())),
        # YYYY-MM-DD (ISO format)
        (r'(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})', lambda m: _parse_ymd(m.groups())),
        # Month DD, YYYY
        (r'(\w+)\s+(\d{1,2}),?\s+(\d{4})', lambda m: _parse_month_name(m.groups())),
        # DD-Mon-YY or DD Mon YYYY
        (r'(\d{1,2})[/\-.\s](\w+)[/\-.\s](\d{2,4})', lambda m: _parse_day_month_year(m.groups())),
    ]
    
    for pattern, parser in patterns:
        match = re.search(pattern, s, re.IGNORECASE)
        if match:
            try:
                result = parser(match)
                if result:
                    return result
            except (ValueError, IndexError):
                continue
    
    return None


def _parse_datetime(s: str) -> Optional[str]:
    """Parse datetime strings to ISO 8601 format"""
    # Pattern for ISO datetime: YYYY-MM-DD HH:MM:SS
    iso_datetime = re.search(r'(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})\s+(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?', s)
    if iso_datetime:
        year, month, day, hour, minute = iso_datetime.groups()[:5]
        second = iso_datetime.group(6) or '00'
        try:
            year, month, day = int(year), int(month), int(day)
            hour, minute, second = int(hour), int(minute), int(second)
            if (1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31 and 
                0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
                return f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:{second:02d}"
        except ValueError:
            pass
    
    # Pattern for date with 12-hour time: MM/DD/YYYY H:MM AM/PM
    datetime_12h = re.search(r'(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})\s+(\d{1,2}):(\d{1,2})\s*(AM|PM)', s, re.IGNORECASE)
    if datetime_12h:
        month, day, year, hour, minute, ampm = datetime_12h.groups()
        try:
            year, month, day = int(year), int(month), int(day)
            hour, minute = int(hour), int(minute)
            
            # Handle 2-digit years
            if year < 100:
                year = 2000 + year if year < 50 else 1900 + year
            
            # Convert to 24-hour format
            if ampm.upper() == 'PM' and hour != 12:
                hour += 12
            elif ampm.upper() == 'AM' and hour == 12:
                hour = 0
                
            if (1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31 and 
                0 <= hour <= 23 and 0 <= minute <= 59):
                return f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:00"
        except ValueError:
            pass
    
    # Pattern for Month DD, YYYY at H:MM AM/PM
    month_datetime = re.search(r'(\w+)\s+(\d{1,2}),?\s+(\d{4})\s+(?:at\s+)?(\d{1,2}):(\d{1,2})\s*(AM|PM)', s, re.IGNORECASE)
    if month_datetime:
        month_str, day, year, hour, minute, ampm = month_datetime.groups()
        try:
            day, year = int(day), int(year)
            hour, minute = int(hour), int(minute)
            
            month_names = {
                'jan': 1, 'january': 1, 'feb': 2, 'february': 2, 'mar': 3, 'march': 3,
                'apr': 4, 'april': 4, 'may': 5, 'jun': 6, 'june': 6, 'jul': 7, 'july': 7,
                'aug': 8, 'august': 8, 'sep': 9, 'sept': 9, 'september': 9,
                'oct': 10, 'october': 10, 'nov': 11, 'november': 11, 'dec': 12, 'december': 12,
            }
            
            month = month_names.get(month_str.lower())
            if not month:
                return None
                
            # Convert to 24-hour format
            if ampm.upper() == 'PM' and hour != 12:
                hour += 12
            elif ampm.upper() == 'AM' and hour == 12:
                hour = 0
                
            if (1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31 and 
                0 <= hour <= 23 and 0 <= minute <= 59):
                return f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:00"
        except ValueError:
            pass
    
    return None


def _parse_mdy(groups) -> Optional[str]:
    """Parse MM/DD/YYYY format"""
    month, day, year = groups
    month, day = int(month), int(day)
    year = int(year)
    
    # Handle 2-digit years
    if year < 100:
        year = 2000 + year if year < 50 else 1900 + year
    
    if 1 <= month <= 12 and 1 <= day <= 31 and 1900 <= year <= 2100:
        return f"{year:04d}-{month:02d}-{day:02d}"
    return None


def _parse_dmy_if_makes_sense(groups) -> Optional[str]:
    """Parse DD/MM/YYYY if it makes sense (day > 12)"""
    day, month, year = groups
    day, month = int(day), int(month)
    year = int(year)
    
    # Only use DMY if day > 12 (can't be month)
    if day > 12 and 1 <= month <= 12 and 1900 <= year <= 2100:
        return f"{year:04d}-{month:02d}-{day:02d}"
    return None


def _parse_ymd(groups) -> Optional[str]:
    """Parse YYYY-MM-DD format"""
    year, month, day = groups
    year, month, day = int(year), int(month), int(day)
    
    if 1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
        return f"{year:04d}-{month:02d}-{day:02d}"
    return None


def _parse_month_name(groups) -> Optional[str]:
    """Parse 'Month DD, YYYY' format"""
    month_str, day, year = groups
    day, year = int(day), int(year)
    
    month_names = {
        'jan': 1, 'january': 1,
        'feb': 2, 'february': 2,
        'mar': 3, 'march': 3,
        'apr': 4, 'april': 4,
        'may': 5,
        'jun': 6, 'june': 6,
        'jul': 7, 'july': 7,
        'aug': 8, 'august': 8,
        'sep': 9, 'sept': 9, 'september': 9,
        'oct': 10, 'october': 10,
        'nov': 11, 'november': 11,
        'dec': 12, 'december': 12,
    }
    
    month = month_names.get(month_str.lower())
    if month and 1 <= day <= 31 and 1900 <= year <= 2100:
        return f"{year:04d}-{month:02d}-{day:02d}"
    return None


def _parse_day_month_year(groups) -> Optional[str]:
    """Parse 'DD Mon YY' format"""
    day, month_str, year = groups
    day, year = int(day), int(year)
    
    # Handle 2-digit years
    if year < 100:
        year = 2000 + year if year < 50 else 1900 + year
    
    month_names = {
        'jan': 1, 'january': 1,
        'feb': 2, 'february': 2,
        'mar': 3, 'march': 3,
        'apr': 4, 'april': 4,
        'may': 5,
        'jun': 6, 'june': 6,
        'jul': 7, 'july': 7,
        'aug': 8, 'august': 8,
        'sep': 9, 'sept': 9, 'september': 9,
        'oct': 10, 'october': 10,
        'nov': 11, 'november': 11,
        'dec': 12, 'december': 12,
    }
    
    month = month_names.get(month_str.lower())
    if month and 1 <= day <= 31 and 1900 <= year <= 2100:
        return f"{year:04d}-{month:02d}-{day:02d}"
    return None


def normalize_phone(s: str) -> Optional[str]:
    """Normalize phone number to (XXX) XXX-XXXX format
    
    >>> normalize_phone("(555) 123-4567")
    '(555) 123-4567'
    >>> normalize_phone("555.123.4567")
    '(555) 123-4567'
    >>> normalize_phone("5551234567")
    '(555) 123-4567'
    >>> normalize_phone("1-555-123-4567")
    '(555) 123-4567'
    >>> normalize_phone("555 123 4567")
    '(555) 123-4567'
    >>> normalize_phone("invalid")
    
    >>> normalize_phone("555-1234")
    
    """
    if not s or not isinstance(s, str):
        return None
    
    # Extract digits only
    digits = re.sub(r'[^\d]', '', s)
    
    # Handle US numbers (10 or 11 digits)
    if len(digits) == 11 and digits.startswith('1'):
        digits = digits[1:]  # Remove country code
    elif len(digits) == 10:
        pass  # Good as is
    else:
        return None  # Invalid length
    
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    
    return None


def split_address(block: str) -> Dict[str, Optional[str]]:
    """Split address block into components - robust city/state/zip parsing
    
    >>> split_address("123 Main St, Anytown, ST 12345")
    {'street': '123 Main St', 'city': 'Anytown', 'state': 'ST', 'zip': '12345'}
    >>> split_address("456 Oak Ave\\nSomecity ST 67890")
    {'street': '456 Oak Ave', 'city': 'Somecity', 'state': 'ST', 'zip': '67890'}
    >>> split_address("789 Pine St, Springfield, IL 62701")
    {'street': '789 Pine St', 'city': 'Springfield', 'state': 'IL', 'zip': '62701'}
    >>> split_address("New York, NY 10001")
    {'street': None, 'city': 'New York', 'state': 'NY', 'zip': '10001'}
    >>> split_address("Boston MA 02101")
    {'street': None, 'city': 'Boston', 'state': 'MA', 'zip': '02101'}
    >>> split_address("1600 Pennsylvania Ave")
    {'street': '1600 Pennsylvania Ave', 'city': None, 'state': None, 'zip': None}
    """
    if not block or not isinstance(block, str):
        return {'street': None, 'city': None, 'state': None, 'zip': None}
    
    # Normalize whitespace and line breaks
    normalized = re.sub(r'\s+', ' ', block.strip())
    
    # Try to extract ZIP code first (most reliable)
    zip_match = re.search(r'\b(\d{5}(?:-\d{4})?)\b', normalized)
    zip_code = zip_match.group(1) if zip_match else None
    
    if zip_code:
        # Remove ZIP from string for further parsing
        before_zip = normalized[:zip_match.start()].strip()
    else:
        before_zip = normalized
    
    # Try to extract state (2-letter abbreviation before ZIP)
    state = None
    if zip_code:
        state_match = re.search(r'\b([A-Z]{2})\s*$', before_zip)
        if state_match:
            state = state_match.group(1)
            before_zip = before_zip[:state_match.start()].strip()
    
    # Split remaining into street and city
    # Look for common patterns - split on comma or newline
    parts = re.split(r'[,\n]+', before_zip)
    parts = [p.strip() for p in parts if p.strip()]
    
    # If we have exactly one part and a state was found, 
    # try to split on spaces to separate city from the end
    if len(parts) == 1 and state:
        # Try to find city name at the end of the string before state
        remaining = parts[0]
        words = remaining.split()
        if len(words) > 1:
            # Check if this looks like "City Name" with no street address
            has_street_indicators = any(
                re.search(r'\d', word) or 
                word.lower() in ['st', 'street', 'ave', 'avenue', 'rd', 'road', 'dr', 'drive', 'blvd', 'boulevard', 'ln', 'lane']
                for word in words
            )
            
            if not has_street_indicators:
                # Looks like just a city name, no street
                street = None
                city = remaining
            else:
                # Has street indicators, try to separate
                # Heuristic: if last word is likely a city (no numbers), split there
                if not re.search(r'\d', words[-1]) and len(words[-1]) > 2:
                    street = ' '.join(words[:-1])
                    city = words[-1]
                else:
                    # Keep as street
                    street = remaining
                    city = None
        else:
            # Single word - could be street or city
            if re.search(r'\d', remaining):
                street = remaining
                city = None
            else:
                street = None
                city = remaining
    elif len(parts) >= 2:
        street = parts[0]
        city = parts[1] if len(parts) == 2 else parts[-1]  # Second part or last part before state/zip
    elif len(parts) == 1:
        # Try to detect if it's a street or city
        if re.search(r'\d', parts[0]):  # Has numbers, likely street
            street = parts[0]
            city = None
        else:
            street = None
            city = parts[0]
    else:
        street = None
        city = None
    
    return {
        'street': street,
        'city': city,
        'state': state,
        'zip': zip_code
    }


def parse_ref_range_text(s: str) -> Dict[str, Any]:
    """Parse reference range text into components - collect low/high if pattern matches
    
    >>> parse_ref_range_text("70-100 mg/dL")
    {'text': '70-100 mg/dL', 'low': 70.0, 'high': 100.0}
    >>> parse_ref_range_text("<5.0")
    {'text': '<5.0', 'low': None, 'high': 5.0}
    >>> parse_ref_range_text("≥ 40")
    {'text': '≥ 40', 'low': 40.0, 'high': None}
    >>> parse_ref_range_text(">40")
    {'text': '>40', 'low': 40.0, 'high': None}
    >>> parse_ref_range_text("≤ 7.0")
    {'text': '≤ 7.0', 'low': None, 'high': 7.0}
    >>> parse_ref_range_text("2.5 - 4.0")
    {'text': '2.5 - 4.0', 'low': 2.5, 'high': 4.0}
    >>> parse_ref_range_text("Normal")
    {'text': 'Normal', 'low': None, 'high': None}
    >>> parse_ref_range_text("70–99 (using en-dash)")
    {'text': '70–99 (using en-dash)', 'low': 70.0, 'high': 99.0}
    """
    if not s or not isinstance(s, str):
        return {'text': None, 'low': None, 'high': None}
    
    text = s.strip()
    result = {'text': text, 'low': None, 'high': None}
    
    # Pattern: number - number (with various dash types)
    range_match = re.search(r'([\d.]+)\s*[-–—]\s*([\d.]+)', text)
    if range_match:
        try:
            result['low'] = float(range_match.group(1))
            result['high'] = float(range_match.group(2))
            return result
        except ValueError:
            pass
    
    # Pattern: ≥ number or >= number or > number (greater than or equal)
    greater_equal = re.search(r'(?:≥|>=)\s*([\d.]+)', text)
    if greater_equal:
        try:
            result['low'] = float(greater_equal.group(1))
            return result
        except ValueError:
            pass
    
    # Pattern: > number (greater than)
    greater_than = re.search(r'>\s*([\d.]+)', text)
    if greater_than:
        try:
            result['low'] = float(greater_than.group(1))
            return result
        except ValueError:
            pass
    
    # Pattern: ≤ number or <= number or < number (less than or equal)
    less_equal = re.search(r'(?:≤|<=)\s*([\d.]+)', text)
    if less_equal:
        try:
            result['high'] = float(less_equal.group(1))
            return result
        except ValueError:
            pass
    
    # Pattern: < number (less than)
    less_than = re.search(r'<\s*([\d.]+)', text)
    if less_than:
        try:
            result['high'] = float(less_than.group(1))
            return result
        except ValueError:
            pass
    
    # Pattern: single number (assume it's a target value, set as both low and high)
    single_number = re.search(r'^\s*([\d.]+)\s*$', text)
    if single_number:
        try:
            value = float(single_number.group(1))
            result['low'] = value
            result['high'] = value
            return result
        except ValueError:
            pass
    
    return result


if __name__ == "__main__":
    """Run doctests for normalize.py functions"""
    import doctest
    
    print("Running doctests for normalize.py...")
    print("=" * 50)
    
    # Run doctests with verbose output
    results = doctest.testmod(verbose=True)
    
    print("=" * 50)
    if results.failed == 0:
        print(f"✅ All {results.attempted} tests passed!")
    else:
        print(f"❌ {results.failed} of {results.attempted} tests failed!")
    
    print("\nTesting additional edge cases...")
    
    # Additional manual tests
    test_cases = [
        # Date tests
        ("normalize_date", normalize_date, [
            ("12/25/2023 11:59 PM", "2023-12-25T23:59:00"),
            ("2024-03-15 08:30:15", "2024-03-15T08:30:15"),
            ("Mar 10, 2024 at 12:00 AM", "2024-03-10T00:00:00"),
            ("", None),
            ("not a date", None)
        ]),
        
        # Phone tests  
        ("normalize_phone", normalize_phone, [
            ("800-555-1212", "(800) 555-1212"),
            ("18005551212", "(800) 555-1212"),  
            ("(800)555-1212", "(800) 555-1212"),
            ("800 555 1212", "(800) 555-1212"),
            ("123", None),
            ("", None)
        ]),
        
        # Address tests
        ("split_address", split_address, [
            ("Miami, FL 33101", {'street': None, 'city': 'Miami', 'state': 'FL', 'zip': '33101'}),
            ("Los Angeles CA 90210", {'street': None, 'city': 'Los Angeles', 'state': 'CA', 'zip': '90210'}),
            ("", {'street': None, 'city': None, 'state': None, 'zip': None})
        ]),
        
        # Reference range tests
        ("parse_ref_range_text", parse_ref_range_text, [
            ("≥40", {'text': '≥40', 'low': 40.0, 'high': None}),
            ("<=7", {'text': '<=7', 'low': None, 'high': 7.0}),
            ("5.5", {'text': '5.5', 'low': 5.5, 'high': 5.5}),
            ("negative", {'text': 'negative', 'low': None, 'high': None}),
            ("", {'text': None, 'low': None, 'high': None})
        ])
    ]
    
    failed_manual = 0
    total_manual = 0
    
    for func_name, func, cases in test_cases:
        print(f"\nTesting {func_name}:")
        for input_val, expected in cases:
            total_manual += 1
            try:
                result = func(input_val)
                if result == expected:
                    print(f"  ✅ {func_name}({repr(input_val)}) = {repr(result)}")
                else:
                    print(f"  ❌ {func_name}({repr(input_val)}) = {repr(result)}, expected {repr(expected)}")
                    failed_manual += 1
            except Exception as e:
                print(f"  ❌ {func_name}({repr(input_val)}) raised {type(e).__name__}: {e}")
                failed_manual += 1
    
    print(f"\nManual tests: {total_manual - failed_manual}/{total_manual} passed")
    
    overall_failed = results.failed + failed_manual
    overall_total = results.attempted + total_manual
    
    print(f"\nOverall: {overall_total - overall_failed}/{overall_total} tests passed")
    if overall_failed == 0:
        print("🎉 All normalize.py tests passed!")
    else:
        print(f"⚠️  {overall_failed} tests failed")
        exit(1)