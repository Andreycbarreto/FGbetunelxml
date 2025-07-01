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
from final_tax_processor import process_taxes_final

logger = logging.getLogger(__name__)

class PDFVisionProcessor:
    """Advanced PDF processor using GPT-4 Vision for NFe analysis."""
    
    def __init__(self):
        self.client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
            timeout=60.0  # 60 second timeout
        )
        self.logger = logging.getLogger(__name__)
        self._current_image_base64 = None  # Store current image for tax extraction
    
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
            
            # Store images for precise tax extraction
            self._document_images = pdf_images
            
            # Process each page with specialized multi-stage analysis
            all_extracted_data = []
            for i, image_data in enumerate(pdf_images):
                self.logger.info(f"Processing page {i+1}/{len(pdf_images)} with multi-stage analysis")
                
                # Stage 1: Extract document header data
                header_data = self._extract_header_data(image_data, i+1)
                
                # Stage 2: Extract fiscal values and taxes
                fiscal_data = self._extract_fiscal_data(image_data, i+1)
                
                # Stage 3: Extract items with commercial values
                items_data = self._extract_items_detailed(image_data, i+1)
                
                # Stage 4: Extract additional information
                additional_data = self._extract_additional_info(image_data, i+1)
                
                # Combine all data from stages
                combined_data = self._combine_extraction_stages(header_data, fiscal_data, items_data, additional_data, i+1)
                
                if combined_data:
                    all_extracted_data.append(combined_data)
            
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
            # Store current image for tax extraction
            self._current_image_base64 = image_base64
            
            # First, detect document type to optimize prompt
            doc_type = self._detect_document_type(image_base64)
            
            # Create specialized prompt based on document type
            if doc_type == 'service':
                prompt = self._create_service_prompt()
            elif doc_type == 'product':
                prompt = self._create_product_prompt()
            else:
                prompt = self._create_general_prompt()
                
            prompt = prompt + """
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

            ATENÇÃO CRÍTICA PARA IDENTIFICAÇÃO DE IMPOSTOS:
            Examine CUIDADOSAMENTE cada linha da tabela de impostos. NUNCA confunda:
            
            1. IR (Imposto de Renda):
               - Alíquotas: 1,5%, 3,0%, 4,8%
               - Aparece como: "IR", "I.R.", "IRRF", "Imp. Renda", "IR Retido"
               - Valores típicos: R$ 30,00 a R$ 200,00
            
            2. PIS (Programa Integração Social):
               - Alíquotas: 0,65%, 1,65%
               - Aparece como: "PIS", "P.I.S.", "Contrib. PIS"
               - Valores típicos: R$ 10,00 a R$ 50,00
            
            3. INSS (Previdência Social):
               - Alíquota: SEMPRE 11,0%
               - Aparece como: "INSS", "I.N.S.S.", "Contrib. Prev.", "Prev. Social"
               - Valores típicos: R$ 100,00 a R$ 500,00
            
            4. COFINS (Contribuição Social):
               - Alíquotas: 3,0%, 7,6%
               - Aparece como: "COFINS", "C.O.F.I.N.S."
               - Valores típicos: R$ 50,00 a R$ 300,00
            
            REGRA FUNDAMENTAL: Leia o NOME EXATO do imposto na NFe, não faça suposições baseadas apenas no valor.

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
                    "valor_pis": "float - valor do PIS (procure na seção Impostos Federais/Estaduais)",
                    "valor_cofins": "float - valor do COFINS (procure na seção Impostos Federais/Estaduais)",
                    "valor_issqn": "float - valor do ISSQN (procure na seção Impostos Municipais/Retidos)",
                    "valor_issrf": "float - valor do ISS retido fonte (procure na seção Impostos Municipais/Retidos)",
                    "valor_ir": "float - valor do IR RETIDO (procure especificamente por 'IR Retido' na seção Impostos Municipais/Retidos)",
                    "valor_inss": "float - valor do INSS RETIDO (procure especificamente por 'INSS Retido' na seção Impostos Municipais/Retidos)",
                    "valor_csll": "float - valor do CSLL RETIDO (procure especificamente por 'CSLL Retido' na seção Impostos Municipais/Retidos)",
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

            INSTRUÇÕES CRÍTICAS PARA ITENS:
            - Localize a seção "DADOS DOS PRODUTOS/SERVIÇOS" na NFe
            - Para cada item, extraia TODOS os valores da tabela de produtos/serviços
            - Valores comerciais: quantidade, valor unitário, valor total SEMPRE presentes
            - Valores tributários: procure na seção de impostos de cada item
            - IMPORTANTE: Se há vários itens, liste TODOS eles no array "items"
            - Verifique se existem páginas adicionais com mais itens
            - Para serviços: procure códigos de atividade e descrições específicas
            
            LOCALIZAÇÕES DOS VALORES DOS ITENS:
            - Quantidade: coluna "Qtde" ou "Quantidade"
            - Valor Unitário: coluna "Vl. Unit." ou "Valor Unitário"
            - Valor Total: coluna "Vl. Total" ou "Valor Total"
            - NCM: coluna "NCM/SH" 
            - CFOP: coluna "CFOP"
            - Impostos: seção inferior da tabela ou seção específica de tributos
            
            SE FOR NFe DE SERVIÇOS:
            - Procure campos de serviço e impostos municipais (ISSQN)
            - Códigos de serviço municipal e atividade
            
            SE FOR NFe DE PRODUTOS:
            - Foque em impostos estaduais/federais (ICMS, IPI, PIS, COFINS)
            - Códigos NCM obrigatórios
            
            ATENÇÃO: Analise TODA a estrutura de itens da NFe, não apenas o primeiro item!
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
        
        # Merge items from all pages with validation
        all_items = []
        for page_data in all_page_data:
            items = page_data.get('items', [])
            # Validate and clean items data
            for item in items:
                validated_item = self._validate_item_data(item)
                if validated_item:
                    all_items.append(validated_item)
        
        # Update consolidated data
        if all_items:
            consolidated['items'] = all_items
            self.logger.info(f"Consolidated {len(all_items)} items from all pages")
        
        # Flatten structure for database compatibility
        flattened = {}
        
        # Document fields
        if 'documento' in consolidated:
            doc = consolidated['documento']
            flattened.update({
                'numero_nf': self._validate_field_length(doc.get('numero_nf'), 20),
                'serie': self._validate_field_length(doc.get('serie'), 10),
                'chave_nfe': self._validate_field_length(doc.get('chave_nfe'), 44),
                'data_emissao': self._parse_date(doc.get('data_emissao')),
                'data_saida_entrada': self._parse_date(doc.get('data_saida_entrada')),
                'tipo_operacao': self._validate_field_length(doc.get('tipo_operacao'), 50),
                'natureza_operacao': self._validate_field_length(doc.get('natureza_operacao'), 200),
                'modelo': self._validate_field_length(doc.get('modelo'), 100),
                'tipo_documento': self._validate_field_length(doc.get('tipo_documento'), 20)
            })
        
        # Emitente fields
        if 'emitente' in consolidated:
            emit = consolidated['emitente']
            flattened.update({
                'emitente_cnpj': self._validate_field_length(self._format_cnpj(emit.get('cnpj')), 18),
                'emitente_nome': self._validate_field_length(emit.get('nome'), 255),
                'emitente_fantasia': self._validate_field_length(emit.get('fantasia'), 255),
                'emitente_ie': self._validate_field_length(emit.get('inscricao_estadual'), 20),
                'emitente_im': self._validate_field_length(emit.get('inscricao_municipal'), 20),
                'emitente_endereco': emit.get('endereco'),  # TEXT field - no limit
                'emitente_municipio': self._validate_field_length(emit.get('municipio'), 100),
                'emitente_uf': self._validate_uf(emit.get('uf')),
                'emitente_cep': self._validate_field_length(emit.get('cep'), 10)
            })
        
        # Destinatario fields
        if 'destinatario' in consolidated:
            dest = consolidated['destinatario']
            flattened.update({
                'destinatario_cnpj': self._validate_field_length(self._format_cnpj(dest.get('cnpj')), 18),
                'destinatario_nome': self._validate_field_length(dest.get('nome'), 255),
                'destinatario_ie': self._validate_field_length(dest.get('inscricao_estadual'), 20),
                'destinatario_im': self._validate_field_length(dest.get('inscricao_municipal'), 20),
                'destinatario_endereco': dest.get('endereco'),  # TEXT field - no limit
                'destinatario_municipio': self._validate_field_length(dest.get('municipio'), 100),
                'destinatario_uf': self._validate_uf(dest.get('uf')),
                'destinatario_cep': self._validate_field_length(dest.get('cep'), 10)
            })
        
        # Valores fields - incluindo todos os impostos municipais e federais
        if 'valores' in consolidated:
            vals = consolidated['valores']
            
            # Parse service values with special handling for bruto vs líquido
            valor_servicos = self._parse_decimal(vals.get('valor_total_servicos'))
            valor_total_nf = self._parse_decimal(vals.get('valor_total_nf'))
            
            # Log values for debugging
            self.logger.info(f"Service value extraction: valor_servicos={valor_servicos}, valor_total_nf={valor_total_nf}")
            
            # Special handling for service documents
            if valor_servicos and valor_total_nf:
                # If service value exists and is different from total, it's likely bruto
                if valor_servicos != valor_total_nf:
                    self.logger.info(f"Service document detected - using BRUTO value: {valor_servicos}")
            
            # Use standard extraction for non-tax values
            flattened.update({
                'valor_total_produtos': self._parse_decimal(vals.get('valor_total_produtos')),
                'valor_total_servicos': valor_servicos,
                'valor_total_nf': valor_total_nf,
                'valor_frete': self._parse_decimal(vals.get('valor_frete')),
                'valor_seguro': self._parse_decimal(vals.get('valor_seguro')),
                'valor_desconto': self._parse_decimal(vals.get('valor_desconto')),
                'valor_tributos': self._parse_decimal(vals.get('valor_tributos'))
            })
            
            # Use FINAL tax processor - comprehensive solution!
            self.logger.info("Using FINAL tax processor for complete accuracy")
            try:
                # Get image and service value for processing
                image_for_taxes = None
                if hasattr(self, '_document_images') and self._document_images:
                    image_for_taxes = self._document_images[0]
                elif hasattr(self, '_current_image_base64') and self._current_image_base64:
                    image_for_taxes = self._current_image_base64
                
                if image_for_taxes:
                    # Get service value for rate validation
                    total_service_value = self._parse_decimal(vals.get('valor_total_servicos', 0))
                    
                    self.logger.info(f"Processing taxes with service value: {total_service_value}")
                    final_taxes = process_taxes_final(image_for_taxes, total_service_value)
                    self.logger.info(f"FINAL tax processing results: {final_taxes}")
                    flattened.update(final_taxes)
                else:
                    # No image available - set all taxes to zero
                    self.logger.warning("No image available - setting all taxes to zero")
                    flattened.update({
                        'valor_icms': 0.0,
                        'valor_ipi': 0.0,
                        'valor_pis': 0.0,
                        'valor_cofins': 0.0,
                        'valor_issqn': 0.0,
                        'valor_issrf': 0.0,
                        'valor_ir': 0.0,
                        'valor_inss': 0.0,
                        'valor_csll': 0.0,
                        'valor_iss_retido': 0.0
                    })
            except Exception as e:
                self.logger.error(f"Error in final tax processing: {str(e)}")
                # Set to zero instead of inventing values
                self.logger.warning("Setting all taxes to zero due to error")
                flattened.update({
                    'valor_icms': 0.0,
                    'valor_ipi': 0.0,
                    'valor_pis': 0.0,
                    'valor_cofins': 0.0,
                    'valor_issqn': 0.0,
                    'valor_issrf': 0.0,
                    'valor_ir': 0.0,
                    'valor_inss': 0.0,
                    'valor_csll': 0.0,
                    'valor_iss_retido': 0.0
                })
        
        # Transporte fields
        if 'transporte' in consolidated:
            transp = consolidated['transporte']
            flattened.update({
                'modalidade_frete': self._validate_field_length(transp.get('modalidade_frete'), 50),
                'transportadora_cnpj': self._validate_field_length(self._format_cnpj(transp.get('transportadora_cnpj')), 18),
                'transportadora_nome': self._validate_field_length(transp.get('transportadora_nome'), 255)
            })
        
        # Pagamento fields
        if 'pagamento' in consolidated:
            pag = consolidated['pagamento']
            flattened.update({
                'forma_pagamento': self._validate_field_length(pag.get('forma_pagamento'), 150),
                'data_vencimento': self._parse_date(pag.get('data_vencimento'))
            })
        
        # Autorizacao fields
        if 'autorizacao' in consolidated:
            auth = consolidated['autorizacao']
            flattened.update({
                'protocolo_autorizacao': self._validate_field_length(auth.get('protocolo_autorizacao'), 100),
                'status_autorizacao': self._validate_field_length(auth.get('status_autorizacao'), 50),
                'ambiente': self._validate_field_length(auth.get('ambiente'), 50)
            })
        
        # Informações adicionais
        flattened['informacoes_adicionais'] = consolidated.get('informacoes_adicionais')
        
        # Items - processar cada item com todos os detalhes tributários
        items = consolidated.get('items', [])
        processed_items = []
        for item in items:
            processed_item = self._process_item_details(item)
            processed_items.append(processed_item)
        
        flattened['items'] = processed_items
        
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
            return 0.0
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0
    
    def _format_cnpj(self, cnpj_str):
        """Format CNPJ removing all non-numeric characters."""
        if not cnpj_str:
            return None
        # Remove all non-numeric characters
        return ''.join(filter(str.isdigit, str(cnpj_str)))
    
    def _validate_uf(self, uf_str):
        """Validate and clean UF (state) string."""
        if not uf_str or uf_str == 'string' or len(str(uf_str)) > 2:
            return None
        uf = str(uf_str).strip().upper()
        # Lista de UFs válidos no Brasil
        valid_ufs = ['AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 
                     'MT', 'MS', 'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 
                     'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO']
        return uf if uf in valid_ufs else None
    
    def _validate_field_length(self, value, max_length):
        """Validate field length to prevent database truncation errors."""
        if not value or value == 'string':
            return None
        str_value = str(value).strip()
        if len(str_value) > max_length:
            self.logger.warning(f"Field value truncated from {len(str_value)} to {max_length} chars: {str_value[:50]}...")
            return str_value[:max_length]
        return str_value
    
    def _process_item_details(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Process individual item details with all tax information."""
        processed = {}
        
        # Item identification
        processed.update({
            'numero_item': item.get('numero_item'),
            'codigo_produto': item.get('codigo_produto'),
            'codigo_servico': item.get('codigo_servico'),
            'codigo_atividade': item.get('codigo_atividade'),
            'descricao_produto': item.get('descricao_produto'),
            'descricao_servico': item.get('descricao_servico'),
            'ncm': item.get('ncm'),
            'cfop': item.get('cfop')
        })
        
        # Commercial values
        processed.update({
            'unidade_comercial': item.get('unidade_comercial'),
            'quantidade_comercial': self._parse_decimal(item.get('quantidade_comercial')),
            'valor_unitario_comercial': self._parse_decimal(item.get('valor_unitario_comercial')),
            'valor_total_produto': self._parse_decimal(item.get('valor_total_produto'))
        })
        
        # Tax values
        processed.update({
            'origem_mercadoria': item.get('origem_mercadoria'),
            'situacao_tributaria_icms': item.get('situacao_tributaria_icms'),
            'base_calculo_icms': self._parse_decimal(item.get('base_calculo_icms')),
            'aliquota_icms': self._parse_decimal(item.get('aliquota_icms')),
            'valor_icms': self._parse_decimal(item.get('valor_icms')),
            'situacao_tributaria_ipi': item.get('situacao_tributaria_ipi'),
            'valor_ipi': self._parse_decimal(item.get('valor_ipi')),
            'situacao_tributaria_pis': item.get('situacao_tributaria_pis'),
            'base_calculo_pis': self._parse_decimal(item.get('base_calculo_pis')),
            'aliquota_pis': self._parse_decimal(item.get('aliquota_pis')),
            'valor_pis': self._parse_decimal(item.get('valor_pis')),
            'situacao_tributaria_cofins': item.get('situacao_tributaria_cofins'),
            'base_calculo_cofins': self._parse_decimal(item.get('base_calculo_cofins')),
            'aliquota_cofins': self._parse_decimal(item.get('aliquota_cofins')),
            'valor_cofins': self._parse_decimal(item.get('valor_cofins')),
            'situacao_tributaria_issqn': item.get('situacao_tributaria_issqn'),
            'base_calculo_issqn': self._parse_decimal(item.get('base_calculo_issqn')),
            'aliquota_issqn': self._parse_decimal(item.get('aliquota_issqn')),
            'valor_issqn': self._parse_decimal(item.get('valor_issqn'))
        })
        
        return processed
    
    def _validate_item_data(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and ensure item data has required commercial values."""
        if not item:
            return None
            
        # Essential fields that must have valid values
        required_fields = ['quantidade_comercial', 'valor_unitario_comercial', 'valor_total_produto']
        
        # Check if item has essential commercial data
        has_essential_data = False
        for field in required_fields:
            value = item.get(field)
            if value is not None and value != 0:
                has_essential_data = True
                break
        
        if not has_essential_data:
            self.logger.warning(f"Item missing essential commercial data: {item}")
            return None
        
        # Ensure numeric values are properly formatted
        validated = {}
        for key, value in item.items():
            if key in ['quantidade_comercial', 'valor_unitario_comercial', 'valor_total_produto',
                      'base_calculo_icms', 'aliquota_icms', 'valor_icms', 'valor_ipi',
                      'valor_pis', 'valor_cofins', 'valor_issqn']:
                validated[key] = self._parse_decimal(value)
            else:
                validated[key] = value
        
        # Calculate missing total if we have quantity and unit price
        qtd = validated.get('quantidade_comercial')
        unit_price = validated.get('valor_unitario_comercial')
        total = validated.get('valor_total_produto')
        
        if qtd and unit_price and not total:
            validated['valor_total_produto'] = round(float(qtd) * float(unit_price), 2)
            self.logger.info(f"Calculated missing total: {validated['valor_total_produto']}")
        
        return validated
    
    def _detect_document_type(self, image_base64: str) -> str:
        """Quick detection of document type to optimize processing."""
        try:
            quick_prompt = """
            Analise rapidamente esta imagem de NFe e identifique apenas o TIPO DE DOCUMENTO.
            
            Responda apenas com uma palavra:
            - "service" se for NFe de serviços (modelo 57 ou contém seção de serviços/ISSQN)
            - "product" se for NFe de produtos (modelo 55 ou contém produtos/ICMS)
            - "mixed" se contém produtos e serviços
            
            Resposta:
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": quick_prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                        ]
                    }
                ],
                max_tokens=50
            )
            
            content = response.choices[0].message.content
            if content:
                result = content.strip().lower()
                return result if result in ['service', 'product', 'mixed'] else 'general'
            return 'general'
            
        except Exception as e:
            self.logger.warning(f"Could not detect document type: {str(e)}")
            return 'general'
    
    def _create_service_prompt(self) -> str:
        """Create specialized prompt for service NFe documents."""
        return """
        FOCO ESPECIAL EM NFe DE SERVIÇOS:
        - Priorize informações municipais: ISSQN, ISS retido, Inscrição Municipal
        - Procure códigos de serviço e atividade
        - Identifique retenções na fonte: IR, INSS, CSLL, ISS
        - Verifique seções específicas de impostos municipais
        """
    
    def _create_product_prompt(self) -> str:
        """Create specialized prompt for product NFe documents."""
        return """
        FOCO ESPECIAL EM NFe DE PRODUTOS:
        - Priorize informações estaduais/federais: ICMS, IPI, PIS, COFINS
        - Procure códigos NCM e CFOP detalhados
        - Identifique origem da mercadoria
        - Verifique informações de transporte e frete
        """
    
    def _create_general_prompt(self) -> str:
        """Create general prompt for mixed or unidentified documents."""
        return """
        PROCESSAMENTO COMPLETO:
        - Analise todas as seções da NFe cuidadosamente
        - Identifique se há produtos, serviços ou ambos
        - Extraia todos os impostos (municipais e estaduais)
        """
    
    def _analyze_items_section(self, image_base64: str, page_num: int) -> Dict[str, Any]:
        """Analyze specifically the items section of the NFe for detailed product/service extraction."""
        try:
            items_prompt = """
            Você é um especialista em extrair dados de itens de Notas Fiscais Eletrônicas brasileiras.
            
            FOCO EXCLUSIVO: Analise APENAS a seção de ITENS/PRODUTOS/SERVIÇOS desta NFe.
            
            LOCALIZAÇÃO: Procure pela tabela que contém:
            - "DADOS DOS PRODUTOS E SERVIÇOS" ou
            - "DISCRIMINAÇÃO DOS SERVIÇOS" ou 
            - Tabela com colunas: Código, Descrição, Qtde, Vl.Unit., Vl.Total, etc.
            
            EXTRAÇÃO OBRIGATÓRIA para cada item encontrado:
            1. Número do item (sequencial: 1, 2, 3...)
            2. Código do produto/serviço
            3. Descrição completa
            4. Quantidade (SEMPRE presente)
            5. Valor unitário (SEMPRE presente) 
            6. Valor total (SEMPRE presente)
            7. Unidade de medida
            8. NCM (se produto)
            9. CFOP
            10. Informações tributárias específicas de cada item
            
            ATENÇÃO ESPECIAL AOS VALORES:
            - Quantidade: procure na coluna "Qtde", "Quantidade", "Quant."
            - Valor Unitário: procure na coluna "Vl. Unit.", "Valor Unit.", "V.Unit"
            - Valor Total: procure na coluna "Vl. Total", "Valor Total", "V.Total"
            - Unidade: procure na coluna "Un", "Unid", "Unidade"
            
            IMPORTANTE:
            - Se encontrar múltiplos itens, liste TODOS no array
            - Valores monetários sempre com ponto decimal (ex: 123.45)
            - Se um campo não estiver visível, use null
            - Mantenha a ordem sequencial dos itens
            
            Retorne APENAS um JSON com esta estrutura:
            {
                "items": [
                    {
                        "numero_item": 1,
                        "codigo_produto": "string",
                        "codigo_servico": "string",
                        "descricao_produto": "string completa",
                        "descricao_servico": "string completa",
                        "quantidade_comercial": float,
                        "valor_unitario_comercial": float,
                        "valor_total_produto": float,
                        "unidade_comercial": "string",
                        "ncm": "string",
                        "cfop": "string",
                        "origem_mercadoria": "string",
                        "situacao_tributaria_icms": "string",
                        "base_calculo_icms": float,
                        "aliquota_icms": float,
                        "valor_icms": float,
                        "valor_ipi": float,
                        "valor_pis": float,
                        "valor_cofins": float,
                        "valor_issqn": float
                    }
                ]
            }
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": items_prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                        ]
                    }
                ],
                response_format={"type": "json_object"},
                max_tokens=3000
            )
            
            content = response.choices[0].message.content
            if content:
                result = json.loads(content)
                items = result.get('items', [])
                self.logger.info(f"Successfully extracted {len(items)} items from page {page_num}")
                
                # Log detailed item information for debugging
                for i, item in enumerate(items):
                    qtd = item.get('quantidade_comercial')
                    unit_price = item.get('valor_unitario_comercial')
                    total = item.get('valor_total_produto')
                    desc = item.get('descricao_produto', item.get('descricao_servico', 'N/A'))[:50]
                    
                    self.logger.info(f"Item {i+1}: {desc} - Qtd: {qtd}, Unit: {unit_price}, Total: {total}")
                
                return result
            else:
                return {}
                
        except Exception as e:
            self.logger.error(f"Error analyzing items section on page {page_num}: {str(e)}")
            return {}
    
    def _extract_header_data(self, image_base64: str, page_num: int) -> Dict[str, Any]:
        """Extract document header information (emitente, destinatário, identificação)."""
        try:
            header_prompt = """
            FOCO EXCLUSIVO: Extraia APENAS os dados do CABEÇALHO da NFe.
            
            Procure pelas seções:
            - IDENTIFICAÇÃO DA NOTA FISCAL
            - DADOS DO EMITENTE 
            - DADOS DO DESTINATÁRIO
            - CHAVE DE ACESSO
            
            Retorne JSON com esta estrutura exata:
            {
                "documento": {
                    "numero_nf": "string",
                    "serie": "string", 
                    "chave_nfe": "string de 44 dígitos",
                    "data_emissao": "YYYY-MM-DD",
                    "data_saida_entrada": "YYYY-MM-DD",
                    "tipo_operacao": "string",
                    "natureza_operacao": "string",
                    "modelo": "string"
                },
                "emitente": {
                    "cnpj": "apenas números",
                    "nome": "string",
                    "fantasia": "string",
                    "inscricao_estadual": "string",
                    "inscricao_municipal": "string",
                    "endereco": "string completo",
                    "municipio": "string",
                    "uf": "string",
                    "cep": "string"
                },
                "destinatario": {
                    "cnpj": "apenas números",
                    "nome": "string",
                    "inscricao_estadual": "string", 
                    "inscricao_municipal": "string",
                    "endereco": "string completo",
                    "municipio": "string",
                    "uf": "string",
                    "cep": "string"
                }
            }
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": header_prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                        ]
                    }
                ],
                response_format={"type": "json_object"},
                max_tokens=2000
            )
            
            content = response.choices[0].message.content
            if content:
                result = json.loads(content)
                self.logger.info(f"Successfully extracted header data from page {page_num}")
                return result
            return {}
            
        except Exception as e:
            self.logger.error(f"Error extracting header data from page {page_num}: {str(e)}")
            return {}
    
    def _extract_fiscal_data(self, image_base64: str, page_num: int) -> Dict[str, Any]:
        """Extract fiscal values and tax information."""
        try:
            fiscal_prompt = """
            FOCO EXCLUSIVO: Extraia VALORES FISCAIS COMPLETOS da NFe - VALORES BRUTOS E LÍQUIDOS.
            
            Procure pelas seções:
            - CÁLCULO DO IMPOSTO (seção detalhada)
            - TOTAIS DA NOTA FISCAL (caixa de valores)
            - DADOS ADICIONAIS (informações importantes)
            - RETENÇÕES E DEDUÇÕES
            
            CRITICAL: Para SERVIÇOS, identifique:
            - Valor BRUTO dos serviços (antes das deduções)
            - Valor LÍQUIDO (após deduções de impostos retidos)
            - Valor total da nota (pode ser bruto ou líquido)
            
            CRITICAL: Para PRODUTOS, identifique:
            - Valor total dos produtos
            - Impostos incidentes (ICMS, IPI, PIS, COFINS)
            
            Extraia EXATAMENTE como aparece na nota:
            
            Retorne JSON:
            {
                "valores": {
                    "valor_total_produtos": "float - valor total de produtos",
                    "valor_total_servicos": "float - valor BRUTO de serviços",
                    "valor_total_nf": "float - valor total da NFe (pode ser bruto ou líquido)",
                    "valor_icms": "float - ICMS da nota",
                    "valor_ipi": "float - IPI da nota",
                    "valor_pis": "float - PIS da nota (seção Impostos Federais/Estaduais)",
                    "valor_cofins": "float - COFINS da nota (seção Impostos Federais/Estaduais)",
                    "valor_issqn": "float - ISSQN (ISS) da nota (seção Impostos Municipais/Retidos)",
                    "valor_issrf": "float - ISS retido na fonte (busque por 'ISSRF' ou 'ISS Ret. Fonte')",
                    "valor_ir": "float - IR retido (busque ESPECIFICAMENTE por 'IR Retido' - NÃO confundir com PIS)",
                    "valor_inss": "float - INSS retido (busque por 'INSS Retido' - alíquota 11%)",
                    "valor_csll": "float - CSLL retido (busque por 'CSLL Retido')",
                    "valor_iss_retido": "float - ISS retido",
                    "valor_frete": "float - valor do frete",
                    "valor_seguro": "float - valor do seguro",
                    "valor_desconto": "float - descontos aplicados",
                    "valor_tributos": "float - valor aproximado total de tributos"
                },
                "transporte": {
                    "modalidade_frete": "string - modalidade de frete",
                    "transportadora_cnpj": "string - CNPJ transportadora",
                    "transportadora_nome": "string - nome transportadora"
                },
                "pagamento": {
                    "forma_pagamento": "string - forma de pagamento",
                    "data_vencimento": "YYYY-MM-DD - data vencimento"
                }
            }
            
            ATENÇÃO CRÍTICA: Se for NFe de SERVIÇOS, procure especialmente por:
            - Seção "Cálculo do ISS"
            - Seção "Impostos Municipais/Retidos" para IR, INSS, CSLL
            - Valor bruto vs valor líquido do serviço
            
            REGRA FUNDAMENTAL PARA EVITAR CONFUSÕES:
            - Na seção "Impostos Municipais/Retidos", se vir uma linha com "IR" ou "IR Retido", mapeie para valor_ir
            - Na seção "Impostos Federais/Estaduais", se vir uma linha com "PIS", mapeie para valor_pis
            - NUNCA troque IR por PIS ou vice-versa
            - Leia o NOME EXATO do imposto na NFe, não apenas o valor
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": fiscal_prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                        ]
                    }
                ],
                response_format={"type": "json_object"},
                max_tokens=2000
            )
            
            content = response.choices[0].message.content
            if content:
                result = json.loads(content)
                self.logger.info(f"Successfully extracted fiscal data from page {page_num}")
                return result
            return {}
            
        except Exception as e:
            self.logger.error(f"Error extracting fiscal data from page {page_num}: {str(e)}")
            return {}
    
    def _extract_items_detailed(self, image_base64: str, page_num: int) -> Dict[str, Any]:
        """Extract items with detailed commercial and tax values."""
        try:
            items_prompt = """
            FOCO EXCLUSIVO: Extraia APENAS os ITENS/PRODUTOS/SERVIÇOS da tabela principal.
            
            Localize a tabela com colunas como:
            - Código, Descrição, Quantidade, Valor Unitário, Valor Total
            - NCM, CFOP, Unidade
            
            CRÍTICO: Para cada item, extraia:
            1. Todos os valores comerciais (quantidade, valor unitário, valor total)
            2. Códigos de identificação
            3. Descrição completa
            
            Se for SERVIÇO, procure:
            - Código do serviço municipal
            - Código de atividade
            - Descrição do serviço
            
            Retorne JSON:
            {
                "items": [
                    {
                        "numero_item": 1,
                        "codigo_produto": "string",
                        "codigo_servico": "string", 
                        "codigo_atividade": "string",
                        "descricao_produto": "string completa",
                        "descricao_servico": "string completa",
                        "quantidade_comercial": float,
                        "valor_unitario_comercial": float,
                        "valor_total_produto": float,
                        "unidade_comercial": "string",
                        "ncm": "string",
                        "cfop": "string"
                    }
                ]
            }
            
            ATENÇÃO: Se não conseguir ver valores comerciais claramente, use null mas mantenha o item.
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": items_prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                        ]
                    }
                ],
                response_format={"type": "json_object"},
                max_tokens=3000
            )
            
            content = response.choices[0].message.content
            if content:
                result = json.loads(content)
                items = result.get('items', [])
                self.logger.info(f"Successfully extracted {len(items)} items from page {page_num}")
                
                # Log each item for debugging
                for i, item in enumerate(items):
                    qtd = item.get('quantidade_comercial')
                    unit_price = item.get('valor_unitario_comercial')
                    total = item.get('valor_total_produto')
                    desc = str(item.get('descricao_produto') or item.get('descricao_servico') or 'N/A')[:50]
                    self.logger.info(f"Item {i+1}: {desc} - Qtd: {qtd}, Unit: {unit_price}, Total: {total}")
                
                return result
            return {}
            
        except Exception as e:
            self.logger.error(f"Error extracting items from page {page_num}: {str(e)}")
            return {}
    
    def _extract_additional_info(self, image_base64: str, page_num: int) -> Dict[str, Any]:
        """Extract authorization and additional information."""
        try:
            additional_prompt = """
            FOCO EXCLUSIVO: Extraia informações de AUTORIZAÇÃO e DADOS ADICIONAIS.
            
            Procure por:
            - Protocolo de autorização
            - Status de autorização  
            - Ambiente (Produção/Homologação)
            - Informações adicionais (texto no rodapé)
            
            Retorne JSON:
            {
                "autorizacao": {
                    "protocolo_autorizacao": "string",
                    "status_autorizacao": "string", 
                    "ambiente": "string"
                },
                "informacoes_adicionais": "string - texto completo das informações adicionais"
            }
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": additional_prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                        ]
                    }
                ],
                response_format={"type": "json_object"},
                max_tokens=1000
            )
            
            content = response.choices[0].message.content
            if content:
                result = json.loads(content)
                self.logger.info(f"Successfully extracted additional info from page {page_num}")
                return result
            return {}
            
        except Exception as e:
            self.logger.error(f"Error extracting additional info from page {page_num}: {str(e)}")
            return {}
    
    def _combine_extraction_stages(self, header_data: Dict, fiscal_data: Dict, items_data: Dict, additional_data: Dict, page_num: int) -> Dict[str, Any]:
        """Combine data from all extraction stages."""
        try:
            combined = {}
            
            # Merge all sections
            if header_data:
                combined.update(header_data)
            
            if fiscal_data:
                combined.update(fiscal_data)
                
            if items_data:
                combined.update(items_data)
                
            if additional_data:
                combined.update(additional_data)
            
            combined['page_number'] = page_num
            
            self.logger.info(f"Successfully combined all data for page {page_num}")
            return combined
            
        except Exception as e:
            self.logger.error(f"Error combining extraction stages for page {page_num}: {str(e)}")
            return {}

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