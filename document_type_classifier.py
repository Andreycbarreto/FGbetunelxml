"""
Document Type Classifier
Specialized agent for classifying NFe documents into operation types:
- Serviços e Produtos
- CT-e (Transporte)
"""

import os
import logging
from typing import Dict, Any, Optional
from openai import OpenAI

logger = logging.getLogger(__name__)

class DocumentTypeClassifier:
    """Classifica documentos NFe por tipo de operação"""
    
    def __init__(self):
        self.client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
            timeout=30.0
        )
        self.logger = logging.getLogger(__name__)
    
    def classify_operation_type(self, base64_image: str, extracted_data: Dict[str, Any] = None) -> str:
        """
        Classifica o tipo de operação do documento
        
        Args:
            base64_image: Imagem base64 do documento
            extracted_data: Dados já extraídos do documento (opcional)
            
        Returns:
            "Serviços e Produtos" ou "CT-e (Transporte)"
        """
        try:
            # Primeiro tenta classificar pelos dados extraídos
            if extracted_data:
                text_based_classification = self._classify_by_extracted_data(extracted_data)
                if text_based_classification:
                    return text_based_classification
            
            # Se não conseguir pelos dados, usa análise visual
            return self._classify_by_visual_analysis(base64_image)
            
        except Exception as e:
            self.logger.error(f"Erro na classificação do tipo de operação: {e}")
            return "Serviços e Produtos"  # Fallback padrão
    
    def _classify_by_extracted_data(self, data: Dict[str, Any]) -> Optional[str]:
        """Classifica baseado nos dados já extraídos"""
        
        # Indicadores de CT-e (Transporte)
        transport_indicators = [
            # Códigos de serviço específicos de transporte
            "transporte", "frete", "logística", "carga", "entrega",
            "rodoviário", "ferroviário", "aquaviário", "aéreo",
            "movimentação", "armazenagem", "terminal", "porto",
            "aeroporto", "rodoviária", "ferrovia",
            # Códigos CFOP típicos de transporte
            "5351", "5352", "5353", "5354", "5355", "5356",
            "6351", "6352", "6353", "6354", "6355", "6356",
            # Códigos de serviço LC 116/2003 relacionados a transporte
            "20.01", "20.02", "20.03", "16.01", "16.02"
        ]
        
        # Verificar descrições de serviços
        items = data.get('items', [])
        for item in items:
            if isinstance(item, dict):
                desc_servico = str(item.get('descricao_servico', '')).lower()
                desc_produto = str(item.get('descricao_produto', '')).lower()
                codigo_servico = str(item.get('codigo_servico', ''))
                cfop = str(item.get('cfop', ''))
                
                # Verificar se contém indicadores de transporte
                full_description = f"{desc_servico} {desc_produto}".lower()
                
                for indicator in transport_indicators:
                    if indicator in full_description or indicator in codigo_servico or indicator in cfop:
                        self.logger.info(f"Classificado como CT-e por indicador: {indicator}")
                        return "CT-e (Transporte)"
        
        # Verificar natureza da operação
        natureza = str(data.get('natureza_operacao', '')).lower()
        for indicator in transport_indicators:
            if indicator in natureza:
                self.logger.info(f"Classificado como CT-e por natureza da operação: {indicator}")
                return "CT-e (Transporte)"
        
        # Verificar informações adicionais
        info_adicional = str(data.get('informacoes_adicionais', '')).lower()
        for indicator in transport_indicators:
            if indicator in info_adicional:
                self.logger.info(f"Classificado como CT-e por informações adicionais: {indicator}")
                return "CT-e (Transporte)"
        
        # Se não encontrou indicadores de transporte, é serviços e produtos
        return None
    
    def _classify_by_visual_analysis(self, base64_image: str) -> str:
        """Classifica usando análise visual com GPT-4 Vision"""
        
        classification_prompt = """
        Você é um especialista em classificação de documentos fiscais brasileiros.
        
        Analise este documento e classifique-o em UMA das seguintes categorias:
        
        1. "Serviços e Produtos" - Para documentos que representam:
           - Venda de produtos físicos
           - Prestação de serviços em geral
           - Serviços profissionais
           - Serviços técnicos
           - Serviços de consultoria
           - Serviços de manutenção
           - Qualquer operação que não seja transporte
        
        2. "CT-e (Transporte)" - Para documentos que representam:
           - Transporte de cargas
           - Frete rodoviário, ferroviário, aquaviário ou aéreo
           - Serviços logísticos
           - Movimentação de mercadorias
           - Armazenagem em terminais
           - Serviços portuários
           - Operações de carga e descarga
           - Qualquer atividade relacionada ao transporte de bens
        
        CRITÉRIOS DE CLASSIFICAÇÃO:
        
        Para CT-e (Transporte), procure por:
        - Palavras-chave: "transporte", "frete", "logística", "carga", "entrega"
        - Códigos de serviço: 16.01, 16.02, 20.01, 20.02, 20.03
        - Descrições: "movimentação", "armazenagem", "terminal", "porto"
        - CFOPs: 5351-5356, 6351-6356 (típicos de transporte)
        - Natureza da operação relacionada a transporte
        
        Para Serviços e Produtos, procure por:
        - Descrições de produtos físicos
        - Serviços profissionais ou técnicos
        - Consultoria, manutenção, reparos
        - Qualquer atividade que NÃO seja transporte
        
        IMPORTANTE: Responda APENAS com uma das duas opções:
        - "Serviços e Produtos"
        - "CT-e (Transporte)"
        
        Não forneça explicações, apenas a classificação.
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": classification_prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                        ]
                    }
                ],
                max_tokens=50,
                temperature=0.1
            )
            
            classification = response.choices[0].message.content.strip()
            
            # Validar resposta
            if "CT-e" in classification or "Transporte" in classification:
                self.logger.info("Classificado como CT-e (Transporte) por análise visual")
                return "CT-e (Transporte)"
            else:
                self.logger.info("Classificado como Serviços e Produtos por análise visual")
                return "Serviços e Produtos"
                
        except Exception as e:
            self.logger.error(f"Erro na análise visual: {e}")
            return "Serviços e Produtos"  # Fallback padrão

def classify_document_operation_type(base64_image: str, extracted_data: Dict[str, Any] = None) -> str:
    """
    Função utilitária para classificar tipo de operação
    
    Args:
        base64_image: Imagem base64 do documento
        extracted_data: Dados já extraídos (opcional)
        
    Returns:
        "Serviços e Produtos" ou "CT-e (Transporte)"
    """
    classifier = DocumentTypeClassifier()
    return classifier.classify_operation_type(base64_image, extracted_data)