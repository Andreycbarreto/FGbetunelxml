"""
Tax Disambiguation Agent
Specialized agent to correctly distinguish between IR and INSS taxes in Brazilian NFe documents
"""

import json
import logging
import os
from typing import Dict, Any, List, Optional
from openai import OpenAI
import re

logger = logging.getLogger(__name__)

class TaxDisambiguationAgent:
    """Specialized agent for disambiguating IR vs INSS in Brazilian tax documents"""
    
    def __init__(self, client: OpenAI):
        self.client = client
        
    def disambiguate_ir_inss(self, base64_image: str, extracted_taxes: Dict[str, Any]) -> Dict[str, Any]:
        """Specifically analyze and correct IR vs INSS confusion"""
        
        # Extract current IR and INSS values for analysis
        current_ir = extracted_taxes.get('valor_ir', 0)
        current_inss = extracted_taxes.get('valor_inss', 0)
        
        disambiguation_prompt = f"""Você é um especialista fiscal brasileiro com foco em distinguir IR e INSS.
        
        SITUAÇÃO ATUAL:
        - IR extraído: R$ {current_ir}
        - INSS extraído: R$ {current_inss}
        
        CONTEXTO FISCAL BRASILEIRO:
        
        1. IMPOSTO DE RENDA (IR) - Federal:
           - Siglas: "IR", "IRRF", "I.R.", "Imp. Renda", "Imposto de Renda"
           - Alíquotas típicas: 0.9%, 1.5%, 3.0%, 4.8%
           - Base: valor dos serviços
           - Retenção na fonte
           
        2. INSS - Previdenciário:
           - Siglas: "INSS", "Contribuição Previdenciária", "Prev. Social"
           - Alíquota típica: 11%
           - Base: valor dos serviços 
           - Contribuição social
           
        INSTRUÇÕES CRÍTICAS:
        1. Analise CADA seção da NFe que mencione impostos
        2. Procure por:
           - Quadros de "Cálculo dos Impostos"
           - Seção "Valores Totais"
           - "Informações Adicionais"
           - Discriminação de serviços
           
        3. Identifique EXATAMENTE onde cada valor aparece
        4. Verifique a consistência das alíquotas:
           - IR: geralmente menor alíquota (0.9-4.8%)
           - INSS: geralmente 11%
           
        5. Busque por descrições como:
           - "IR retido na fonte"
           - "INSS retido"
           - "Contribuição previdenciária"
           - "Imposto de renda retido"
        
        RETORNE JSON com análise detalhada:
        {{
            "analysis": {{
                "ir_found_at": "localização exata na NFe",
                "inss_found_at": "localização exata na NFe",
                "ir_description": "como aparece na NFe",
                "inss_description": "como aparece na NFe"
            }},
            "validation": {{
                "ir_rate_calculated": "alíquota calculada",
                "inss_rate_calculated": "alíquota calculada",
                "rate_consistency": "consistent/inconsistent"
            }},
            "corrected_values": {{
                "ir_value": 0.00,
                "inss_value": 0.00,
                "correction_made": true/false,
                "correction_reason": "motivo da correção"
            }},
            "confidence": 0-100
        }}"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": disambiguation_prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                            }
                        ]
                    }
                ],
                max_tokens=1000,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            if content is None:
                raise ValueError("Empty response from OpenAI")
            
            result = json.loads(content)
            logger.info(f"IR/INSS disambiguation: {result.get('confidence', 0)}% confidence")
            
            # Log the correction details
            if result.get('corrected_values', {}).get('correction_made'):
                reason = result['corrected_values'].get('correction_reason', 'Unknown')
                logger.info(f"IR/INSS correction made: {reason}")
            
            return result
            
        except Exception as e:
            logger.error(f"IR/INSS disambiguation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "confidence": 0
            }
    
    def apply_disambiguation_corrections(self, base_data: Dict[str, Any], 
                                       disambiguation_result: Dict[str, Any]) -> Dict[str, Any]:
        """Apply the disambiguation corrections to the base data"""
        
        corrected_data = base_data.copy()
        
        if disambiguation_result.get('corrected_values', {}).get('correction_made'):
            corrected_values = disambiguation_result['corrected_values']
            
            # Apply IR correction
            if 'ir_value' in corrected_values:
                corrected_data['valor_ir'] = corrected_values['ir_value']
                logger.info(f"Applied IR correction: {corrected_values['ir_value']}")
            
            # Apply INSS correction  
            if 'inss_value' in corrected_values:
                corrected_data['valor_inss'] = corrected_values['inss_value']
                logger.info(f"Applied INSS correction: {corrected_values['inss_value']}")
            
            # Update processing notes
            processing_notes = corrected_data.get('processing_notes', [])
            processing_notes.append(f"IR/INSS disambiguation: {corrected_values.get('correction_reason', 'Corrected')}")
            corrected_data['processing_notes'] = processing_notes
            
            # Update confidence based on disambiguation confidence
            disambiguation_confidence = disambiguation_result.get('confidence', 0)
            current_confidence = corrected_data.get('confidence_score', 0)
            # Weighted average: give more weight to disambiguation if it made corrections
            corrected_data['confidence_score'] = (current_confidence * 0.7) + (disambiguation_confidence * 0.3)
        
        return corrected_data

def enhance_tax_extraction_with_disambiguation(base64_image: str, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enhance tax extraction by applying specialized IR/INSS disambiguation
    
    Args:
        base64_image: Base64 encoded image of the document
        extracted_data: Previously extracted data that may have IR/INSS confusion
        
    Returns:
        Enhanced data with corrected IR/INSS values
    """
    try:
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        disambiguation_agent = TaxDisambiguationAgent(client)
        
        # Check if we have IR or INSS values that might be confused
        has_ir = extracted_data.get('valor_ir', 0) > 0
        has_inss = extracted_data.get('valor_inss', 0) > 0
        
        if has_ir or has_inss:
            logger.info("Running IR/INSS disambiguation analysis...")
            
            # Run disambiguation analysis
            disambiguation_result = disambiguation_agent.disambiguate_ir_inss(
                base64_image, extracted_data
            )
            
            # Apply corrections if any were identified
            if disambiguation_result.get('success', True):  # Success defaults to True if not specified
                corrected_data = disambiguation_agent.apply_disambiguation_corrections(
                    extracted_data, disambiguation_result
                )
                return corrected_data
        
        # Return original data if no disambiguation was needed or failed
        return extracted_data
        
    except Exception as e:
        logger.error(f"Tax disambiguation enhancement failed: {e}")
        return extracted_data