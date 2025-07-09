#!/usr/bin/env python3
"""
Test script for enhanced date extraction system
"""

from date_utils import (
    convert_brazilian_date_to_iso,
    validate_and_correct_date,
    extract_emission_date_from_text
)

def test_brazilian_date_conversion():
    """Test Brazilian date format conversion"""
    print("=== Testing Brazilian Date Conversion ===")
    
    test_cases = [
        ("15/03/2024", "2024-03-15"),
        ("01/01/2025", "2025-01-01"),
        ("31-12-2023", "2023-12-31"),
        ("15.03.2024", "2024-03-15"),
        ("15032024", "2024-03-15"),
        ("15/03/24", "2024-03-15"),
        ("Data de Emissão: 15/03/2024", "2024-03-15"),
        ("DT. EMISSÃO: 15/03/2024", "2024-03-15"),
        ("EMISSÃO: 15/03/2024", "2024-03-15"),
        ("15/03/2024 h", "2024-03-15"),
        ("I5/O3/2O24", "2024-03-15"),  # OCR errors
        ("invalid date", None),
        ("", None),
        (None, None)
    ]
    
    for input_date, expected in test_cases:
        result = convert_brazilian_date_to_iso(input_date)
        status = "✓" if result == expected else "✗"
        print(f"{status} '{input_date}' -> '{result}' (expected: '{expected}')")

def test_date_validation():
    """Test date validation and correction"""
    print("\n=== Testing Date Validation ===")
    
    test_cases = [
        ("15/03/2024", "2024-03-15"),
        ("I5/O3/2O24", "2024-03-15"),  # OCR errors
        ("15/03/2024 extra text", "2024-03-15"),
        ("garbage 15/03/2024 more", "2024-03-15"),
        ("completely invalid", None),
        ("", None)
    ]
    
    for input_date, expected in test_cases:
        result = validate_and_correct_date(input_date, "test_field")
        status = "✓" if result == expected else "✗"
        print(f"{status} '{input_date}' -> '{result}' (expected: '{expected}')")

def test_emission_date_extraction():
    """Test emission date extraction from text"""
    print("\n=== Testing Emission Date Extraction ===")
    
    test_texts = [
        "Data de Emissão: 15/03/2024",
        "DT. EMISSÃO: 15/03/2024",
        "EMISSÃO: 15/03/2024",
        "Data Emissão: 15/03/2024",
        "Dt. Emissão: 15/03/2024",
        "Emitido em: 15/03/2024",
        "Some text without date",
        ""
    ]
    
    for text in test_texts:
        result = extract_emission_date_from_text(text)
        status = "✓" if result else "✗"
        print(f"{status} '{text}' -> '{result}'")

def test_edge_cases():
    """Test edge cases and error handling"""
    print("\n=== Testing Edge Cases ===")
    
    # Test various invalid formats
    edge_cases = [
        "32/01/2024",  # Invalid day
        "15/13/2024",  # Invalid month
        "15/03/1800",  # Invalid year
        "00/00/0000",  # All zeros
        "15/03/99",    # 2-digit year > 30
        "15/03/25",    # 2-digit year <= 30
        "03/15/2024",  # American format (ambiguous)
        "15/03/2024 10:30",  # With time
        "2024-03-15",  # ISO format
        "15/03/2024\n",  # With newline
        "  15/03/2024  ",  # With spaces
    ]
    
    for test_case in edge_cases:
        result = convert_brazilian_date_to_iso(test_case)
        print(f"'{test_case}' -> '{result}'")

if __name__ == "__main__":
    test_brazilian_date_conversion()
    test_date_validation()
    test_emission_date_extraction()
    test_edge_cases()
    print("\n=== Date Extraction Tests Complete ===")