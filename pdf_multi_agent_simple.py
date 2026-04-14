"""
Simplified Multi-Agent PDF Processing System
A working implementation with 3-agent validation for NFe PDF processing
"""

import json
import logging
import os
from typing import Dict, Any, List
from openai import OpenAI
from pdf_vision_processor import PDFVisionProcessor
from tax_validation_agent import validate_tax_data

logger = logging.getLogger(__name__)

class MultiAgentPDFProcessor:
    """Simplified multi-agent processor for PDF NFe documents"""
    
    def __init__(self):
        self._client = None
        self.vision_processor = PDFVisionProcessor()
        
    @property
    def client(self):
        if not self._client:
            self._client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        return self._client
        
        
    def process_pdf_file(self, pdf_path: str) -> Dict[str, Any]:
        """Process PDF file with multi-agent validation"""
        try:
            logger.info(f"Starting multi-agent processing for: {pdf_path}")
            
            # Use existing vision processor method to process PDF
            vision_result = self.vision_processor.process_pdf_with_vision(pdf_path)
            if not vision_result.get('success'):
                return {
                    'success': False,
                    'error': 'Failed to process PDF with vision',
                    'confidence_score': 0
                }
            
            # Get base64 images from vision processor for multi-agent analysis
            base64_images = vision_result.get('base64_images', [])
            if not base64_images:
                return {
                    'success': False,
                    'error': 'No images extracted from PDF',
                    'confidence_score': 0
                }
            
            # Use first page for multi-agent processing
            base64_image = base64_images[0]
            
            # Run 3-agent validation system
            return self._run_multi_agent_extraction(base64_image)
            
        except Exception as e:
            logger.error(f"Multi-agent processing failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'confidence_score': 0
            }
    
    def _run_multi_agent_extraction(self, base64_image: str) -> Dict[str, Any]:
        """Run 3-agent validation system"""
        
        # Agent 1: Conservative extractor
        logger.info("Running Agent 1 - Conservative Extractor")
        agent1_result = self._agent_conservative_extract(base64_image)
        
        # Agent 2: Aggressive extractor  
        logger.info("Running Agent 2 - Aggressive Extractor")
        agent2_result = self._agent_aggressive_extract(base64_image)
        
        # Agent 3: Validator/Consolidator
        logger.info("Running Agent 3 - Validator")
        consolidated_result = self._agent_validator(agent1_result, agent2_result)
        
        # Agent 4: Tax Specialist Validator (NEW!)
        logger.info("Running Agent 4 - Tax Specialist Validator")
        final_result = self._tax_specialist_validation(base64_image, consolidated_result)
        
        return final_result
    
    def _agent_conservative_extract(self, base64_image: str) -> Dict[str, Any]:
        """Agent 1: Conservative approach - only extract clearly visible data"""
        
        prompt = """
        Você é um especialista conservador em NFe brasileiras. Extraia APENAS dados que você consegue ver claramente.
        
        Se não conseguir ver algo com 100% de certeza, deixe como null.
        
        Extraia os seguintes campos (apenas se claramente visíveis):
        - numero_nf
        - serie  
        - data_emissao
        - emitente_cnpj
        - emitente_nome
        - destinatario_cnpj
        - destinatario_nome
        - valor_total_nf
        - valor_total_produtos
        - valor_total_servicos
        - valor_icms
        - valor_issqn
        - valor_ir
        - valor_inss
        
        Retorne JSON com os campos extraídos e um campo "confidence" (0-100).
        Seja MUITO conservador na confiança.
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
                max_tokens=1500,
                response_format={"type": "json_object"},
                timeout=60
            )
            
            result = json.loads(response.choices[0].message.content or '{}')
            result['agent_id'] = 'conservative'
            return result
            
        except Exception as e:
            logger.error(f"Conservative agent failed: {str(e)}")
            return {'confidence': 0, 'agent_id': 'conservative', 'error': str(e)}
    
    def _agent_aggressive_extract(self, base64_image: str) -> Dict[str, Any]:
        """Agent 2: Aggressive approach - extract with inference"""
        
        prompt = """
        Você é um especialista agressivo em NFe brasileiras. Use inferência inteligente para extrair o máximo de dados.
        
        Pode fazer inferências baseadas em:
        - Padrões típicos de NFe
        - Cálculos de impostos
        - Valores relacionados
        - Contexto do documento
        
        Extraia TODOS os campos possíveis:
        - numero_nf, serie, data_emissao
        - chave_nfe (se visível)
        - emitente_cnpj, emitente_nome, emitente_ie
        - destinatario_cnpj, destinatario_nome, destinatario_ie
        - valor_total_nf, valor_total_produtos, valor_total_servicos
        - Todos os impostos: valor_icms, valor_ipi, valor_pis, valor_cofins
        - Impostos de serviço: valor_issqn, valor_ir, valor_inss, valor_csll
        - natureza_operacao, forma_pagamento
        - informacoes_adicionais (se houver texto adicional visível)
        
        Use inferência para completar dados parciais.
        
        Retorne JSON completo com "confidence" (0-100).
        Seja agressivo mas indique incertezas.
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
                max_tokens=1500,
                response_format={"type": "json_object"},
                timeout=60
            )
            
            result = json.loads(response.choices[0].message.content or '{}')
            result['agent_id'] = 'aggressive'
            return result
            
        except Exception as e:
            logger.error(f"Aggressive agent failed: {str(e)}")
            return {'confidence': 0, 'agent_id': 'aggressive', 'error': str(e)}
    
    def _agent_validator(self, agent1_result: Dict[str, Any], agent2_result: Dict[str, Any]) -> Dict[str, Any]:
        """Agent 3: Validate and consolidate results from both agents"""
        
        prompt = f"""
        Você é um validador especialista em NFe brasileiras. Analise os resultados de dois agentes e consolide a melhor resposta.
        
        AGENTE CONSERVADOR:
        Confiança: {agent1_result.get('confidence', 0)}%
        Dados: {json.dumps(agent1_result, indent=2)}
        
        AGENTE AGRESSIVO:
        Confiança: {agent2_result.get('confidence', 0)}%
        Dados: {json.dumps(agent2_result, indent=2)}
        
        REGRAS DE CONSOLIDAÇÃO:
        1. Se ambos concordam no valor: alta confiança (usar o valor)
        2. Se apenas um tem o valor e confiança > 70%: usar o valor
        3. Se divergem: escolher o mais lógico fiscalmente
        4. Para valores monetários: preferir o mais conservador em caso de dúvida
        5. Para campos de texto: preferir o mais completo se confiável
        
        VALIDAÇÕES FISCAIS:
        - Valores devem ser consistentes (total >= soma das partes)
        - Impostos devem fazer sentido para o tipo de documento
        - CNPJ deve ter formato válido
        - Datas devem ser realistas
        
        Retorne JSON consolidado com:
        {{
            "success": true,
            "confidence_score": confianca_final_0_100,
            "data": {{ todos_os_campos_consolidados }},
            "validation_notes": ["observações sobre a validação"],
            "agent_agreement": percentual_concordancia_0_100,
            "best_fields": {{ "campo": "agent_conservative|agent_aggressive|consensus" }}
        }}
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                response_format={"type": "json_object"},
                timeout=60
            )
            
            result = json.loads(response.choices[0].message.content or '{}')
            
            # Ensure required fields
            if 'success' not in result:
                result['success'] = True
            if 'confidence_score' not in result:
                result['confidence_score'] = max(
                    agent1_result.get('confidence', 0),
                    agent2_result.get('confidence', 0)
                )
            if 'data' not in result:
                # Fallback: merge both results
                result['data'] = {**agent1_result, **agent2_result}
                result['data'].pop('confidence', None)
                result['data'].pop('agent_id', None)
                result['data'].pop('error', None)
            
            # Add multi-agent metadata
            result['multi_agent_validation'] = True
            result['processing_notes'] = result.get('validation_notes', [])
            
            logger.info(f"Validation completed - Final confidence: {result['confidence_score']:.1f}%")
            
            return result
            
        except Exception as e:
            logger.error(f"Validator failed: {str(e)}")
            
            # Fallback: choose better agent result
            if agent1_result.get('confidence', 0) >= agent2_result.get('confidence', 0):
                best_result = agent1_result
            else:
                best_result = agent2_result
            
            return {
                'success': True,
                'confidence_score': best_result.get('confidence', 50),
                'data': {k: v for k, v in best_result.items() if k not in ['confidence', 'agent_id', 'error']},
                'validation_notes': [f"Validator failed, used {best_result.get('agent_id', 'unknown')} result"],
                'agent_agreement': 0,
                'multi_agent_validation': True,
                'processing_notes': [f"Fallback validation: {str(e)}"]
            }
    
    def _tax_specialist_validation(self, base64_image: str, consolidated_result: Dict[str, Any]) -> Dict[str, Any]:
        """Apply specialized tax validation as final validation layer"""
        
        try:
            logger.info("Applying specialized tax validation")
            
            # Extract consolidated data for tax validation
            consolidated_data = consolidated_result.get('data', {})
            
            # Run specialized tax validation
            tax_validation_result = validate_tax_data(base64_image, consolidated_data)
            
            if tax_validation_result.get('success'):
                # Merge tax-validated data with consolidated result
                validated_taxes = tax_validation_result.get('validated_taxes', {})
                
                # Update data with tax-validated values
                final_data = {**consolidated_data, **validated_taxes}
                
                # Update confidence based on tax validation
                tax_confidence = tax_validation_result.get('confidence_score', 80)
                original_confidence = consolidated_result.get('confidence_score', 80)
                
                # Final confidence is average weighted towards tax validation
                final_confidence = (tax_confidence * 0.6) + (original_confidence * 0.4)
                
                # Combine validation notes
                tax_notes = tax_validation_result.get('validation_notes', [])
                original_notes = consolidated_result.get('processing_notes', [])
                
                final_result = {
                    'success': True,
                    'confidence_score': final_confidence,
                    'data': final_data,
                    'processing_notes': original_notes + tax_notes + ["Tax specialist validation applied"],
                    'multi_agent_validation': True,
                    'tax_specialist_validation': True,
                    'document_type': tax_validation_result.get('document_type', 'unknown'),
                    'validation_layers': 4  # All 4 agents applied
                }
                
                logger.info(f"Tax specialist validation completed - Final confidence: {final_confidence:.1f}%")
                return final_result
            
            else:
                # Tax validation failed, use consolidated result
                logger.warning("Tax specialist validation failed, using consolidated result")
                consolidated_result['processing_notes'] = consolidated_result.get('processing_notes', []) + [
                    "Tax specialist validation failed - using consolidated result"
                ]
                consolidated_result['validation_layers'] = 3
                return consolidated_result
                
        except Exception as e:
            logger.error(f"Tax specialist validation error: {str(e)}")
            # Return consolidated result with error note
            consolidated_result['processing_notes'] = consolidated_result.get('processing_notes', []) + [
                f"Tax specialist validation error: {str(e)}"
            ]
            consolidated_result['validation_layers'] = 3
            return consolidated_result

# Global processor instance
multi_agent_processor = MultiAgentPDFProcessor()

def process_pdf_with_multi_agent_validation(pdf_path: str) -> Dict[str, Any]:
    """
    Main function to process PDF with multi-agent validation
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Processing results with validation data
    """
    return multi_agent_processor.process_pdf_file(pdf_path)

def process_pdf_with_advanced_agents(pdf_path: str) -> Dict[str, Any]:
    """
    Process PDF with advanced multi-agent system for improved accuracy
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Processing results with enhanced tax and item extraction
    """
    try:
        from pdf_advanced_multi_agent import AdvancedMultiAgentProcessor
        advanced_processor = AdvancedMultiAgentProcessor()
        return advanced_processor.process_pdf_file(pdf_path)
    except Exception as e:
        logger.error(f"Advanced processing failed, falling back to standard multi-agent: {e}")
        return multi_agent_processor.process_pdf_file(pdf_path)