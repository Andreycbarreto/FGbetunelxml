#!/usr/bin/env python3
"""
Teste específico para descobrir qual campo funciona para o VALOR na tabela do Fluig
"""

import logging
from app import app, db
from models import NFERecord, UserSettings
from fluig_integration import FluigIntegration
import json

def test_valor_field_discovery():
    """Testa diferentes campos para o valor da tabela"""
    
    with app.app_context():
        # Buscar NFE para teste
        nfe_record = NFERecord.query.filter(
            NFERecord.numero_nf == '11282'
        ).first()
        
        if not nfe_record:
            logging.error("NFE não encontrada!")
            return
        
        user_settings = UserSettings.query.filter_by(user_id=nfe_record.user_id).first()
        if not user_settings:
            logging.error("Configurações não encontradas!")
            return
        
        logging.info(f"🔍 DESCOBERTA DO CAMPO VALOR")
        logging.info(f"Testando NFE: {nfe_record.numero_nf}")
        
        # Valor para teste
        valor_teste = "3187,80"  # Formato brasileiro
        
        # Campos mínimos + múltiplas opções para o valor
        form_fields = {
            # Campos básicos obrigatórios
            "nome": "TESTE CAMPO VALOR",
            "email": "teste@teste.com",
            "numero_NF": nfe_record.numero_nf,
            
            # Dados do item (o que já funciona)
            "column1_1___1": "01.071.010",  # Código (funciona)
            "column1_2___1": "TESTE DESCOBERTA VALOR",  # Nome (funciona)
            "column1_3___1": "SEMPROJETO",  # Projeto (funciona)
            "column1_4___1": "SEMSUBPROJETO",  # Sub projeto (funciona)
            
            # TESTES PARA O VALOR (posição 5):
            "column1_5___1": valor_teste,  # Posição original
            "column1_6___1": valor_teste,  # Próxima posição
            "column1_7___1": valor_teste,  # Outra posição
            
            # TESTES COM NOMES ESPECÍFICOS:
            "valor___1": valor_teste,
            "vlr___1": valor_teste,
            "valorItem___1": valor_teste,
            "vlrItem___1": valor_teste,
            "preco___1": valor_teste,
            "amount___1": valor_teste,
            "value___1": valor_teste,
            
            # FORMATO DE TABELA ESPECÍFICO DO FLUIG:
            "table_valor___1": valor_teste,
            "tabela_valor___1": valor_teste,
            "item_valor___1": valor_teste,
            "linha_valor___1": valor_teste,
            
            # TESTE COM PREFIXOS DIFERENTES:
            "col_5___1": valor_teste,
            "col_6___1": valor_teste,
            "field_5___1": valor_teste,
            "field_6___1": valor_teste,
        }
        
        logging.info(f"🧪 CAMPOS TESTADOS PARA VALOR:")
        for campo, valor in form_fields.items():
            if 'valor' in campo.lower() or 'vlr' in campo.lower() or 'column1_' in campo:
                logging.info(f"  {campo}: {valor}")
        
        # Payload de teste
        payload = {
            "attachments": [],
            "comment": "TESTE ESPECÍFICO PARA DESCOBRIR CAMPO VALOR",
            "formFields": form_fields
        }
        
        logging.info(f"🚀 CRIANDO PROCESSO DE TESTE...")
        logging.info(f"Total de campos de valor testados: {len([k for k in form_fields.keys() if 'valor' in k.lower() or 'vlr' in k.lower() or 'column1_' in k])}")
        
        # Fazer integração real para teste
        fluig = FluigIntegration(user_settings)
        
        try:
            import requests
            
            start_process_payload = {
                "targetState": 59,
                "targetAssignee": "",
                "subProcessTargetState": 0,
                "comment": "TESTE CAMPO VALOR",
                "formFields": form_fields
            }
            
            response = requests.post(
                f'{fluig.fluig_url}/process-management/api/v2/processes/Processo%20de%20Lançamento%20de%20Nota%20Fiscal/start',
                json=start_process_payload,
                auth=fluig.auth,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                process_id = result.get("processInstanceId")
                logging.info(f"✅ PROCESSO CRIADO: {process_id}")
                logging.info(f"🔍 VERIFIQUE NO FLUIG QUAL CAMPO FUNCIONOU!")
                logging.info(f"📋 URL: {user_settings.fluig_url}")
                return process_id
            else:
                logging.error(f"❌ Erro na criação: {response.status_code}")
                logging.error(f"Response: {response.text}")
                
        except Exception as e:
            logging.error(f"❌ Erro: {str(e)}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_valor_field_discovery()