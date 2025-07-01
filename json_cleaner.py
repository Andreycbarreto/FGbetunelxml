"""
JSON Cleaner Utility
Helper function to clean JSON responses from GPT that may include markdown formatting
"""

import json
import logging

logger = logging.getLogger(__name__)

def clean_and_parse_json(content, fallback_data=None):
    """
    Clean and parse JSON content that may be wrapped in markdown code blocks
    
    Args:
        content (str): Raw content from GPT response
        fallback_data: Data to return if parsing fails
        
    Returns:
        Parsed JSON data or fallback_data
    """
    if not content:
        return fallback_data
    
    try:
        # Handle JSON wrapped in markdown code blocks
        cleaned_content = content.strip()
        
        if '```json' in cleaned_content:
            start = cleaned_content.find('```json') + 7
            end = cleaned_content.find('```', start)
            if end > start:
                cleaned_content = cleaned_content[start:end].strip()
        elif '```' in cleaned_content:
            start = cleaned_content.find('```') + 3
            end = cleaned_content.find('```', start)
            if end > start:
                cleaned_content = cleaned_content[start:end].strip()
        
        # Remove any remaining markdown formatting
        if cleaned_content.startswith('```') and cleaned_content.endswith('```'):
            cleaned_content = cleaned_content[3:-3].strip()
        
        return json.loads(cleaned_content)
        
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse JSON: {content[:200]}, error: {e}")
        return fallback_data
    except Exception as e:
        logger.error(f"Unexpected error parsing JSON: {e}")
        return fallback_data