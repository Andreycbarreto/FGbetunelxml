"""
Multi-Agent PDF Processing System
Implements a robust 3-agent validation system for NFe PDF processing:
- 2 extraction agents with different approaches
- 1 validation agent that consolidates results
"""

import json
import logging
import os
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from openai import OpenAI
import base64

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def safe_json_parse(content) -> Dict[str, Any]:
    """Safely parse JSON content with fallback"""
    if not content:
        return {}
    try:
        return json.loads(content)
    except (json.JSONDecodeError, TypeError):
        logger.warning(f"Failed to parse JSON content: {str(content)[:100]}...")
        return {}

@dataclass
class AgentResult:
    """Result from a single agent processing"""
    data: Dict[str, Any]
    confidence: float
    processing_notes: List[str]
    agent_id: str
    
@dataclass  
class ValidationResult:
    """Final consolidated result from multi-agent validation"""
    consolidated_data: Dict[str, Any]
    confidence_score: float
    validation_notes: List[str]
    agent_agreement: float
    best_agent: str

class PDFExtractionAgentA:
    """First extraction agent - Conservative approach with detailed field mapping"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.agent_id = "conservative_extractor"
        
    def extract_header_data(self, base64_image: str) -> AgentResult:
        """Extract header data with conservative approach"""
        prompt = """
        Você é um especialista em análise de documentos fiscais brasileiros. Analise esta imagem de NFe com EXTREMA PRECISÃO.
        
        Extraia APENAS os dados que você consegue ver claramente na imagem. Se não conseguir ver algum campo, deixe como null.
        
        FOQUE nos dados do cabeçalho:
        - Número da NFe
        - Série
        - Data de emissão  
        - Chave de acesso
        - Dados do emitente (CNPJ, nome, inscrição estadual)
        - Dados do destinatário (CNPJ, nome, inscrição estadual)
        
        Seja CONSERVADOR: apenas extraia dados que estão claramente visíveis.
        
        Retorne JSON com os campos extraídos e uma nota de confiança (0-100).
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
            
            result = safe_json_parse(response.choices[0].message.content)
            confidence = result.get('confidence', 70)
            
            return AgentResult(
                data=result,
                confidence=confidence,
                processing_notes=[f"Conservative extraction completed with {confidence}% confidence"],
                agent_id=self.agent_id
            )
            
        except Exception as e:
            logger.error(f"Agent A header extraction failed: {e}")
            return AgentResult(
                data={},
                confidence=0,
                processing_notes=[f"Extraction failed: {str(e)}"],
                agent_id=self.agent_id
            )
    
    def extract_fiscal_data(self, base64_image: str) -> AgentResult:
        """Extract fiscal values with conservative approach"""
        prompt = """
        Você é um especialista em tributos brasileiros. Analise esta NFe com MÁXIMA PRECISÃO nos valores fiscais.
        
        Identifique o tipo de documento:
        - Produtos (modelo 55): Foque em ICMS, IPI, PIS, COFINS
        - Serviços (modelo 57): Foque em ISS, IR, INSS, CSLL, ISSQN
        
        Para SERVIÇOS, extraia valores BRUTOS (antes das retenções).
        Para PRODUTOS, extraia valores LÍQUIDOS.
        
        Campos obrigatórios:
        - valor_total_nf
        - valor_total_produtos OU valor_total_servicos
        - Impostos específicos do tipo de documento
        
        Seja CONSERVADOR: apenas valores claramente visíveis.
        
        Retorne JSON com valores e confiança (0-100).
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
            
            result = json.loads(response.choices[0].message.content)
            confidence = result.get('confidence', 70)
            
            return AgentResult(
                data=result,
                confidence=confidence,
                processing_notes=[f"Conservative fiscal extraction completed with {confidence}% confidence"],
                agent_id=self.agent_id
            )
            
        except Exception as e:
            logger.error(f"Agent A fiscal extraction failed: {e}")
            return AgentResult(
                data={},
                confidence=0,
                processing_notes=[f"Fiscal extraction failed: {str(e)}"],
                agent_id=self.agent_id
            )

class PDFExtractionAgentB:
    """Second extraction agent - Aggressive approach with inference capabilities"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.agent_id = "aggressive_extractor"
        
    def extract_header_data(self, base64_image: str) -> AgentResult:
        """Extract header data with aggressive inference"""
        prompt = """
        Você é um especialista em NFe com capacidade de inferência. Analise esta imagem e extraia todos os dados possíveis.
        
        Use seu conhecimento para INFERIR dados quando necessário:
        - Se vir CNPJ parcial, complete com padrão esperado
        - Se vir apenas nome fantasia, tente identificar razão social
        - Infira tipo de operação baseado nos dados visíveis
        
        Extraia TODOS os campos do cabeçalho possíveis:
        - Identificação completa da NFe
        - Dados completos do emitente (CNPJ, nome, fantasia, IE, IM, endereço)
        - Dados completos do destinatário
        - Natureza da operação
        - Tipo de operação (entrada/saída)
        
        Seja AGRESSIVO na extração, mas indique seu nível de certeza.
        
        Retorne JSON completo com confiança (0-100).
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
            
            result = json.loads(response.choices[0].message.content)
            confidence = result.get('confidence', 80)
            
            return AgentResult(
                data=result,
                confidence=confidence,
                processing_notes=[f"Aggressive extraction completed with {confidence}% confidence"],
                agent_id=self.agent_id
            )
            
        except Exception as e:
            logger.error(f"Agent B header extraction failed: {e}")
            return AgentResult(
                data={},
                confidence=0,
                processing_notes=[f"Extraction failed: {str(e)}"],
                agent_id=self.agent_id
            )
    
    def extract_fiscal_data(self, base64_image: str) -> AgentResult:
        """Extract fiscal values with aggressive inference"""
        prompt = """
        Você é um especialista tributário com capacidade de inferência avançada. Analise esta NFe e extraia TODOS os valores fiscais.
        
        Use inferência inteligente:
        - Calcule valores não mostrados baseado em outros campos
        - Identifique padrões de retenção para serviços
        - Deduza alíquotas baseadas em valores base
        - Infira datas de vencimento para serviços pré-pagos
        
        Para documentos de SERVIÇO:
        - Extraia valor bruto ANTES das retenções
        - Identifique todas as retenções (IR, INSS, CSLL, ISS)
        - Calcule valor líquido se necessário
        
        Para documentos de PRODUTO:
        - Foque em ICMS, IPI, PIS, COFINS
        - Extraia valores de frete, seguro, desconto
        
        Seja AGRESSIVO mas indique incertezas.
        
        Retorne JSON completo com todos os impostos e confiança (0-100).
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
            
            result = json.loads(response.choices[0].message.content)
            confidence = result.get('confidence', 80)
            
            return AgentResult(
                data=result,
                confidence=confidence,
                processing_notes=[f"Aggressive fiscal extraction completed with {confidence}% confidence"],
                agent_id=self.agent_id
            )
            
        except Exception as e:
            logger.error(f"Agent B fiscal extraction failed: {e}")
            return AgentResult(
                data={},
                confidence=0,
                processing_notes=[f"Fiscal extraction failed: {str(e)}"],
                agent_id=self.agent_id
            )

