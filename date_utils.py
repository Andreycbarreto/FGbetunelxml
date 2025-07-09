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
    
    # Remove common prefixes and suffixes
    date_str = re.sub(r'^(Data de |DT\. |EMISSÃO:?|SAÍDA:?|ENTRADA:?)\s*', '', date_str, flags=re.IGNORECASE)
    date_str = re.sub(r'\s*(h|H)\s*$', '', date_str)  # Remove trailing "h" for hours
    
    # Try different Brazilian date patterns with enhanced detection
    patterns = [
        r'(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})',  # dd/mm/yyyy or dd-mm-yyyy
        r'(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2})',   # dd/mm/yy or dd-mm-yy
        r'(\d{2})(\d{2})(\d{4})',  # ddmmyyyy (without separators)
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
                    logger.warning(f"Invalid day in date: {date_str} (day={day_int})")
                    return None
                if not (1 <= month_int <= 12):
                    logger.warning(f"Invalid month in date: {date_str} (month={month_int})")
                    return None
                if not (1900 <= year_int <= 2100):
                    logger.warning(f"Invalid year in date: {date_str} (year={year_int})")
                    return None
                
                # Create datetime object to validate the date
                dt = datetime(year_int, month_int, day_int)
                
                # Return ISO format
                iso_date = dt.strftime('%Y-%m-%d')
                logger.debug(f"Successfully converted date: {date_str} -> {iso_date}")
                return iso_date
                
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
    
    # Try American format (mm/dd/yyyy) and convert to Brazilian
    american_pattern = r'(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})'
    match = re.search(american_pattern, date_str)
    if match:
        first, second, year = match.groups()
        
        # If first > 12, it's likely day/month format (Brazilian)
        if int(first) > 12:
            day, month = first, second
        # If second > 12, it's likely month/day format (American)
        elif int(second) > 12:
            month, day = first, second
        else:
            # Ambiguous case - assume Brazilian format (dd/mm/yyyy)
            day, month = first, second
            
        try:
            day_int = int(day)
            month_int = int(month)
            year_int = int(year)
            
            if 1 <= day_int <= 31 and 1 <= month_int <= 12 and 1900 <= year_int <= 2100:
                dt = datetime(year_int, month_int, day_int)
                iso_date = dt.strftime('%Y-%m-%d')
                logger.debug(f"Converted ambiguous date: {date_str} -> {iso_date} (assumed Brazilian format)")
                return iso_date
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

def extract_emission_date_from_text(text_content: str) -> Optional[str]:
    """
    Extract emission date from document text using pattern matching
    
    Args:
        text_content: Raw text content from document
        
    Returns:
        Emission date in ISO format (yyyy-mm-dd) or None if not found
    """
    # Common patterns for emission date in Brazilian documents
    emission_patterns = [
        r'Data de Emissão[:\s]*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})',
        r'DT\.?\s*EMISSÃO[:\s]*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})',
        r'EMISSÃO[:\s]*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})',
        r'Data\s*Emissão[:\s]*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})',
        r'Dt\.\s*Emissão[:\s]*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})',
        r'Emitido\s*em[:\s]*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})',
    ]
    
    for pattern in emission_patterns:
        match = re.search(pattern, text_content, re.IGNORECASE)
        if match:
            date_str = match.group(1)
            converted_date = convert_brazilian_date_to_iso(date_str)
            if converted_date:
                logger.info(f"Found emission date from text: {date_str} -> {converted_date}")
                return converted_date
    
    logger.warning("No emission date found in text content")
    return None

def validate_and_correct_date(date_str: str, field_name: str = "date") -> Optional[str]:
    """
    Validate and correct a date string with enhanced error handling
    
    Args:
        date_str: Date string to validate
        field_name: Name of the field being validated (for logging)
        
    Returns:
        Corrected date in ISO format or None if invalid
    """
    if not date_str:
        return None
    
    # First, try normal conversion
    converted = convert_brazilian_date_to_iso(date_str)
    if converted:
        return converted
    
    # If it failed, try to clean and fix common issues
    cleaned = date_str.strip()
    
    # Fix common OCR errors
    cleaned = cleaned.replace('O', '0').replace('o', '0')  # Replace O with 0
    cleaned = cleaned.replace('I', '1').replace('l', '1')  # Replace I/l with 1
    cleaned = re.sub(r'[^\d/\-\.]', '', cleaned)  # Remove non-date characters
    
    # Try again with cleaned version
    if cleaned != date_str:
        logger.info(f"Trying to clean {field_name}: '{date_str}' -> '{cleaned}'")
        converted = convert_brazilian_date_to_iso(cleaned)
        if converted:
            logger.info(f"Successfully corrected {field_name} after cleaning")
            return converted
    
    # If still failing, try to extract just the date part
    date_match = re.search(r'(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})', cleaned)
    if date_match:
        date_part = date_match.group(1)
        logger.info(f"Extracted date part from {field_name}: '{date_part}'")
        converted = convert_brazilian_date_to_iso(date_part)
        if converted:
            return converted
    
    logger.error(f"Could not validate/correct {field_name}: '{date_str}'")
    return None