"""
Tax Validation Agent
Specialized validation system for Brazilian tax recognition and verification
Focuses on correct tax identification and value validation
"""

import json
import logging
import os
from typing import Dict, Any, List, Tuple
from openai import OpenAI

logger = logging.getLogger(__name__)

class TaxValidationAgent:
    """Specialized agent for validating Brazilian tax data extraction"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        
        # Define Brazilian tax rules and patterns
        self.tax_rules = {
            'federal_taxes': {
                'ICMS': {'applies_to': 'products', 'typical_rate': [7, 12, 17, 18]},
                'IPI': {'applies_to': 'products', 'typical_rate': [0, 5, 10, 15]},
                'PIS': {'applies_to': 'both', 'typical_rate': [0.65, 1.65]},
                'COFINS': {'applies_to': 'both', 'typical_rate': [3, 7.6]}
            },
            'municipal_taxes': {
                'ISSQN': {'applies_to': 'services', 'typical_rate': [2, 3, 4, 5]},
                'ISS': {'applies_to': 'services', 'typical_rate': [2, 3, 4, 5]}
            },
            'retention_taxes': {
                'IR': {'applies_to': 'services', 'typical_rate': [1.5, 3, 4.5]},
                'INSS': {'applies_to': 'services', 'typical_rate': [11]},
                'CSLL': {'applies_to': 'services', 'typical_rate': [1]},
                'ISSRF': {'applies_to': 'services', 'typical_rate': [2, 3, 4, 5]}
            }
        }
    
    def validate_tax_extraction(self, base64_image: str, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate tax extraction with specialized tax knowledge
        
        Args:
            base64_image: Base64 encoded image of the NFe
            extracted_data: Previously extracted tax data
            
        Returns:
            Validated and corrected tax data
        """
        logger.info("Starting specialized tax validation")
        
        # Step 1: Identify document type (product vs service)
        doc_type = self._identify_document_type(extracted_data, base64_image)
        
        # Step 2: Extract taxes with tax-specific prompts
        tax_specific_data = self._extract_taxes_by_category(base64_image, doc_type)
        
        # Step 3: Cross-validate extracted taxes
        validated_taxes = self._cross_validate_taxes(extracted_data, tax_specific_data, doc_type)
        
        # Step 4: Apply fiscal logic validation
        final_taxes = self._apply_fiscal_logic(validated_taxes, doc_type)
        
        return {
            'success': True,
            'document_type': doc_type,
            'validated_taxes': final_taxes,
            'validation_notes': final_taxes.get('validation_notes', []),
            'confidence_score': final_taxes.get('confidence_score', 85)
        }
    
    def _identify_document_type(self, extracted_data: Dict[str, Any], base64_image: str) -> str:
        """Identify if document is product, service, or mixed"""
        
        # Check extracted data first
        if extracted_data.get('valor_total_servicos', 0) > 0:
            return 'service'
        elif extracted_data.get('valor_total_produtos', 0) > 0:
            return 'product'
        
        # Use AI to identify from image
        prompt = """
        Analise esta NFe e identifique o tipo de documento:
        
        TIPOS:
        - "product": NFe de produtos (mercadorias físicas) - modelo 55
        - "service": NFe de serviços - modelo 57  
        - "mixed": NFe mista (produtos + serviços)
        
        INDICADORES:
        - Produtos: ICMS, IPI, mercadorias, CFOP de venda
        - Serviços: ISSQN, ISS, prestação de serviços, códigos de atividade
        
        Retorne JSON: {"document_type": "product|service|mixed", "confidence": 0-100}
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
                response_format={"type": "json_object"},
                timeout=60
            )
            
            result = json.loads(response.choices[0].message.content or '{}')
            return result.get('document_type', 'product')
            
        except Exception as e:
            logger.warning(f"Document type identification failed: {e}")
            return 'product'  # Default fallback
    
    def _extract_taxes_by_category(self, base64_image: str, doc_type: str) -> Dict[str, Any]:
        """Extract taxes using category-specific prompts"""
        
        if doc_type == 'service':
            return self._extract_service_taxes(base64_image)
        elif doc_type == 'product':
            return self._extract_product_taxes(base64_image)
        else:
            # Mixed document - extract both
            service_taxes = self._extract_service_taxes(base64_image)
            product_taxes = self._extract_product_taxes(base64_image)
            return {**service_taxes, **product_taxes}
    
    def _extract_service_taxes(self, base64_image: str) -> Dict[str, Any]:
        """Extract service-specific taxes with specialized prompt"""
        
        prompt = """
        Você é um especialista em tributos MUNICIPAIS e de SERVIÇOS brasileiros.
        Analise esta NFe de SERVIÇOS e extraia APENAS impostos de serviços.
        
        IMPOSTOS DE SERVIÇOS (foque nestes):
        - ISSQN (ISS Municipal) - alíquota 2-5%
        - IR Retido (Imposto de Renda) - alíquota 1,5-4,5%
        - INSS Retido - alíquota 11%
        - CSLL Retido - alíquota 1%
        - ISSRF (ISS Retido na Fonte) - quando aplicável
        
        VALORES IMPORTANTES:
        - Valor BRUTO dos serviços (antes das retenções)
        - Valor LÍQUIDO (após retenções)
        - Base de cálculo de cada imposto
        
        IGNORE impostos de produtos (ICMS, IPI).
        
        Para cada imposto encontrado, extraia:
        - Nome EXATO do imposto
        - Valor do imposto
        - Base de cálculo
        - Alíquota (se visível)
        
        Retorne JSON com:
        {
            "valor_issqn": valor_ou_null,
            "valor_ir": valor_ou_null,
            "valor_inss": valor_ou_null,
            "valor_csll": valor_ou_null,
            "valor_issrf": valor_ou_null,
            "valor_total_servicos": valor_bruto,
            "base_calculo_issqn": valor_ou_null,
            "aliquota_issqn": percentual_ou_null,
            "confidence": 0-100,
            "found_taxes": ["lista", "de", "impostos", "identificados"]
        }
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
                max_tokens=1000,
                response_format={"type": "json_object"},
                timeout=60
            )
            
            result = json.loads(response.choices[0].message.content or '{}')
            result['extraction_type'] = 'service_specific'
            return result
            
        except Exception as e:
            logger.error(f"Service tax extraction failed: {e}")
            return {'confidence': 0, 'extraction_type': 'service_specific'}
    
    def _extract_product_taxes(self, base64_image: str) -> Dict[str, Any]:
        """Extract product-specific taxes with specialized prompt"""
        
        prompt = """
        Você é um especialista em tributos ESTADUAIS e FEDERAIS de PRODUTOS brasileiros.
        Analise esta NFe de PRODUTOS e extraia APENAS impostos de produtos/mercadorias.
        
        IMPOSTOS DE PRODUTOS (foque nestes):
        - ICMS (Estadual) - alíquota 7-18%
        - IPI (Federal) - alíquota 0-15%
        - PIS (Federal) - alíquota 0,65% ou 1,65%
        - COFINS (Federal) - alíquota 3% ou 7,6%
        
        VALORES IMPORTANTES:
        - Valor dos produtos/mercadorias
        - Base de cálculo de cada imposto
        - Alíquotas aplicadas
        
        IGNORE impostos de serviços (ISSQN, IR, INSS).
        
        Para cada imposto encontrado, extraia:
        - Nome EXATO do imposto
        - Valor do imposto
        - Base de cálculo
        - Alíquota (se visível)
        
        Retorne JSON com:
        {
            "valor_icms": valor_ou_null,
            "valor_ipi": valor_ou_null,
            "valor_pis": valor_ou_null,
            "valor_cofins": valor_ou_null,
            "valor_total_produtos": valor,
            "base_calculo_icms": valor_ou_null,
            "aliquota_icms": percentual_ou_null,
            "confidence": 0-100,
            "found_taxes": ["lista", "de", "impostos", "identificados"]
        }
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
                max_tokens=1000,
                response_format={"type": "json_object"},
                timeout=60
            )
            
            result = json.loads(response.choices[0].message.content or '{}')
            result['extraction_type'] = 'product_specific'
            return result
            
        except Exception as e:
            logger.error(f"Product tax extraction failed: {e}")
            return {'confidence': 0, 'extraction_type': 'product_specific'}
    
    def _cross_validate_taxes(self, original_data: Dict[str, Any], 
                             tax_specific_data: Dict[str, Any], 
                             doc_type: str) -> Dict[str, Any]:
        """Cross-validate taxes between different extraction methods"""
        
        prompt = f"""
        Você é um validador especialista em impostos brasileiros.
        Compare os resultados de duas extrações e consolide a resposta mais precisa.
        
        TIPO DE DOCUMENTO: {doc_type}
        
        EXTRAÇÃO ORIGINAL:
        {json.dumps(original_data, indent=2)}
        
        EXTRAÇÃO ESPECÍFICA DE IMPOSTOS:
        {json.dumps(tax_specific_data, indent=2)}
        
        REGRAS DE VALIDAÇÃO:
        1. Para documentos de SERVIÇOS: priorize ISSQN, IR, INSS, CSLL
        2. Para documentos de PRODUTOS: priorize ICMS, IPI, PIS, COFINS
        3. Verifique se nomes dos impostos estão corretos
        4. Valide se alíquotas estão dentro dos padrões brasileiros
        5. Prefira valores que fazem mais sentido fiscalmente
        
        VALIDAÇÕES ESPECÍFICAS:
        - ISSQN vs ISS: são o mesmo imposto (usar ISSQN)
        - IR deve estar entre 1,5% e 4,5% da base
        - INSS deve ser 11% da base (serviços)
        - ICMS deve estar entre 7% e 18% (produtos)
        
        Retorne JSON consolidado com:
        {{
            "valor_icms": valor_validado_ou_null,
            "valor_ipi": valor_validado_ou_null,
            "valor_pis": valor_validado_ou_null,
            "valor_cofins": valor_validado_ou_null,
            "valor_issqn": valor_validado_ou_null,
            "valor_ir": valor_validado_ou_null,
            "valor_inss": valor_validado_ou_null,
            "valor_csll": valor_validado_ou_null,
            "valor_total_produtos": valor_ou_null,
            "valor_total_servicos": valor_ou_null,
            "valor_total_nf": valor_total,
            "validation_notes": ["observacoes_da_validacao"],
            "confidence": 0-100,
            "corrected_taxes": ["impostos_que_foram_corrigidos"]
        }}
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1500,
                response_format={"type": "json_object"},
                timeout=60
            )
            
            result = json.loads(response.choices[0].message.content or '{}')
            return result
            
        except Exception as e:
            logger.error(f"Tax cross-validation failed: {e}")
            # Fallback: merge data with preference for tax-specific
            merged = {**original_data, **tax_specific_data}
            merged['validation_notes'] = [f"Cross-validation failed: {str(e)}"]
            merged['confidence'] = max(
                original_data.get('confidence', 0),
                tax_specific_data.get('confidence', 0)
            )
            return merged
    
    def _apply_fiscal_logic(self, validated_data: Dict[str, Any], doc_type: str) -> Dict[str, Any]:
        """Apply Brazilian fiscal logic to validate tax consistency"""
        
        notes = validated_data.get('validation_notes', [])
        confidence = validated_data.get('confidence', 80)
        
        # Validate tax combinations based on document type
        if doc_type == 'service':
            # Service documents should have ISSQN, might have retentions
            if not validated_data.get('valor_issqn') and not validated_data.get('valor_iss'):
                notes.append("AVISO: Documento de serviço sem ISSQN identificado")
                confidence = max(60, confidence - 15)
            
            # Check for impossible taxes in service documents
            if validated_data.get('valor_icms'):
                notes.append("AVISO: ICMS encontrado em documento de serviço (verificar)")
                confidence = max(70, confidence - 10)
        
        elif doc_type == 'product':
            # Product documents should have ICMS
            if not validated_data.get('valor_icms'):
                notes.append("AVISO: Documento de produto sem ICMS identificado")
                confidence = max(60, confidence - 15)
            
            # Check for impossible taxes in product documents
            if validated_data.get('valor_issqn'):
                notes.append("AVISO: ISSQN encontrado em documento de produto (verificar)")
                confidence = max(70, confidence - 10)
        
        # Validate value consistency
        total_nf = validated_data.get('valor_total_nf', 0)
        total_produtos = validated_data.get('valor_total_produtos', 0)
        total_servicos = validated_data.get('valor_total_servicos', 0)
        
        if total_nf and (total_produtos or total_servicos):
            calculated_total = total_produtos + total_servicos
            if abs(total_nf - calculated_total) > (total_nf * 0.1):  # 10% tolerance
                notes.append(f"AVISO: Inconsistência nos totais - NFe: {total_nf}, Calculado: {calculated_total}")
                confidence = max(65, confidence - 10)
        
        # Apply tax rate validations
        confidence = self._validate_tax_rates(validated_data, notes, confidence)
        
        validated_data['validation_notes'] = notes
        validated_data['confidence_score'] = confidence
        validated_data['fiscal_logic_applied'] = True
        
        return validated_data
    
    def _validate_tax_rates(self, data: Dict[str, Any], notes: List[str], confidence: float) -> float:
        """Validate if tax rates are within expected Brazilian ranges"""
        
        # ISSQN validation (2-5%)
        issqn_value = data.get('valor_issqn', 0)
        issqn_base = data.get('base_calculo_issqn', 0) or data.get('valor_total_servicos', 0)
        if issqn_value and issqn_base:
            issqn_rate = (issqn_value / issqn_base) * 100
            if issqn_rate < 1 or issqn_rate > 6:
                notes.append(f"AVISO: Alíquota ISSQN atípica: {issqn_rate:.2f}%")
                confidence = max(70, confidence - 5)
        
        # IR validation (1.5-4.5%)
        ir_value = data.get('valor_ir', 0)
        ir_base = data.get('valor_total_servicos', 0)
        if ir_value and ir_base:
            ir_rate = (ir_value / ir_base) * 100
            if ir_rate < 1 or ir_rate > 5:
                notes.append(f"AVISO: Alíquota IR atípica: {ir_rate:.2f}%")
                confidence = max(75, confidence - 5)
        
        # ICMS validation (7-18%)
        icms_value = data.get('valor_icms', 0)
        icms_base = data.get('base_calculo_icms', 0) or data.get('valor_total_produtos', 0)
        if icms_value and icms_base:
            icms_rate = (icms_value / icms_base) * 100
            if icms_rate < 5 or icms_rate > 20:
                notes.append(f"AVISO: Alíquota ICMS atípica: {icms_rate:.2f}%")
                confidence = max(70, confidence - 5)
        
        return confidence

# Global instance
tax_validator = TaxValidationAgent()

def validate_tax_data(base64_image: str, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate tax data using specialized tax validation agent
    
    Args:
        base64_image: Base64 encoded image
        extracted_data: Previously extracted tax data
        
    Returns:
        Validated tax data with corrections
    """
    return tax_validator.validate_tax_extraction(base64_image, extracted_data)