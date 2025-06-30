"""
AI Agents for PDF NFe Processing
Specialized agents for processing NFe PDF documents using LangGraph workflow.
"""

import json
import logging
from typing import Dict, Any, List, Optional, TypedDict
from dataclasses import dataclass
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage
from openai import OpenAI
import os

logger = logging.getLogger(__name__)

class PDFAgentState(TypedDict):
    """State shared between PDF processing agents."""
    markdown_content: str
    pdf_metadata: Dict[str, Any]
    analyzed_data: Dict[str, Any]
    extracted_data: Dict[str, Any]
    validated_data: Dict[str, Any]
    confidence_score: float
    errors: List[str]
    processing_notes: List[str]
    current_step: str

@dataclass
class PDFProcessingResult:
    """Result of the PDF AI processing workflow."""
    success: bool
    data: Optional[Dict[str, Any]]
    confidence_score: float
    errors: List[str]
    processing_notes: List[str]

class PDFAnalysisAgent:
    """Agent responsible for analyzing PDF markdown content and structure."""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.logger = logging.getLogger(__name__)
    
    def analyze(self, state: PDFAgentState) -> PDFAgentState:
        """Analyze the PDF markdown content and identify NFe structure."""
        try:
            self.logger.info("PDF Analysis Agent: Starting analysis")
            
            prompt = f"""
            Você é um especialista em análise de documentos fiscais brasileiros. 
            Analise o conteúdo markdown extraído de um PDF de NFe e identifique as principais seções e estrutura do documento.

            CONTEÚDO DO PDF (MARKDOWN):
            {state['markdown_content'][:8000]}  # Limitar para não exceder token limits

            TAREFAS:
            1. Identifique se este é realmente um documento de NFe válido
            2. Identifique o modelo do documento (55=produto, 57=serviço, 65=misto)
            3. Classifique o tipo de documento (produto/serviço/misto)
            4. Localize as principais seções: cabeçalho, emitente, destinatário, produtos/serviços, totais, impostos
            5. Identifique impostos específicos de serviços (ISSQN, IR retido, ISS retido)
            6. Localize campos de informações adicionais
            7. Avalie a qualidade e completude das informações extraídas
            8. Identifique possíveis problemas ou dados ausentes
            9. Forneça uma confiança geral do documento (0-100)

            ATENÇÃO ESPECIAL:
            - Para documentos de serviço: foque em inscrições municipais
            - Identifique códigos de serviço e atividade
            - Verifique presença de impostos municipais
            - Analise contexto de pagamento (à vista/prazo)

            Responda em formato JSON:
            {{
                "is_valid_nfe": true/false,
                "document_model": "55|57|65",
                "document_type": "produto|servico|misto",
                "identified_sections": ["seção1", "seção2", ...],
                "has_service_taxes": true/false,
                "has_municipal_registration": true/false,
                "has_additional_info": true/false,
                "tax_context": "municipal|estadual|misto",
                "data_quality": "alta|média|baixa",
                "confidence_score": 0-100,
                "issues_found": ["problema1", "problema2", ...],
                "processing_notes": ["nota1", "nota2", "incluindo", "justificativa", "da", "classificação"]
            }}
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024. do not change this unless explicitly requested by the user
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            content = response.choices[0].message.content
            if content is None:
                raise ValueError("No content returned from OpenAI")
            analysis_result = json.loads(content)
            
            # Update state
            state['analyzed_data'] = analysis_result
            state['confidence_score'] = analysis_result.get('confidence_score', 0) / 100.0
            state['processing_notes'].extend(analysis_result.get('processing_notes', []))
            state['current_step'] = 'analysis_completed'
            
            if not analysis_result.get('is_valid_nfe', False):
                state['errors'].append("Documento não identificado como NFe válida")
            
            self.logger.info(f"PDF Analysis completed with confidence: {state['confidence_score']}")
            return state
            
        except Exception as e:
            error_msg = f"Erro na análise PDF: {str(e)}"
            self.logger.error(error_msg)
            state['errors'].append(error_msg)
            state['current_step'] = 'analysis_error'
            return state

class PDFExtractionAgent:
    """Agent responsible for extracting structured NFe data from PDF markdown."""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.logger = logging.getLogger(__name__)
    
    def extract(self, state: PDFAgentState) -> PDFAgentState:
        """Extract structured NFe data from PDF markdown content."""
        try:
            self.logger.info("PDF Extraction Agent: Starting data extraction")
            
            # Get analysis context for extraction
            analyzed_data = state.get('analyzed_data', {})
            document_model = analyzed_data.get('document_model', '55')
            document_type = analyzed_data.get('document_type', 'produto')
            
            # Create comprehensive extraction prompt
            prompt = f"""
            Você é um especialista em extração de dados de NFe brasileira. 
            Extraia todos os dados estruturados do conteúdo markdown de uma NFe em PDF.

            CONTEXTO DO DOCUMENTO:
            - Modelo: {document_model} ({document_type})
            - Processamento específico para documentos de serviço (modelo 57)

            CONTEÚDO DO PDF (MARKDOWN):
            {state['markdown_content']}

            EXTRAIA OS SEGUINTES DADOS (use null para campos não encontrados):

            IDENTIFICAÇÃO:
            - chave_nfe: Chave de acesso da NFe (44 dígitos)
            - numero_nf: Número da nota fiscal
            - serie: Série da nota
            - modelo: Modelo do documento (APENAS O CÓDIGO: 55, 57, 65, etc.)
            - tipo_documento: produto|servico|misto (baseado no modelo)
            - data_emissao: Data de emissão (formato YYYY-MM-DD)
            - data_saida_entrada: Data de saída/entrada
            - tipo_operacao: Entrada ou Saída
            - natureza_operacao: Natureza da operação

            EMITENTE:
            - emitente_cnpj: CNPJ do emitente
            - emitente_nome: Razão social
            - emitente_fantasia: Nome fantasia
            - emitente_ie: Inscrição estadual
            - emitente_im: Inscrição municipal (especialmente para serviços)
            - emitente_endereco: Endereço completo
            - emitente_municipio: Município
            - emitente_uf: UF
            - emitente_cep: CEP

            DESTINATÁRIO:
            - destinatario_cnpj: CNPJ/CPF do destinatário
            - destinatario_nome: Nome/Razão social
            - destinatario_ie: Inscrição estadual
            - destinatario_im: Inscrição municipal (especialmente para serviços)
            - destinatario_endereco: Endereço completo
            - destinatario_municipio: Município
            - destinatario_uf: UF
            - destinatario_cep: CEP

            VALORES TOTAIS:
            - valor_total_produtos: Valor total dos produtos
            - valor_total_servicos: Valor total dos serviços
            - valor_total_nf: Valor total da nota
            - valor_icms: Valor do ICMS
            - valor_ipi: Valor do IPI
            - valor_pis: Valor do PIS
            - valor_cofins: Valor do COFINS
            - valor_issqn: Valor do ISSQN (imposto municipal sobre serviços)
            - valor_issrf: Valor do ISSRF (ISS retido na fonte)
            - valor_ir: Valor do IR retido (imposto de renda)
            - valor_inss: Valor do INSS retido (contribuição previdenciária)
            - valor_csll: Valor do CSLL retido (contribuição social)
            - valor_iss_retido: Valor do ISS retido na fonte
            - valor_frete: Valor do frete
            - valor_seguro: Valor do seguro
            - valor_desconto: Valor do desconto
            - valor_tributos: Valor aproximado dos tributos

            TRANSPORTE:
            - modalidade_frete: Modalidade do frete
            - transportadora_cnpj: CNPJ da transportadora
            - transportadora_nome: Nome da transportadora

            PAGAMENTO:
            - forma_pagamento: Forma de pagamento
            - data_vencimento: Data de vencimento (inferir se não informado para pagamentos à vista)

            PROTOCOLO:
            - protocolo_autorizacao: Protocolo de autorização
            - status_autorizacao: Status
            - ambiente: Produção ou Homologação

            INFORMAÇÕES ADICIONAIS:
            - informacoes_adicionais: Conteúdo do campo de informações adicionais da NFe

            ITENS (lista de produtos/serviços):
            Para cada item, extrair TODOS os campos específicos:
            
            IDENTIFICAÇÃO DO ITEM:
            - numero_item, codigo_produto, descricao_produto
            - codigo_servico: Código específico do serviço (separado do produto)
            - codigo_atividade: Código da atividade do serviço
            - descricao_servico: Descrição específica do serviço (separada do produto)
            - ncm, cfop, unidade_comercial, quantidade_comercial, valor_unitario_comercial, valor_total_produto
            
            IMPOSTOS TRADICIONAIS:
            - valor_icms, valor_ipi, valor_pis, valor_cofins com bases e alíquotas
            
            IMPOSTOS MUNICIPAIS/FEDERAIS (ESSENCIAL PARA SERVIÇOS):
            - valor_issqn: ISSQN (imposto municipal)
            - valor_issrf: ISSRF (ISS retido na fonte)  
            - valor_ir: IR retido (imposto de renda)
            - valor_inss: INSS retido (contribuição previdenciária)
            - valor_csll: CSLL retido (contribuição social)
            - valor_iss_retido: ISS retido na fonte
            - Para cada imposto: base de cálculo, alíquota e valor

            REGRAS ESPECIAIS PARA EXTRAÇÃO:
            
            MODELO DO DOCUMENTO:
            - Para o campo "modelo": extraia APENAS o código numérico (55, 57, 65)
            - Se encontrar "Nota Fiscal de Serviço Eletrônica": modelo = 57
            - Se encontrar "NFe" ou "Nota Fiscal Eletrônica": modelo = 55
            - Se encontrar "NFCe": modelo = 65
            
            DOCUMENTOS E IMPOSTOS:
            - Para documentos de serviço (modelo 57): priorize inscrições municipais
            - Separe códigos de serviço dos códigos de produto
            - Capture descrições de serviços separadamente dos produtos
            - IDENTIFIQUE IMPOSTOS MUNICIPAIS/FEDERAIS: procure por:
              * ISSQN, ISS, "Imposto sobre Serviços"
              * ISSRF, "ISS Retido na Fonte", "ISS Ret. Fonte"
              * IR, "Imposto de Renda", "IR Retido"
              * INSS, "Contribuição Previdenciária", "INSS Retido"
              * CSLL, "Contribuição Social", "CSLL Retido"
            - Para cada imposto encontrado: extraia base, alíquota e valor
            - Para pagamentos à vista sem data: infira como mesma data de emissão
            - Extraia todo conteúdo do campo "informações adicionais"
            - Para documentos de serviço: busque especialmente impostos municipais na seção de totais

            IMPORTANTE: Não confunda impostos tradicionais (ICMS, IPI, PIS, COFINS) com impostos de serviços.
            Os impostos municipais/federais são específicos e devem ser identificados separadamente.

            Responda APENAS em formato JSON válido com todos os campos acima.
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024. do not change this unless explicitly requested by the user
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=4000
            )
            
            extracted_data = json.loads(response.choices[0].message.content)
            
            # Update state
            state['extracted_data'] = extracted_data
            state['current_step'] = 'extraction_completed'
            state['processing_notes'].append(f"Extraídos {len(extracted_data)} campos de dados")
            
            self.logger.info("PDF data extraction completed successfully")
            return state
            
        except Exception as e:
            error_msg = f"Erro na extração de dados PDF: {str(e)}"
            self.logger.error(error_msg)
            state['errors'].append(error_msg)
            state['current_step'] = 'extraction_error'
            return state

