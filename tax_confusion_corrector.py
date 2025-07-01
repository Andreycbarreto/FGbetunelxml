"""
Tax Confusion Corrector
Automatically detects and corrects common tax misidentifications
Focus on IR vs INSS confusion based on known patterns
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class TaxConfusionCorrector:
    """Corrects common tax identification errors"""
    
    def __init__(self):
        # Common Brazilian tax rates for validation
        self.expected_rates = {
            'pis': 0.65,      # 0.65%
            'cofins': 3.0,    # 3.0%
            'ir': 1.5,        # 1.5%
            'inss': 11.0,     # 11.0%
            'csll': 1.0       # 1.0%
        }
    
    def detect_and_correct_confusion(self, tax_values: Dict[str, float], total_service_value: float) -> Dict[str, float]:
        """
        Detect and correct IR vs INSS confusion based on expected rates and patterns
        
        Args:
            tax_values: Dictionary with extracted tax values
            total_service_value: Total service value for rate calculation
            
        Returns:
            Corrected tax values
        """
        corrected = tax_values.copy()
        
        ir_value = tax_values.get('valor_ir', 0.0)
        inss_value = tax_values.get('valor_inss', 0.0)
        
        # If we have both values, check if they match expected patterns
        if ir_value > 0 and inss_value > 0:
            logger.info(f"Both IR ({ir_value}) and INSS ({inss_value}) found - checking rates")
            return corrected
        
        # If only one is set, check if it matches the wrong pattern
        if ir_value > 0 and inss_value == 0:
            # Check if IR value actually matches INSS rate pattern
            if total_service_value > 0:
                calculated_rate = (ir_value / total_service_value) * 100
                logger.info(f"IR rate calculated: {calculated_rate:.2f}%")
                
                # If rate is closer to INSS (11%) than IR (1.5%), it's likely swapped
                if abs(calculated_rate - self.expected_rates['inss']) < abs(calculated_rate - self.expected_rates['ir']):
                    logger.warning(f"IR value {ir_value} has rate {calculated_rate:.2f}% - closer to INSS rate (11%). Swapping!")
                    corrected['valor_inss'] = ir_value
                    corrected['valor_ir'] = 0.0
                    
        elif inss_value > 0 and ir_value == 0:
            # Check if INSS value actually matches IR rate pattern
            if total_service_value > 0:
                calculated_rate = (inss_value / total_service_value) * 100
                logger.info(f"INSS rate calculated: {calculated_rate:.2f}%")
                
                # If rate is closer to IR (1.5%) than INSS (11%), it's likely swapped
                if abs(calculated_rate - self.expected_rates['ir']) < abs(calculated_rate - self.expected_rates['inss']):
                    logger.warning(f"INSS value {inss_value} has rate {calculated_rate:.2f}% - closer to IR rate (1.5%). Swapping!")
                    corrected['valor_ir'] = inss_value
                    corrected['valor_inss'] = 0.0
        
        # Log final decision
        if corrected != tax_values:
            logger.info(f"Tax correction applied: IR {tax_values.get('valor_ir', 0)} → {corrected.get('valor_ir', 0)}, INSS {tax_values.get('valor_inss', 0)} → {corrected.get('valor_inss', 0)}")
        else:
            logger.info("No tax corrections needed")
            
        return corrected
    
    def validate_tax_rates(self, tax_values: Dict[str, float], total_service_value: float) -> Dict[str, str]:
        """
        Validate if tax rates match expected Brazilian patterns
        
        Args:
            tax_values: Dictionary with tax values
            total_service_value: Total service value
            
        Returns:
            Dictionary with validation messages
        """
        validation = {}
        
        if total_service_value <= 0:
            return {"error": "Cannot validate without service value"}
        
        for tax_name, expected_rate in self.expected_rates.items():
            value_key = f'valor_{tax_name}'
            tax_value = tax_values.get(value_key, 0.0)
            
            if tax_value > 0:
                calculated_rate = (tax_value / total_service_value) * 100
                rate_diff = abs(calculated_rate - expected_rate)
                
                if rate_diff < 0.5:  # Within 0.5% is good
                    validation[tax_name] = f"✓ Rate {calculated_rate:.2f}% matches expected {expected_rate}%"
                elif rate_diff < 2.0:  # Within 2% is acceptable
                    validation[tax_name] = f"⚠ Rate {calculated_rate:.2f}% close to expected {expected_rate}%"
                else:
                    validation[tax_name] = f"✗ Rate {calculated_rate:.2f}% differs from expected {expected_rate}%"
        
        return validation

def correct_tax_confusion(tax_values: Dict[str, float], total_service_value: float) -> Dict[str, float]:
    """
    Convenience function to correct tax confusion
    
    Args:
        tax_values: Dictionary with extracted tax values
        total_service_value: Total service value for rate validation
        
    Returns:
        Corrected tax values
    """
    corrector = TaxConfusionCorrector()
    return corrector.detect_and_correct_confusion(tax_values, total_service_value)