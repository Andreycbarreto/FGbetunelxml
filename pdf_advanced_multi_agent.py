"""
Advanced Multi-Agent PDF Processing System
Specialized system for precise Brazilian tax extraction and comprehensive item field analysis
"""

import json
import logging
import os
from typing import Dict, Any, List, Optional
from openai import OpenAI
from pdf_vision_processor import PDFVisionProcessor
from comprehensive_tax_validator import apply_comprehensive_tax_validation
import re

logger = logging.getLogger(__name__)

class TaxExpertAgent:
    """Specialized agent for Brazilian tax identification and validation"""
    
    def __init__(self, client: OpenAI):
        self.client = client
        
    def analyze_taxes(self, base64_image: str, document_type: str = "unknown") -> Dict[str, Any]:
        """Deep analysis of Brazilian taxes with fiscal expertise"""
        
        tax_prompt = f"""Você é um especialista em tributação brasileira com décadas de experiência em NFe.
        Analise esta NFe PDF com extrema precisão fiscal.

        DOCUMENT TYPE: {document_type}

        INSTRUÇÕES CRÍTICAS:
        1. IDENTIFIQUE O TIPO DE DOCUMENTO:
           - Modelo 55 = Produtos (ICMS, IPI, PIS, COFINS)
           - Modelo 57/56 = Serviços (ISSQN, IR, INSS, CSLL, ISSRF)
           
        2. IMPOSTOS DE PRODUTOS (quando aplicável):
           - ICMS: Imposto sobre Circulação de Mercadorias
           - IPI: Imposto sobre Produtos Industrializados
           - PIS: Programa de Integração Social
           - COFINS: Contribuição para Financiamento da Seguridade Social
           
        3. IMPOSTOS DE SERVIÇOS (quando aplicável):
           - ISSQN/ISS: Imposto sobre Serviços (municipal)
           - IR: Imposto de Renda retido na fonte (FEDERAL - siglas: IR, IRRF, I.R.)
           - INSS: Contribuição Previdenciária retida (PREVIDENCIÁRIO - siglas: INSS, Prev. Social)
           - CSLL: Contribuição Social sobre Lucro Líquido
           - ISSRF: ISS Retido na Fonte
           
        ATENÇÃO ESPECIAL IR vs INSS:
           - IR: Alíquotas 0.9%, 1.5%, 3.0%, 4.8% - NUNCA 11%
           - INSS: Alíquota típica 11% - NUNCA percentuais baixos como 1.5%
           - IR aparece como "Imposto de Renda", "IRRF", "I.R."
           - INSS aparece como "INSS", "Contribuição Previdenciária", "Prev. Social"
           
        4. REGRAS DE VALIDAÇÃO CRÍTICAS:
           - Valores devem ser numéricos e positivos
           - Soma dos impostos não pode exceder valor total
           - ISS/ISSQN é sempre municipal (2-5% típico)
           - IR retido é federal (0.9-4.8% típico) - SE ENCONTRAR 11% É INSS!
           - INSS retido é previdenciário (11% típico) - SE ENCONTRAR 1.5% É IR!
           - NUNCA confundir: valor com alíquota 11% = INSS, valor com alíquota baixa = IR
           
        5. BUSQUE SEÇÕES ESPECÍFICAS:
           - "Cálculo do Imposto"
           - "Valores Totais da NFe"
           - "Informações Adicionais"
           - "Discriminação dos Serviços"
           - Quadros de totais
           
        RETORNE JSON com precisão absoluta:
        {{
            "document_model": "55/56/57",
            "document_type": "produto/servico/misto",
            "taxes": {{
                "icms": {{"value": 0.00, "found": true/false, "confidence": 0-100}},
                "ipi": {{"value": 0.00, "found": true/false, "confidence": 0-100}},
                "pis": {{"value": 0.00, "found": true/false, "confidence": 0-100}},
                "cofins": {{"value": 0.00, "found": true/false, "confidence": 0-100}},
                "issqn": {{"value": 0.00, "found": true/false, "confidence": 0-100}},
                "ir": {{"value": 0.00, "found": true/false, "confidence": 0-100}},
                "inss": {{"value": 0.00, "found": true/false, "confidence": 0-100}},
                "csll": {{"value": 0.00, "found": true/false, "confidence": 0-100}},
                "iss_retido": {{"value": 0.00, "found": true/false, "confidence": 0-100}}
            }},
            "validation_notes": ["observações específicas"],
            "confidence_score": 0-100
        }}"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": tax_prompt},
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
            logger.info(f"Tax expert analysis: {result.get('confidence_score', 0)}% confidence")
            return result
            
        except Exception as e:
            logger.error(f"Tax expert analysis failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "confidence_score": 0
            }

class ItemExtractionAgent:
    """Specialized agent for comprehensive item field extraction"""
    
    def __init__(self, client: OpenAI):
        self.client = client
        
    def extract_items(self, base64_image: str) -> Dict[str, Any]:
        """Extract comprehensive item information including service codes"""
        
        item_prompt = """Você é um especialista em análise de itens de NFe brasileira.
        Extraia TODOS os campos de itens com precisão absoluta.

        CAMPOS OBRIGATÓRIOS POR ITEM:
        1. IDENTIFICAÇÃO:
           - Número do item (sequencial)
           - Código do produto/serviço
           - Código da atividade (para serviços)
           - Código de serviço municipal (se aplicável)
           
        2. DESCRIÇÃO:
           - Descrição completa do produto/serviço
           - Observações específicas
           
        3. VALORES COMERCIAIS:
           - Quantidade
           - Unidade
           - Valor unitário
           - Valor total
           
        4. CLASSIFICAÇÃO FISCAL:
           - NCM (Nomenclatura Comum do Mercosul)
           - CFOP (Código Fiscal de Operações)
           - CST/CSOSN (Código de Situação Tributária)
           
        5. IMPOSTOS POR ITEM:
           - Base de cálculo de cada imposto
           - Alíquota aplicada
           - Valor do imposto
           
        BUSQUE SEÇÕES:
        - "Dados dos Produtos/Serviços"
        - "Discriminação"
        - "Itens da Nota"
        - Tabelas de produtos/serviços
        
        RETORNE JSON estruturado:
        {{
            "items": [
                {{
                    "item_number": 1,
                    "product_code": "código",
                    "service_code": "código_serviço",
                    "activity_code": "código_atividade", 
                    "description": "descrição completa",
                    "service_description": "descrição serviço específica",
                    "quantity": 1.0,
                    "unit": "UN",
                    "unit_value": 100.00,
                    "total_value": 100.00,
                    "ncm": "código_ncm",
                    "cfop": "código_cfop",
                    "cst": "código_cst",
                    "taxes": {{
                        "icms": {{"base": 0, "rate": 0, "value": 0}},
                        "issqn": {{"base": 0, "rate": 0, "value": 0}}
                    }}
                }}
            ],
            "total_items": 1,
            "confidence_score": 0-100
        }}"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": item_prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                            }
                        ]
                    }
                ],
                max_tokens=2000,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            if content is None:
                raise ValueError("Empty response from OpenAI")
            result = json.loads(content)
            logger.info(f"Item extraction: {len(result.get('items', []))} items, {result.get('confidence_score', 0)}% confidence")
            return result
            
        except Exception as e:
            logger.error(f"Item extraction failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "items": [],
                "confidence_score": 0
            }