class PDFValidationAgent:
    """Agent responsible for validating extracted PDF NFe data."""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.logger = logging.getLogger(__name__)
    
    def validate(self, state: PDFAgentState) -> PDFAgentState:
        """Validate the extracted PDF NFe data for consistency and completeness."""
        try:
            self.logger.info("PDF Validation Agent: Starting validation")
            
            extracted_data = state.get('extracted_data', {})
            
            prompt = f"""
            Você é um especialista em validação de dados de NFe brasileira.
            Valide os dados extraídos de uma NFe em PDF e verifique consistência, completude e correção.

            DADOS EXTRAÍDOS:
            {json.dumps(extracted_data, indent=2, ensure_ascii=False)}

            VALIDAÇÕES A REALIZAR:
            1. Verificar se campos obrigatórios estão preenchidos
            2. Validar formatos (CNPJ, CPF, datas, valores)
            3. Verificar consistência entre valores (total = soma dos itens, etc.)
            4. Validar códigos (NCM, CFOP, etc.)
            5. Verificar integridade dos dados dos itens
            6. Calcular score de confiança final (0-100)

            Responda em formato JSON:
            {{
                "is_valid": true/false,
                "validation_score": 0-100,
                "required_fields_missing": ["campo1", "campo2"],
                "format_errors": ["erro1", "erro2"],
                "consistency_issues": ["issue1", "issue2"],
                "data_quality_assessment": "alta/média/baixa",
                "confidence_score": 0-100,
                "validated_data": {{ dados_corrigidos_ou_validados }},
                "validation_notes": ["nota1", "nota2"]
            }}
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024. do not change this unless explicitly requested by the user
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            validation_result = json.loads(response.choices[0].message.content)
            
            # Update state
            state['validated_data'] = validation_result.get('validated_data', extracted_data)
            state['confidence_score'] = min(state['confidence_score'], validation_result.get('confidence_score', 0) / 100.0)
            state['processing_notes'].extend(validation_result.get('validation_notes', []))
            state['current_step'] = 'validation_completed'
            
            # Add any validation errors
            for error_type in ['required_fields_missing', 'format_errors', 'consistency_issues']:
                errors = validation_result.get(error_type, [])
                state['errors'].extend(errors)
            
            self.logger.info(f"PDF validation completed with score: {validation_result.get('validation_score', 0)}")
            return state
            
        except Exception as e:
            error_msg = f"Erro na validação PDF: {str(e)}"
            self.logger.error(error_msg)
            state['errors'].append(error_msg)
            state['current_step'] = 'validation_error'
            return state

class PDFProcessingWorkflow:
    """LangGraph workflow orchestrating the PDF NFe processing agents."""
    
    def __init__(self):
        self.analysis_agent = PDFAnalysisAgent()
        self.extraction_agent = PDFExtractionAgent()
        self.validation_agent = PDFValidationAgent()
        self.workflow = self._build_workflow()
        self.logger = logging.getLogger(__name__)
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow for PDF processing."""
        workflow = StateGraph(PDFAgentState)
        
        # Add nodes
        workflow.add_node("analyze", self.analysis_agent.analyze)
        workflow.add_node("extract", self.extraction_agent.extract)
        workflow.add_node("validate", self.validation_agent.validate)
        
        # Add edges
        workflow.add_edge("analyze", "extract")
        workflow.add_edge("extract", "validate")
        workflow.add_edge("validate", END)
        
        # Set entry point
        workflow.set_entry_point("analyze")
        
        return workflow.compile()
    
    def process_nfe_pdf(self, markdown_content: str, pdf_metadata: Dict[str, Any]) -> PDFProcessingResult:
        """
        Process an NFe PDF through the complete AI workflow.
        
        Args:
            markdown_content (str): Structured markdown from PDF
            pdf_metadata (Dict): PDF metadata and processing info
            
        Returns:
            PDFProcessingResult: Complete processing results
        """
        try:
            self.logger.info("Starting PDF NFe processing workflow")
            
            # Initialize state
            initial_state = PDFAgentState(
                markdown_content=markdown_content,
                pdf_metadata=pdf_metadata,
                analyzed_data={},
                extracted_data={},
                validated_data={},
                confidence_score=1.0,
                errors=[],
                processing_notes=[],
                current_step="starting"
            )
            
            # Run the workflow
            final_state = self.workflow.invoke(initial_state)
            
            # Prepare result
            success = len(final_state['errors']) == 0 and final_state['current_step'] == 'validation_completed'
            
            # Merge PDF metadata with validated data
            final_data = self._merge_pdf_data(pdf_metadata, final_state['validated_data'])
            
            result = PDFProcessingResult(
                success=success,
                data=final_data if success else None,
                confidence_score=final_state['confidence_score'],
                errors=final_state['errors'],
                processing_notes=final_state['processing_notes']
            )
            
            self.logger.info(f"PDF processing workflow completed. Success: {success}")
            return result
            
        except Exception as e:
            error_msg = f"Erro no workflow de processamento PDF: {str(e)}"
            self.logger.error(error_msg)
            
            return PDFProcessingResult(
                success=False,
                data=None,
                confidence_score=0.0,
                errors=[error_msg],
                processing_notes=[]
            )
    
    def _merge_pdf_data(self, pdf_metadata: Dict[str, Any], validated_data: Dict[str, Any]) -> Dict[str, Any]:
        """Merge PDF metadata with AI-validated data."""
        merged_data = validated_data.copy()
        
        # Add PDF processing metadata
        merged_data['_pdf_metadata'] = pdf_metadata
        merged_data['_processing_method'] = 'pdf_ai_workflow'
        
        return merged_data

def process_nfe_pdf_with_ai(markdown_content: str, pdf_metadata: Dict[str, Any]) -> PDFProcessingResult:
    """
    Convenience function to process NFe PDF with AI agents.
    
    Args:
        markdown_content (str): Structured markdown from PDF
        pdf_metadata (Dict): PDF metadata and processing info
        
    Returns:
        PDFProcessingResult: Complete processing results
    """
    workflow = PDFProcessingWorkflow()
    return workflow.process_nfe_pdf(markdown_content, pdf_metadata)