class PDFValidationAgent:
    """Validation agent that consolidates results from extraction agents"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.agent_id = "validator"
        
    def validate_and_consolidate(self, agent_a_result: AgentResult, agent_b_result: AgentResult, 
                                extraction_type: str) -> ValidationResult:
        """Validate and consolidate results from both extraction agents"""
        
        prompt = f"""
        Você é um validador especialista em NFe brasileiras. Analise os resultados de dois agentes de extração e consolide a melhor resposta.
        
        DADOS DO AGENTE CONSERVADOR (A):
        Confiança: {agent_a_result.confidence}%
        Dados: {json.dumps(agent_a_result.data, indent=2)}
        
        DADOS DO AGENTE AGRESSIVO (B):
        Confiança: {agent_b_result.confidence}%
        Dados: {json.dumps(agent_b_result.data, indent=2)}
        
        Tipo de extração: {extraction_type}
        
        CRITÉRIOS DE VALIDAÇÃO:
        1. Consistência entre agentes (maior peso)
        2. Confiança individual de cada agente
        3. Completude dos dados
        4. Lógica fiscal brasileira
        
        REGRAS DE CONSOLIDAÇÃO:
        - Se ambos concordam: use o valor (alta confiança)
        - Se apenas um tem o valor: use se confiança > 70%
        - Se divergem: escolha o mais lógico fiscalmente
        - Prefira valores conservadores em caso de dúvida
        
        Para IMPOSTOS:
        - Valores devem ser consistentes com tipo de documento
        - Retenções devem fazer sentido matematicamente
        - Totais devem bater com somatórias
        
        Retorne JSON com:
        {{
            "consolidated_data": {{ dados_consolidados }},
            "confidence_score": confianca_final_0_100,
            "validation_notes": ["nota1", "nota2"],
            "agent_agreement": percentual_concordancia_0_100,
            "best_agent": "conservative_extractor" ou "aggressive_extractor",
            "field_analysis": {{
                "campo": {{
                    "value": valor_escolhido,
                    "source": "agent_a|agent_b|consensus|calculated",
                    "confidence": confianca_especifica
                }}
            }}
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
            
            result = json.loads(response.choices[0].message.content)
            
            return ValidationResult(
                consolidated_data=result.get('consolidated_data', {}),
                confidence_score=result.get('confidence_score', 50),
                validation_notes=result.get('validation_notes', []),
                agent_agreement=result.get('agent_agreement', 0),
                best_agent=result.get('best_agent', 'conservative_extractor')
            )
            
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            # Fallback: choose agent with higher confidence
            if agent_a_result.confidence >= agent_b_result.confidence:
                best_result = agent_a_result
            else:
                best_result = agent_b_result
                
            return ValidationResult(
                consolidated_data=best_result.data,
                confidence_score=best_result.confidence,
                validation_notes=[f"Validation failed, used {best_result.agent_id}: {str(e)}"],
                agent_agreement=0,
                best_agent=best_result.agent_id
            )

class MultiAgentPDFProcessor:
    """Main orchestrator for multi-agent PDF processing"""
    
    def __init__(self):
        self.agent_a = PDFExtractionAgentA()
        self.agent_b = PDFExtractionAgentB()
        self.validator = PDFValidationAgent()
        
    def process_pdf_stage(self, base64_image: str, stage_type: str) -> ValidationResult:
        """
        Process a single stage with multi-agent validation
        
        Args:
            base64_image: Base64 encoded image
            stage_type: 'header' or 'fiscal' or 'items' or 'additional'
        """
        logger.info(f"Starting multi-agent processing for stage: {stage_type}")
        
        # Run both extraction agents
        if stage_type == 'header':
            result_a = self.agent_a.extract_header_data(base64_image)
            result_b = self.agent_b.extract_header_data(base64_image)
        elif stage_type == 'fiscal':
            result_a = self.agent_a.extract_fiscal_data(base64_image)
            result_b = self.agent_b.extract_fiscal_data(base64_image)
        else:
            # For other stages, use generic extraction (can be extended)
            result_a = AgentResult({}, 0, [f"Stage {stage_type} not implemented for agent A"], "agent_a")
            result_b = AgentResult({}, 0, [f"Stage {stage_type} not implemented for agent B"], "agent_b")
        
        logger.info(f"Agent A confidence: {result_a.confidence}%, Agent B confidence: {result_b.confidence}%")
        
        # Validate and consolidate
        validation_result = self.validator.validate_and_consolidate(result_a, result_b, stage_type)
        
        logger.info(f"Validation completed - Final confidence: {validation_result.confidence_score}%, "
                   f"Agreement: {validation_result.agent_agreement}%, Best agent: {validation_result.best_agent}")
        
        return validation_result
    
    def process_complete_pdf(self, base64_images: List[str]) -> Dict[str, Any]:
        """Process complete PDF with multi-agent validation for all stages"""
        
        logger.info(f"Starting complete multi-agent PDF processing for {len(base64_images)} pages")
        
        results = {}
        all_notes = []
        total_confidence = []
        
        # Process each stage
        stages = ['header', 'fiscal']
        
        for stage in stages:
            logger.info(f"Processing stage: {stage}")
            
            # Use first page for header and fiscal data
            if base64_images:
                validation_result = self.process_pdf_stage(base64_images[0], stage)
                
                results[stage] = {
                    'data': validation_result.consolidated_data,
                    'confidence': validation_result.confidence_score,
                    'agent_agreement': validation_result.agent_agreement,
                    'best_agent': validation_result.best_agent,
                    'validation_notes': validation_result.validation_notes
                }
                
                all_notes.extend(validation_result.validation_notes)
                total_confidence.append(validation_result.confidence_score)
        
        # Calculate overall confidence
        overall_confidence = sum(total_confidence) / len(total_confidence) if total_confidence else 0
        
        # Consolidate all data
        consolidated_data = {}
        for stage_data in results.values():
            consolidated_data.update(stage_data['data'])
        
        logger.info(f"Multi-agent processing completed - Overall confidence: {overall_confidence:.1f}%")
        
        return {
            'success': True,
            'data': consolidated_data,
            'confidence_score': overall_confidence,
            'processing_notes': all_notes,
            'stage_results': results,
            'multi_agent_validation': True
        }

# Global processor instance
multi_agent_processor = MultiAgentPDFProcessor()

def process_pdf_with_multi_agent_validation(base64_images: List[str]) -> Dict[str, Any]:
    """
    Main function to process PDF with multi-agent validation
    
    Args:
        base64_images: List of base64 encoded images
        
    Returns:
        Processing results with validation data
    """
    return multi_agent_processor.process_complete_pdf(base64_images)