"""
Comprehensive Tax Validation System
Advanced system for accurate identification and validation of all Brazilian taxes
"""

import json
import logging
import os
from typing import Dict, Any, List, Optional, Tuple
from openai import OpenAI
import re

logger = logging.getLogger(__name__)

class ComprehensiveTaxValidator:
    """Advanced tax validator with individual tax analysis"""
    
    def __init__(self, client: OpenAI):
        self.client = client
        
        # Define tax characteristics for validation
        self.tax_profiles = {
            'ICMS': {
                'type': 'product',
                'typical_rates': [0, 7, 12, 17, 18, 25],
                'keywords': ['ICMS', 'I.C.M.S.', 'Imposto sobre Circulação'],
                'never_rates': [11, 1.5, 3.0, 4.8, 0.65, 3.65]
            },
            'IPI': {
                'type': 'product', 
                'typical_rates': [0, 5, 10, 15, 30],
                'keywords': ['IPI', 'I.P.I.', 'Imposto sobre Produtos'],
                'never_rates': [11, 1.5, 3.0, 4.8, 0.65, 3.65]
            },
            'PIS': {
                'type': 'both',
                'typical_rates': [0.65, 1.65],
                'keywords': ['PIS', 'P.I.S.', 'Programa de Integração'],
                'never_rates': [11, 1.5, 3.0, 4.8, 7, 12, 17, 18]
            },
            'COFINS': {
                'type': 'both',
                'typical_rates': [3.0, 7.6],
                'keywords': ['COFINS', 'C.O.F.I.N.S.', 'Contribuição para Financiamento'],
                'never_rates': [11, 1.5, 4.8, 0.65, 1.65]
            },
            'ISSQN': {
                'type': 'service',
                'typical_rates': [2, 3, 4, 5],
                'keywords': ['ISSQN', 'ISS', 'I.S.S.', 'Imposto sobre Serviços'],
                'never_rates': [11, 1.5, 3.0, 4.8, 0.65, 3.65]
            },
            'IR': {
                'type': 'service',
                'typical_rates': [0.9, 1.5, 3.0, 4.8],
                'keywords': ['IR', 'IRRF', 'I.R.', 'Imposto de Renda', 'Imp. Renda'],
                'never_rates': [11, 0.65, 1.65, 3.65, 7.6]
            },
            'INSS': {
                'type': 'service',
                'typical_rates': [11],
                'keywords': ['INSS', 'I.N.S.S.', 'Contribuição Previdenciária', 'Prev. Social'],
                'never_rates': [0.9, 1.5, 3.0, 4.8, 0.65, 1.65, 3.65, 7.6]
            },
            'CSLL': {
                'type': 'service',
                'typical_rates': [1.0, 3.0],
                'keywords': ['CSLL', 'C.S.L.L.', 'Contribuição Social', 'Lucro Líquido'],
                'never_rates': [11, 0.65, 1.65, 3.65, 7.6]
            }
        }
    
    def analyze_individual_taxes(self, base64_image: str) -> Dict[str, Any]:
        """Analyze each tax individually with specific validation"""
        
        analysis_prompt = """Você é um especialista fiscal brasileiro. Analise esta NFe e identifique CADA IMPOSTO INDIVIDUALMENTE.

        INSTRUÇÕES CRÍTICAS:
        1. Para CADA imposto encontrado, identifique:
           - Nome EXATO como aparece na NFe
           - Valor em reais (R$)
           - Alíquota (%) se visível
           - Localização na NFe (seção específica)
        
        2. IMPOSTOS BRASILEIROS PRINCIPAIS:
           - ICMS: Produtos, alíquotas 7%, 12%, 17%, 18%
           - IPI: Produtos industrializados, alíquotas 5%, 10%, 15%
           - PIS: 0,65% ou 1,65%
           - COFINS: 3,0% ou 7,6%
           - ISSQN/ISS: Serviços, 2% a 5%
           - IR/IRRF: 0,9%, 1,5%, 3,0%, 4,8%
           - INSS: 11% (NUNCA outro valor)
           - CSLL: 1,0% ou 3,0%
        
        3. VALIDAÇÃO POR ALÍQUOTA:
           - Se encontrar 11% = SEMPRE é INSS
           - Se encontrar 0,65% = SEMPRE é PIS
           - Se encontrar 3,0% = IR ou COFINS ou CSLL (verificar contexto)
           - Se encontrar 1,5% = SEMPRE é IR
           - Se encontrar 7,6% = SEMPRE é COFINS
        
        4. BUSQUE EM:
           - Quadro "Cálculo do Imposto"
           - "Valores Totais da NFe"
           - "Discriminação dos Serviços"
           - "Informações Adicionais"
           - Totais por imposto
        
        RETORNE JSON detalhado:
        {
            "taxes_found": [
                {
                    "tax_name": "nome do imposto",
                    "displayed_as": "como aparece na NFe",
                    "value": 0.00,
                    "rate": 0.0,
                    "location": "onde foi encontrado",
                    "confidence": 0-100
                }
            ],
            "validation_notes": ["observações específicas"],
            "overall_confidence": 0-100
        }"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": analysis_prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                            }
                        ]
                    }
                ],
                max_tokens=1500,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            if content is None:
                raise ValueError("Empty response from OpenAI")
            
            result = json.loads(content)
            logger.info(f"Individual tax analysis found {len(result.get('taxes_found', []))} taxes")
            return result
            
        except Exception as e:
            logger.error(f"Individual tax analysis failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "taxes_found": [],
                "overall_confidence": 0
            }
    
    def validate_and_correct_taxes(self, found_taxes: List[Dict], base64_image: str) -> Dict[str, Any]:
        """Validate found taxes against profiles and correct misidentifications"""
        
        corrections = {}
        validation_notes = []
        
        for tax_data in found_taxes:
            tax_name = tax_data.get('tax_name', '').upper()
            rate = tax_data.get('rate', 0)
            value = tax_data.get('value', 0)
            
            # Find best match for tax name
            matched_tax = self._match_tax_name(tax_name, tax_data.get('displayed_as', ''))
            
            if matched_tax:
                # Validate rate consistency
                profile = self.tax_profiles[matched_tax]
                
                if rate > 0:
                    if rate in profile['never_rates']:
                        # This is definitely wrong - find correct tax for this rate
                        correct_tax = self._find_tax_by_rate(rate)
                        if correct_tax and correct_tax != matched_tax:
                            validation_notes.append(f"Corrected {matched_tax} to {correct_tax} based on rate {rate}%")
                            matched_tax = correct_tax
                
                # Apply correction
                field_name = self._get_field_name(matched_tax)
                if field_name:
                    corrections[field_name] = value
                    logger.info(f"Mapped {matched_tax} (rate: {rate}%) = R$ {value} to {field_name}")
        
        return {
            "corrections": corrections,
            "validation_notes": validation_notes,
            "success": True
        }
    
    def _match_tax_name(self, tax_name: str, displayed_as: str) -> Optional[str]:
        """Match tax name to correct tax type"""
        
        combined_text = f"{tax_name} {displayed_as}".upper()
        
        # Score each tax type
        scores = {}
        for tax_type, profile in self.tax_profiles.items():
            score = 0
            for keyword in profile['keywords']:
                if keyword.upper() in combined_text:
                    score += len(keyword)
            scores[tax_type] = score
        
        # Return best match if score > 0
        if scores:
            best_score = 0
            best_match = None
            for tax_type, score in scores.items():
                if score > best_score:
                    best_score = score
                    best_match = tax_type
            
            if best_match and best_score > 0:
                return best_match
        
        return None
    
    def _find_tax_by_rate(self, rate: float) -> Optional[str]:
        """Find correct tax type based on rate"""
        
        for tax_type, profile in self.tax_profiles.items():
            if rate in profile['typical_rates']:
                return tax_type
        
        return None
    
    def _get_field_name(self, tax_type: str) -> Optional[str]:
        """Get database field name for tax type"""
        
        mapping = {
            'ICMS': 'valor_icms',
            'IPI': 'valor_ipi',
            'PIS': 'valor_pis',
            'COFINS': 'valor_cofins',
            'ISSQN': 'valor_issqn',
            'IR': 'valor_ir',
            'INSS': 'valor_inss',
            'CSLL': 'valor_csll'
        }
        
        return mapping.get(tax_type)
    
    def comprehensive_tax_validation(self, base64_image: str, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run comprehensive tax validation and correction"""
        
        logger.info("Running comprehensive tax validation...")
        
        # Step 1: Analyze individual taxes
        individual_analysis = self.analyze_individual_taxes(base64_image)
        
        if not individual_analysis.get('success', True):
            logger.error("Individual tax analysis failed")
            return current_data
        
        # Step 2: Validate and correct
        taxes_found = individual_analysis.get('taxes_found', [])
        validation_result = self.validate_and_correct_taxes(taxes_found, base64_image)
        
        if not validation_result.get('success'):
            logger.error("Tax validation failed")
            return current_data
        
        # Step 3: Apply corrections
        corrected_data = current_data.copy()
        corrections = validation_result.get('corrections', {})
        
        # Reset all tax values first to avoid incorrect carryover
        tax_fields = ['valor_icms', 'valor_ipi', 'valor_pis', 'valor_cofins', 
                     'valor_issqn', 'valor_ir', 'valor_inss', 'valor_csll']
        for field in tax_fields:
            corrected_data[field] = 0.0
        
        # Apply validated corrections
        for field_name, value in corrections.items():
            corrected_data[field_name] = value
            logger.info(f"Applied correction: {field_name} = R$ {value}")
        
        # Update processing notes
        processing_notes = corrected_data.get('processing_notes', [])
        processing_notes.extend(validation_result.get('validation_notes', []))
        processing_notes.append("Comprehensive tax validation completed")
        corrected_data['processing_notes'] = processing_notes
        
        return corrected_data

def apply_comprehensive_tax_validation(base64_image: str, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply comprehensive tax validation to correct all tax misidentifications
    
    Args:
        base64_image: Base64 encoded image of the document
        extracted_data: Previously extracted data that may have tax errors
        
    Returns:
        Corrected data with accurate tax identification
    """
    try:
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        validator = ComprehensiveTaxValidator(client)
        
        return validator.comprehensive_tax_validation(base64_image, extracted_data)
        
    except Exception as e:
        logger.error(f"Comprehensive tax validation failed: {e}")
        return extracted_data