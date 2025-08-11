#!/usr/bin/env python3
"""
Teste com payload COMPLETO focado apenas no campo valor
"""

import logging
from app import app, db
from models import NFERecord, UserSettings, User
from fluig_integration import FluigIntegration
from datetime import datetime

def test_valor_completo():
    """Teste com payload completo do exemplo que funciona + foco no valor"""
    
    with app.app_context():
        # Buscar NFE para teste
        nfe_record = NFERecord.query.filter(
            NFERecord.numero_nf == '11282'
        ).first()
        
        if not nfe_record:
            logging.error("NFE não encontrada!")
            return
        
        user_settings = UserSettings.query.filter_by(user_id=nfe_record.user_id).first()
        user = User.query.get(nfe_record.user_id)
        
        logging.info(f"🧪 TESTE VALOR COM PAYLOAD COMPLETO")
        
        # Usar EXATAMENTE o formato que funciona, mas testando o campo valor
        form_fields = {
            "nome": f"{user.first_name} {user.last_name}" if user and user.first_name else "Admin Sistema",
            "matricula": "0d44ddb10e5a41a3a7a378aa5862694d",
            "email": user.email if user else "admin@sistema.com", 
            "Hdt_entrada_nf": datetime.now().strftime('%d/%m/%Y'),
            "dt_entrada_nf": datetime.now().strftime('%d/%m/%Y'),
            "nm_empresa": "BETUNEL",
            "cod_empresa": "1",
            "cnpj": "60.546.801/0001-89",
            "nm_filial": "Jacarei",
            "cod_filial": "16",
            "cnpj_filial": "60.546.801/0025-56",
            "unid_negoc": "SUPPLY E CUSTOS",
            "cod_un": "0.10.02.01.001",
            "centro_custo": "1.0.3299 - SUPRIMENTOS",
            "cod_cc": "1.0.3299",
            "tp_doc": "Nota fiscal de serviço eletrônica",
            "numero_NF": nfe_record.numero_nf,
            "serie": "E1",
            "valor_NF": "2991,75",
            "dt_emissao_NF": "04/07/2025",
            "Hdt_emissao_NF": "04/07/2025", 
            "dt_vencimento_NF": "20/08/2025",
            "fornecedor": f"{nfe_record.emitente_nome} - {nfe_record.emitente_cnpj} - 20.0581",
            "cod_fornecedor": "20.0581",
            "fm_pagamento": "DESPACHANTE",
            "chk_boleto": "NAO",
            "justificativa": "NFe recebida nesta data.",
            "destinacao": "Exigível",
            "projeto___1": "SEMPROJETO",
            "subprojeto___1": "SEMSUBPROJETO",
            "identificador": f"TESTE VALOR ITEM - NFE {nfe_record.numero_nf}",
            
            # DADOS DOS ITENS - FOCO NO VALOR
            "column1_1___1": "02.007.014",  # Código que funciona
            "column1_2___1": "TESTE - DIMDOC/0425 Numer do processo...DMI0908/0625",  # Descrição que funciona
            
            # TESTES ESPECÍFICOS PARA O VALOR:
            # Tentativa 1: Posição 5 (como temos usado)
            "column1_5___1": "3187,80",
            
            # Tentativa 2: Posição 3 e 4 (pode ser que projeto/subprojeto estejam em lugar errado)
            "column1_3___1": "3187,80",  # Teste valor na posição 3
            "column1_4___1": "3187,80",  # Teste valor na posição 4
            
            # Tentativa 3: Posição 6 e além
            "column1_6___1": "3187,80",
            "column1_7___1": "3187,80",
        }
        
        logging.info(f"🔍 TESTANDO POSIÇÕES PARA VALOR:")
        logging.info(f"  column1_3___1: {form_fields['column1_3___1']}")
        logging.info(f"  column1_4___1: {form_fields['column1_4___1']}")
        logging.info(f"  column1_5___1: {form_fields['column1_5___1']}")
        logging.info(f"  column1_6___1: {form_fields['column1_6___1']}")
        
        # Fazer integração
        fluig = FluigIntegration(user_settings)
        
        try:
            import requests
            
            payload = {
                "targetState": 59,
                "targetAssignee": "",
                "subProcessTargetState": 0,
                "comment": "TESTE DESCOBERTA CAMPO VALOR",
                "formFields": form_fields
            }
            
            response = requests.post(
                f'{fluig.fluig_url}/process-management/api/v2/processes/Processo%20de%20Lançamento%20de%20Nota%20Fiscal/start',
                json=payload,
                auth=fluig.auth,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                process_id = result.get("processInstanceId")
                logging.info(f"✅ PROCESSO CRIADO: {process_id}")
                logging.info(f"🔍 VERIFIQUE NO FLUIG EM QUAL POSIÇÃO APARECEU O VALOR!")
                return process_id
            else:
                logging.error(f"❌ Erro: {response.status_code} - {response.text}")
                
        except Exception as e:
            logging.error(f"❌ Exceção: {str(e)}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_valor_completo()