class ValidationAgent:
    """Agent for cross-validation and consistency checking"""
    
    def __init__(self, client: OpenAI):
        self.client = client
        
    def validate_extraction(self, tax_data: Dict, item_data: Dict, base64_image: str) -> Dict[str, Any]:
        """Cross-validate tax and item data for consistency"""
        
        validation_prompt = f"""Você é um auditor fiscal especialista em NFe brasileira.
        Valide a consistência entre os dados extraídos e a imagem da NFe.

        DADOS DE IMPOSTOS EXTRAÍDOS:
        {json.dumps(tax_data, indent=2)}
        
        DADOS DE ITENS EXTRAÍDOS:
        {json.dumps(item_data, indent=2)}
        
        VALIDAÇÕES OBRIGATÓRIAS:
        1. CONSISTÊNCIA NUMÉRICA:
           - Soma dos impostos por item vs totais gerais
           - Valores unitários × quantidades = valores totais
           - Base de cálculo vs alíquotas vs valores
           
        2. LÓGICA FISCAL:
           - Impostos aplicáveis ao tipo de documento
           - Alíquotas dentro das faixas legais
           - CST compatível com impostos aplicados
           
        3. CAMPOS OBRIGATÓRIOS:
           - Todos os campos essenciais preenchidos
           - Códigos de serviço para documentos de serviço
           - NCM para produtos
           
        4. CORREÇÕES AUTOMÁTICAS:
           - Ajustar nomes de impostos incorretos
           - Corrigir valores inconsistentes
           - Preencher campos faltantes quando possível
           
        RETORNE JSON com correções:
        {{
            "validation_status": "approved/warning/rejected",
            "corrected_taxes": {{...dados corrigidos...}},
            "corrected_items": {{...dados corrigidos...}},
            "validation_errors": ["lista de erros"],
            "validation_warnings": ["lista de avisos"],
            "corrections_made": ["lista de correções"],
            "final_confidence": 0-100
        }}"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": validation_prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                            }
                        ]
                    }
                ],
                max_tokens=2000,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            if content is None:
                raise ValueError("Empty response from OpenAI")
            result = json.loads(content)
            logger.info(f"Validation complete: {result.get('validation_status', 'unknown')} - {result.get('final_confidence', 0)}% confidence")
            return result
            
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "final_confidence": 0
            }

class AdvancedMultiAgentProcessor:
    """Advanced multi-agent processor with specialized tax and item expertise"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.vision_processor = PDFVisionProcessor()
        self.tax_agent = TaxExpertAgent(self.client)
        self.item_agent = ItemExtractionAgent(self.client)
        self.validation_agent = ValidationAgent(self.client)
        
    def process_pdf_file(self, pdf_path: str) -> Dict[str, Any]:
        """Process PDF with advanced multi-agent system"""
        try:
            logger.info(f"Starting advanced multi-agent processing for: {pdf_path}")
            
            # Get base vision processing
            vision_result = self.vision_processor.process_pdf_with_vision(pdf_path)
            if not vision_result.get('success'):
                return self._fallback_processing(pdf_path)
            
            base64_images = vision_result.get('base64_images', [])
            if not base64_images:
                return self._fallback_processing(pdf_path)
                
            base64_image = base64_images[0]
            
            # Step 1: Tax Expert Analysis
            logger.info("Step 1: Running tax expert analysis...")
            tax_analysis = self.tax_agent.analyze_taxes(base64_image)
            
            # Step 2: Item Field Extraction
            logger.info("Step 2: Extracting comprehensive item fields...")
            item_analysis = self.item_agent.extract_items(base64_image)
            
            # Step 3: Cross-validation
            logger.info("Step 3: Cross-validating extracted data...")
            validation_result = self.validation_agent.validate_extraction(
                tax_analysis, item_analysis, base64_image
            )
            
            # Step 4: Comprehensive Tax Validation (all taxes)
            logger.info("Step 4: Running comprehensive tax validation...")
            pre_validation_result = self._combine_results(
                vision_result, tax_analysis, item_analysis, validation_result
            )
            
            # Apply comprehensive tax validation to fix all tax confusions
            final_result = apply_comprehensive_tax_validation(
                base64_image, pre_validation_result
            )
            
            # Step 5: Final processing notes update
            processing_notes = final_result.get('processing_notes', [])
            processing_notes.append("Advanced multi-agent processing with comprehensive tax validation completed")
            final_result['processing_notes'] = processing_notes
            
            logger.info(f"Advanced processing complete - Final confidence: {final_result.get('confidence_score', 0)}%")
            return final_result
            
        except Exception as e:
            logger.error(f"Advanced multi-agent processing failed: {e}")
            return self._fallback_processing(pdf_path)
    
    def _fallback_processing(self, pdf_path: str) -> Dict[str, Any]:
        """Fallback to simple vision processing if multi-agent fails"""
        logger.warning("Falling back to simple vision processing")
        try:
            return self.vision_processor.process_pdf_with_vision(pdf_path)
        except Exception as e:
            logger.error(f"Fallback processing also failed: {e}")
            return {
                'success': False,
                'error': f'All processing methods failed: {e}',
                'confidence_score': 0
            }
    
    def _combine_results(self, vision_result: Dict, tax_analysis: Dict, 
                        item_analysis: Dict, validation_result: Dict) -> Dict[str, Any]:
        """Combine all agent results into final output"""
        
        # Start with vision result as base
        final_result = vision_result.copy()
        
        # Apply tax corrections if validation was successful
        if validation_result.get('validation_status') != 'rejected':
            corrected_taxes = validation_result.get('corrected_taxes', {})
            if corrected_taxes:
                # Update tax values with corrected data
                tax_mapping = {
                    'icms': 'valor_icms',
                    'ipi': 'valor_ipi', 
                    'pis': 'valor_pis',
                    'cofins': 'valor_cofins',
                    'issqn': 'valor_issqn',
                    'ir': 'valor_ir',
                    'inss': 'valor_inss',
                    'csll': 'valor_csll',
                    'iss_retido': 'valor_iss_retido'
                }
                
                for tax_key, field_name in tax_mapping.items():
                    if tax_key in corrected_taxes.get('taxes', {}):
                        tax_info = corrected_taxes['taxes'][tax_key]
                        if tax_info.get('found') and tax_info.get('value', 0) > 0:
                            final_result[field_name] = tax_info['value']
        
        # Apply item corrections
        corrected_items = validation_result.get('corrected_items', item_analysis)
        if corrected_items.get('items'):
            final_result['items'] = corrected_items['items']
            
            # Enhance item data with service-specific fields
            enhanced_items = []
            for item in corrected_items['items']:
                enhanced_item = {
                    'numero_item': item.get('item_number', 1),
                    'codigo_produto': item.get('product_code'),
                    'codigo_servico': item.get('service_code'),
                    'codigo_atividade': item.get('activity_code'),
                    'descricao_produto': item.get('description'),
                    'descricao_servico': item.get('service_description'),
                    'ncm': item.get('ncm'),
                    'cfop': item.get('cfop'),
                    'quantidade_comercial': item.get('quantity', 1),
                    'unidade_comercial': item.get('unit', 'UN'),
                    'valor_unitario_comercial': item.get('unit_value', 0),
                    'valor_total_produto': item.get('total_value', 0),
                    # Tax details per item
                    'situacao_tributaria_icms': item.get('cst'),
                }
                
                # Add tax values per item if available
                item_taxes = item.get('taxes', {})
                if 'icms' in item_taxes:
                    enhanced_item.update({
                        'base_calculo_icms': item_taxes['icms'].get('base', 0),
                        'aliquota_icms': item_taxes['icms'].get('rate', 0),
                        'valor_icms': item_taxes['icms'].get('value', 0)
                    })
                
                if 'issqn' in item_taxes:
                    enhanced_item.update({
                        'base_calculo_issqn': item_taxes['issqn'].get('base', 0),
                        'aliquota_issqn': item_taxes['issqn'].get('rate', 0),
                        'valor_issqn': item_taxes['issqn'].get('value', 0)
                    })
                
                enhanced_items.append(enhanced_item)
            
            final_result['items'] = enhanced_items
        
        # Update confidence score based on validation
        final_confidence = validation_result.get('final_confidence', 
                                               tax_analysis.get('confidence_score', 0))
        final_result['confidence_score'] = final_confidence
        
        # Add processing notes
        processing_notes = final_result.get('processing_notes', [])
        processing_notes.extend([
            f"Advanced multi-agent processing completed",
            f"Tax analysis confidence: {tax_analysis.get('confidence_score', 0)}%",
            f"Item extraction confidence: {item_analysis.get('confidence_score', 0)}%",
            f"Validation status: {validation_result.get('validation_status', 'unknown')}"
        ])
        
        if validation_result.get('corrections_made'):
            processing_notes.extend(validation_result['corrections_made'])
            
        final_result['processing_notes'] = processing_notes
        
        return final_result