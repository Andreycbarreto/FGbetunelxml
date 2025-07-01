"""
Final Tax Processor
Comprehensive solution that combines precise reading with automatic confusion correction
"""

import os
import json
import logging
from typing import Dict, Any
from openai import OpenAI

logger = logging.getLogger(__name__)

class FinalTaxProcessor:
    """Final solution for accurate tax extraction with automatic correction"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        
        # Known Brazilian tax rates for validation
        self.tax_rates = {
            'pis': 0.65,      # 0.65%
            'cofins': 3.0,    # 3.0%
            'ir': 1.5,        # 1.5%
            'inss': 11.0,     # 11.0%
            'csll': 1.0       # 1.0%
        }
    
    def process_taxes_completely(self, base64_image: str, total_service_value: float = 0.0) -> Dict[str, float]:
        """
        Complete tax processing with reading and automatic correction
        
        Args:
            base64_image: Base64 encoded image of the document
            total_service_value: Total service value for rate validation
            
        Returns:
            Dictionary with accurate tax values
        """
        
        # Step 1: Read taxes precisely
        raw_taxes = self._read_taxes_precisely(base64_image)
        logger.info(f"Raw tax reading: {raw_taxes}")
        
        # Step 2: Apply automatic correction
        corrected_taxes = self._auto_correct_confusion(raw_taxes, total_service_value)
        logger.info(f"After correction: {corrected_taxes}")
        
        return corrected_taxes
    
    def _read_taxes_precisely(self, base64_image: str) -> Dict[str, float]:
        """Read taxes with enhanced precision and IR/INSS distinction"""
        
        prompt = """
        Leia esta nota fiscal brasileira e extraia APENAS os valores de impostos que estão CLARAMENTE VISÍVEIS.

        REGRAS CRÍTICAS:
        1. NÃO invente valores - apenas leia o que está escrito
        2. Se um valor não estiver visível, retorne 0.0
        3. CUIDADO ESPECIAL com IR vs INSS:
           - IR (Imposto de Renda): procure "IR", "I.R.", "IRRF"
           - INSS (Previdência): procure "INSS", "I.N.S.S."
           - São impostos completamente diferentes!

        PROCURE NA TABELA DE IMPOSTOS por:
        - PIS: valor ao lado de "PIS"
        - COFINS: valor ao lado de "COFINS"
        - IR: valor ao lado de "IR" ou "IRRF" (NÃO confunda com INSS!)
        - INSS: valor ao lado de "INSS" (NÃO confunda com IR!)
        - ISSQN: valor ao lado de "ISSQN" ou "ISS"
        - CSLL: valor ao lado de "CSLL"

        RETORNE APENAS EM JSON:
        {
            "valor_pis": 0.0,
            "valor_cofins": 0.0,
            "valor_ir": 0.0,
            "valor_inss": 0.0,
            "valor_issqn": 0.0,
            "valor_csll": 0.0,
            "observacoes": "descreva brevemente o que você viu para IR e INSS"
        }

        IMPORTANTE: IR ≠ INSS! Leia com atenção o nome de cada imposto.
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user", 
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                            }
                        ]
                    }
                ],
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            if content:
                result = json.loads(content)
                logger.info(f"AI observations: {result.get('observacoes', 'N/A')}")
                
                return {
                    'valor_pis': float(result.get('valor_pis', 0.0)),
                    'valor_cofins': float(result.get('valor_cofins', 0.0)),
                    'valor_ir': float(result.get('valor_ir', 0.0)),
                    'valor_inss': float(result.get('valor_inss', 0.0)),
                    'valor_issqn': float(result.get('valor_issqn', 0.0)),
                    'valor_csll': float(result.get('valor_csll', 0.0))
                }
            else:
                return self._zero_taxes()
                
        except Exception as e:
            logger.error(f"Error in precise tax reading: {str(e)}")
            return self._zero_taxes()
    
    def _auto_correct_confusion(self, tax_values: Dict[str, float], total_service_value: float) -> Dict[str, float]:
        """Automatically detect and correct IR vs INSS confusion based on rates"""
        
        corrected = tax_values.copy()
        
        if total_service_value <= 0:
            logger.info("No service value available for rate validation")
            return corrected
        
        ir_value = tax_values.get('valor_ir', 0.0)
        inss_value = tax_values.get('valor_inss', 0.0)
        
        # If both are set, no correction needed
        if ir_value > 0 and inss_value > 0:
            logger.info("Both IR and INSS found - no correction needed")
            return corrected
        
        # Check if IR value actually has INSS rate
        if ir_value > 0 and inss_value == 0:
            ir_rate = (ir_value / total_service_value) * 100
            logger.info(f"IR rate: {ir_rate:.2f}%")
            
            if abs(ir_rate - self.tax_rates['inss']) < abs(ir_rate - self.tax_rates['ir']):
                logger.warning(f"IR value {ir_value} has INSS rate ({ir_rate:.2f}%) - correcting!")
                corrected['valor_inss'] = ir_value
                corrected['valor_ir'] = 0.0
        
        # Check if INSS value actually has IR rate
        elif inss_value > 0 and ir_value == 0:
            inss_rate = (inss_value / total_service_value) * 100
            logger.info(f"INSS rate: {inss_rate:.2f}%")
            
            if abs(inss_rate - self.tax_rates['ir']) < abs(inss_rate - self.tax_rates['inss']):
                logger.warning(f"INSS value {inss_value} has IR rate ({inss_rate:.2f}%) - correcting!")
                corrected['valor_ir'] = inss_value
                corrected['valor_inss'] = 0.0
        
        return corrected
    
    def _zero_taxes(self) -> Dict[str, float]:
        """Return zero values for all taxes"""
        return {
            'valor_pis': 0.0,
            'valor_cofins': 0.0,
            'valor_ir': 0.0,
            'valor_inss': 0.0,
            'valor_issqn': 0.0,
            'valor_csll': 0.0
        }

def process_taxes_final(base64_image: str, total_service_value: float = 0.0) -> Dict[str, float]:
    """
    Final comprehensive tax processing
    
    Args:
        base64_image: Base64 encoded image of the document
        total_service_value: Total service value for validation
        
    Returns:
        Dictionary with accurate tax values
    """
    processor = FinalTaxProcessor()
    return processor.process_taxes_completely(base64_image, total_service_value)