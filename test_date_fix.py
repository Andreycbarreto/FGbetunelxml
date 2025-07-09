#!/usr/bin/env python3
"""
Test the date fix
"""

import sys
from datetime import datetime
from date_utils import convert_brazilian_date_to_iso, clean_date_fields

def test_date_conversion():
    print("=== TESTING DATE CONVERSION FIX ===")
    
    # Test cases
    test_cases = [
        # String dates
        "13/06/2025",
        "12/06/2025", 
        "16/06/2025",
        "2025-06-13",
        # Datetime objects
        datetime(2025, 6, 13),
        datetime(2025, 6, 12),
        # Problem case from logs
        "2025-06-13 00:00:00"
    ]
    
    print("Testing convert_brazilian_date_to_iso:")
    for test_case in test_cases:
        result = convert_brazilian_date_to_iso(test_case)
        print(f"  {test_case} -> {result}")
    
    print("\nTesting clean_date_fields:")
    test_data = {
        'data_emissao': '13/06/2025',
        'data_saida_entrada': datetime(2025, 6, 13),
        'data_vencimento': '2025-06-13 00:00:00',
        'other_field': 'test'
    }
    
    cleaned = clean_date_fields(test_data)
    print(f"  Input: {test_data}")
    print(f"  Output: {cleaned}")

if __name__ == "__main__":
    test_date_conversion()