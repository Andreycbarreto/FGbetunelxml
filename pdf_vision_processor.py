"""
PDF NFe Vision Processor
Advanced PDF processing using GPT-4 Vision to analyze PDF pages as images
for more accurate NFe data extraction with proper formatting.
"""

import os
import base64
import logging
import json
from typing import Dict, Any, List
from openai import OpenAI
import pymupdf

logger = logging.getLogger(__name__)

class PDFVisionProcessor:
    """Advanced PDF processor using GPT-4 Vision for NFe analysis."""
    
    def __init__(self):
        self.client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
            timeout=60.0  # 60 second timeout
        )
        self.logger = logging.getLogger(__name__)
    
    def process_pdf_with_vision(self, file_path: str) -> Dict[str, Any]:
        """
        Process a PDF file using GPT-4 Vision to extract NFe data.
        
        Args:
            file_path (str): Path to the PDF file
            
        Returns:
            dict: Extracted NFe data with proper formatting
        """
        try:
            self.logger.info(f"Starting vision-based PDF processing for: {file_path}")
            
            # Convert PDF pages to images
            pdf_images = self._convert_pdf_to_images(file_path)
            
            if not pdf_images:
                raise Exception("Failed to convert PDF to images")
            
            # Analyze each page with GPT-4 Vision
            all_extracted_data = []
            for i, image_data in enumerate(pdf_images):
                self.logger.info(f"Analyzing page {i+1}/{len(pdf_images)} with GPT-4 Vision")
                page_data = self._analyze_page_with_vision(image_data, i+1)
                if page_data:
                    all_extracted_data.append(page_data)
            
            # Consolidate data from all pages
            consolidated_data = self._consolidate_nfe_data(all_extracted_data)
            
            return {
                'success': True,
                'data': consolidated_data,
                'confidence_score': 0.9,  # High confidence for vision processing
                'processing_method': 'GPT-4 Vision',
                'pages_processed': len(pdf_images)
            }
            
        except Exception as e:
            self.logger.error(f"Error in vision-based PDF processing: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'data': {}
            }
    
    def _convert_pdf_to_images(self, file_path: str) -> List[str]:
        """Convert PDF pages to base64 encoded images."""
        try:
            doc = pymupdf.open(file_path)
            images = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                # Render page as image with high resolution
                mat = pymupdf.Matrix(2.0, 2.0)  # 2x zoom for better quality
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("png")
                
                # Convert to base64
                img_base64 = base64.b64encode(img_data).decode('utf-8')
                images.append(img_base64)
                
                self.logger.info(f"Converted page {page_num + 1} to image")
            
            doc.close()
            return images
            
        except Exception as e:
            self.logger.error(f"Error converting PDF to images: {str(e)}")
            return []
    
    def _analyze_page_with_vision(self, image_base64: str, page_num: int) -> Dict[str, Any]:
        """Analyze a PDF page image using GPT-4 Vision."""
        try:
            prompt = """
            Você é um especialista em processamento de Notas Fiscais Eletrônicas brasileiras. Analise esta imagem de NFe e extraia TODAS as informações de forma precisa e completa.

            INSTRUÇÕES CRÍTICAS:
            - Examine cada seção da nota fiscal cuidadosamente
            - Valores monetários: use ponto decimal (ex: 1234.56), sem separadores de milhares
            - Datas: formato YYYY-MM-DD (ex: 2024-12-30)
            - CNPJs/CPFs: apenas números, sem formatação
            - Códigos: exatamente como aparecem na imagem
            - Campos não visíveis ou em branco: use null
            - Para impostos municipais (ISSQN, ISS retido): procure na seção específica de serviços
            - Para impostos federais: procure na seção de totais da NFe

            IMPORTANTE: Identifique se é NFe de PRODUTO (modelo 55) ou SERVIÇO (modelo 57) para extrair os campos corretos.

            Retorne um JSON com esta estrutura COMPLETA:
            {
                "documento": {
                    "numero_nf": "string - número da nota fiscal",
                    "serie": "string - série da nota",
                    "chave_nfe": "string - chave de acesso de 44 dígitos",
                    "data_emissao": "YYYY-MM-DD - data de emissão",
                    "data_saida_entrada": "YYYY-MM-DD - data de saída/entrada",
                    "tipo_operacao": "string - Entrada ou Saída",
                    "natureza_operacao": "string - natureza da operação",
                    "modelo": "string - modelo da NFe (55, 57, etc)",
                    "tipo_documento": "string - produto, servico ou misto"
                },
                "emitente": {
                    "cnpj": "string - CNPJ apenas números",
                    "nome": "string - razão social",
                    "fantasia": "string - nome fantasia",
                    "inscricao_estadual": "string - IE",
                    "inscricao_municipal": "string - IM (para prestadores de serviço)",
                    "endereco": "string - endereço completo",
                    "municipio": "string - cidade",
                    "uf": "string - estado (2 letras)",
                    "cep": "string - CEP"
                },
                "destinatario": {
                    "cnpj": "string - CNPJ apenas números",
                    "nome": "string - razão social",
                    "inscricao_estadual": "string - IE",
                    "inscricao_municipal": "string - IM",
                    "endereco": "string - endereço completo",
                    "municipio": "string - cidade",
                    "uf": "string - estado (2 letras)",
                    "cep": "string - CEP"
                },
                "valores": {
                    "valor_total_produtos": "float - valor total de produtos",
                    "valor_total_servicos": "float - valor total de serviços",
                    "valor_total_nf": "float - valor total da NFe",
                    "valor_icms": "float - valor do ICMS",
                    "valor_ipi": "float - valor do IPI",
                    "valor_pis": "float - valor do PIS",
                    "valor_cofins": "float - valor do COFINS",
                    "valor_issqn": "float - valor do ISSQN (imposto municipal)",
                    "valor_issrf": "float - valor do ISS retido fonte",
                    "valor_ir": "float - valor do IR",
                    "valor_inss": "float - valor do INSS",
                    "valor_csll": "float - valor do CSLL",
                    "valor_iss_retido": "float - valor do ISS retido",
                    "valor_frete": "float - valor do frete",
                    "valor_seguro": "float - valor do seguro",
                    "valor_desconto": "float - valor do desconto",
                    "valor_tributos": "float - valor aproximado dos tributos"
                },
                "transporte": {
                    "modalidade_frete": "string - modalidade do frete",
                    "transportadora_cnpj": "string - CNPJ da transportadora",
                    "transportadora_nome": "string - nome da transportadora"
                },
                "pagamento": {
                    "forma_pagamento": "string - forma de pagamento",
                    "data_vencimento": "YYYY-MM-DD - data de vencimento"
                },
                "autorizacao": {
                    "protocolo_autorizacao": "string - protocolo de autorização",
                    "status_autorizacao": "string - status da autorização",
                    "ambiente": "string - Produção ou Homologação"
                },
                "informacoes_adicionais": "string - informações adicionais da NFe",
                "items": [
                    {
                        "numero_item": "int - número do item",
                        "codigo_produto": "string - código do produto",
                        "codigo_servico": "string - código do serviço (se aplicável)",
                        "codigo_atividade": "string - código da atividade",
                        "descricao_produto": "string - descrição do produto",
                        "descricao_servico": "string - descrição do serviço",
                        "ncm": "string - código NCM",
                        "cfop": "string - código CFOP",
                        "unidade_comercial": "string - unidade comercial",
                        "quantidade_comercial": "float - quantidade comercial",
                        "valor_unitario_comercial": "float - valor unitário comercial",
                        "valor_total_produto": "float - valor total do item",
                        "origem_mercadoria": "string - origem da mercadoria",
                        "situacao_tributaria_icms": "string - situação tributária ICMS",
                        "base_calculo_icms": "float - base de cálculo ICMS",
                        "aliquota_icms": "float - alíquota ICMS",
                        "valor_icms": "float - valor ICMS",
                        "situacao_tributaria_ipi": "string - situação tributária IPI",
                        "valor_ipi": "float - valor IPI",
                        "situacao_tributaria_pis": "string - situação tributária PIS",
                        "base_calculo_pis": "float - base de cálculo PIS",
                        "aliquota_pis": "float - alíquota PIS",
                        "valor_pis": "float - valor PIS",
                        "situacao_tributaria_cofins": "string - situação tributária COFINS",
                        "base_calculo_cofins": "float - base de cálculo COFINS",
                        "aliquota_cofins": "float - alíquota COFINS",
                        "valor_cofins": "float - valor COFINS",
                        "situacao_tributaria_issqn": "string - situação tributária ISSQN",
                        "base_calculo_issqn": "float - base de cálculo ISSQN",
                        "aliquota_issqn": "float - alíquota ISSQN",
                        "valor_issqn": "float - valor ISSQN"
                    }
                ]
            }

            ATENÇÃO ESPECIAL:
            - Se for NFe de serviços, foque nos campos de serviço e impostos municipais
            - Se for NFe de produtos, foque nos campos de produto e impostos estaduais/federais
            - Procure por seções específicas de impostos retidos (IR, INSS, CSLL, ISS)
            - Verifique se há informações adicionais no rodapé da nota
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4o",  # GPT-4 Vision model
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_base64}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                response_format={"type": "json_object"},
                max_tokens=4000
            )
            
            content = response.choices[0].message.content
            if content:
                result = json.loads(content)
            else:
                result = {}
            result['page_number'] = page_num
            
            self.logger.info(f"Successfully analyzed page {page_num} with GPT-4 Vision")
            return result
            
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Error analyzing page {page_num} with vision: {error_msg}")
            
            # Check for specific API errors that should trigger fallback
            if any(err in error_msg.lower() for err in ['502', 'bad gateway', 'cloudflare', 'timeout', 'rate limit']):
                raise Exception(f"API error detected: {error_msg}")
            
            return {}
    
    def _consolidate_nfe_data(self, all_page_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Consolidate NFe data from multiple pages into a single structure."""
        if not all_page_data:
            return {}
        
        # Start with the first page as base
        consolidated = all_page_data[0].copy()
        consolidated.pop('page_number', None)
        
        # Merge items from all pages
        all_items = []
        for page_data in all_page_data:
            items = page_data.get('items', [])
            all_items.extend(items)
        
        # Update consolidated data
        if all_items:
            consolidated['items'] = all_items
        
        # Flatten structure for database compatibility
        flattened = {}
        
        # Document fields
        if 'documento' in consolidated:
            doc = consolidated['documento']
            flattened.update({
                'numero_nf': doc.get('numero_nf'),
                'serie': doc.get('serie'),
                'chave_nfe': doc.get('chave_nfe'),
                'data_emissao': self._parse_date(doc.get('data_emissao')),
                'data_saida_entrada': self._parse_date(doc.get('data_saida_entrada')),
                'tipo_operacao': doc.get('tipo_operacao'),
                'natureza_operacao': doc.get('natureza_operacao'),
                'modelo': doc.get('modelo'),
                'tipo_documento': doc.get('tipo_documento')
            })
        
        # Emitente fields
        if 'emitente' in consolidated:
            emit = consolidated['emitente']
            flattened.update({
                'emitente_cnpj': self._format_cnpj(emit.get('cnpj')),
                'emitente_nome': emit.get('nome'),
                'emitente_fantasia': emit.get('fantasia'),
                'emitente_ie': emit.get('inscricao_estadual'),
                'emitente_im': emit.get('inscricao_municipal'),
                'emitente_endereco': emit.get('endereco'),
                'emitente_municipio': emit.get('municipio'),
                'emitente_uf': emit.get('uf'),
                'emitente_cep': emit.get('cep')
            })
        
        # Destinatario fields
        if 'destinatario' in consolidated:
            dest = consolidated['destinatario']
            flattened.update({
                'destinatario_cnpj': self._format_cnpj(dest.get('cnpj')),
                'destinatario_nome': dest.get('nome'),
                'destinatario_ie': dest.get('inscricao_estadual'),
                'destinatario_im': dest.get('inscricao_municipal'),
                'destinatario_endereco': dest.get('endereco'),
                'destinatario_municipio': dest.get('municipio'),
                'destinatario_uf': dest.get('uf'),
                'destinatario_cep': dest.get('cep')
            })
        
        # Valores fields - incluindo todos os impostos municipais e federais
        if 'valores' in consolidated:
            vals = consolidated['valores']
            flattened.update({
                'valor_total_produtos': self._parse_decimal(vals.get('valor_total_produtos')),
                'valor_total_servicos': self._parse_decimal(vals.get('valor_total_servicos')),
                'valor_total_nf': self._parse_decimal(vals.get('valor_total_nf')),
                'valor_icms': self._parse_decimal(vals.get('valor_icms')),
                'valor_ipi': self._parse_decimal(vals.get('valor_ipi')),
                'valor_pis': self._parse_decimal(vals.get('valor_pis')),
                'valor_cofins': self._parse_decimal(vals.get('valor_cofins')),
                'valor_issqn': self._parse_decimal(vals.get('valor_issqn')),
                'valor_issrf': self._parse_decimal(vals.get('valor_issrf')),
                'valor_ir': self._parse_decimal(vals.get('valor_ir')),
                'valor_inss': self._parse_decimal(vals.get('valor_inss')),
                'valor_csll': self._parse_decimal(vals.get('valor_csll')),
                'valor_iss_retido': self._parse_decimal(vals.get('valor_iss_retido')),
                'valor_frete': self._parse_decimal(vals.get('valor_frete')),
                'valor_seguro': self._parse_decimal(vals.get('valor_seguro')),
                'valor_desconto': self._parse_decimal(vals.get('valor_desconto')),
                'valor_tributos': self._parse_decimal(vals.get('valor_tributos'))
            })
        
        # Transporte fields
        if 'transporte' in consolidated:
            transp = consolidated['transporte']
            flattened.update({
                'modalidade_frete': transp.get('modalidade_frete'),
                'transportadora_cnpj': self._format_cnpj(transp.get('transportadora_cnpj')),
                'transportadora_nome': transp.get('transportadora_nome')
            })
        
        # Pagamento fields
        if 'pagamento' in consolidated:
            pag = consolidated['pagamento']
            flattened.update({
                'forma_pagamento': pag.get('forma_pagamento'),
                'data_vencimento': self._parse_date(pag.get('data_vencimento'))
            })
        
        # Autorizacao fields
        if 'autorizacao' in consolidated:
            auth = consolidated['autorizacao']
            flattened.update({
                'protocolo_autorizacao': auth.get('protocolo_autorizacao'),
                'status_autorizacao': auth.get('status_autorizacao'),
                'ambiente': auth.get('ambiente')
            })
        
        # Informações adicionais
        flattened['informacoes_adicionais'] = consolidated.get('informacoes_adicionais')
        
        # Items
        flattened['items'] = consolidated.get('items', [])
        
        return flattened
    
    def _parse_date(self, date_str):
        """Parse date string to datetime object."""
        if not date_str:
            return None
        try:
            from datetime import datetime
            return datetime.strptime(date_str, '%Y-%m-%d')
        except:
            return None
    
    def _parse_decimal(self, value):
        """Parse decimal value ensuring proper formatting."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    def _format_cnpj(self, cnpj_str):
        """Format CNPJ removing all non-numeric characters."""
        if not cnpj_str:
            return None
        # Remove all non-numeric characters
        return ''.join(filter(str.isdigit, str(cnpj_str)))

def process_nfe_pdf_with_vision(file_path: str) -> Dict[str, Any]:
    """
    Convenience function to process NFe PDF with GPT-4 Vision.
    
    Args:
        file_path (str): Path to the PDF file
        
    Returns:
        dict: Complete processing results
    """
    processor = PDFVisionProcessor()
    return processor.process_pdf_with_vision(file_path)