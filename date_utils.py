"""
Date Utilities
Helper functions for handling Brazilian date formats and converting to PostgreSQL compatible formats
"""

import re
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)

def convert_brazilian_date_to_iso(date_str: str) -> Optional[str]:
    """
    Convert Brazilian date format (dd/mm/yyyy) to ISO format (yyyy-mm-dd)
    
    Args:
        date_str: Date string in Brazilian format (dd/mm/yyyy, dd-mm-yyyy, etc.)
        
    Returns:
        ISO date string (yyyy-mm-dd) or None if conversion fails
    """
    if not date_str or not isinstance(date_str, str):
        return None
    
    # Clean the date string
    date_str = date_str.strip()
    
    # Try different Brazilian date patterns
    patterns = [
        r'(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})',  # dd/mm/yyyy or dd-mm-yyyy
        r'(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2})',   # dd/mm/yy or dd-mm-yy
    ]
    
    for pattern in patterns:
        match = re.search(pattern, date_str)
        if match:
            day, month, year = match.groups()
            
            # Convert 2-digit year to 4-digit
            if len(year) == 2:
                year_int = int(year)
                if year_int <= 30:  # Assume 00-30 means 2000-2030
                    year = f"20{year}"
                else:  # 31-99 means 1931-1999
                    year = f"19{year}"
            
            try:
                # Validate the date
                day_int = int(day)
                month_int = int(month)
                year_int = int(year)
                
                # Basic validation
                if not (1 <= day_int <= 31):
                    logger.warning(f"Invalid day in date: {date_str}")
                    return None
                if not (1 <= month_int <= 12):
                    logger.warning(f"Invalid month in date: {date_str}")
                    return None
                if not (1900 <= year_int <= 2100):
                    logger.warning(f"Invalid year in date: {date_str}")
                    return None
                
                # Create datetime object to validate the date
                dt = datetime(year_int, month_int, day_int)
                
                # Return ISO format
                return dt.strftime('%Y-%m-%d')
                
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse date {date_str}: {e}")
                continue
    
    # Try ISO format (already correct) - only if it looks like year first
    if re.match(r'^\d{4}[/\-\.]', date_str):
        iso_pattern = r'(\d{4})[/\-\.](\d{1,2})[/\-\.](\d{1,2})'
        match = re.search(iso_pattern, date_str)
        if match:
            year, month, day = match.groups()
            try:
                dt = datetime(int(year), int(month), int(day))
                return dt.strftime('%Y-%m-%d')
            except (ValueError, TypeError):
                pass
    
    logger.warning(f"Could not parse date: {date_str}")
    return None

def clean_date_fields(data: dict) -> dict:
    """
    Clean all date fields in a data dictionary by converting Brazilian formats to ISO
    
    Args:
        data: Dictionary containing data with potential date fields
        
    Returns:
        Dictionary with cleaned date fields
    """
    date_fields = [
        'data_emissao', 'data_saida_entrada', 'data_vencimento',
        'data_competencia', 'data_prestacao_servico'
    ]
    
    for field in date_fields:
        if field in data and data[field]:
            converted_date = convert_brazilian_date_to_iso(data[field])
            if converted_date:
                data[field] = converted_date
                logger.debug(f"Converted {field}: {data[field]} -> {converted_date}")
            else:
                logger.warning(f"Could not convert {field}: {data[field]}, setting to None")
                data[field] = None
    
    return data

def format_date_for_display(iso_date: str) -> str:
    """
    Convert ISO date back to Brazilian format for display
    
    Args:
        iso_date: Date in ISO format (yyyy-mm-dd)
        
    Returns:
        Date in Brazilian format (dd/mm/yyyy)
    """
    if not iso_date:
        return ""
    
    try:
        dt = datetime.strptime(iso_date, '%Y-%m-%d')
        return dt.strftime('%d/%m/%Y')
    except (ValueError, TypeError):
        return iso_date  # Return as-is if conversion fails