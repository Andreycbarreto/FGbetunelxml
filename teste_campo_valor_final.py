#!/usr/bin/env python3
"""
Teste específico para descobrir o campo exato do valor no Fluig
"""

import logging
import requests
from app import app, db
from models import NFERecord, UserSettings
from fluig_integration import FluigIntegration

def teste_campo_valor_especifico():
    """Teste para descobrir o campo EXATO do valor"""
    
    with app.app_context():
        # Pegar uma NFE qualquer
        nfe_record = NFERecord.query.filter(
            NFERecord.numero_nf.isnot(None)
        ).first()
        
        if not nfe_record:
            logging.error("Nenhuma NFE encontrada!")
            return
        
        user_settings = UserSettings.query.filter_by(user_id=nfe_record.user_id).first()
        if not user_settings:
            logging.error("Configurações não encontradas!")
            return
        
        fluig = FluigIntegration(user_settings)
        
        logging.info(f"🎯 TESTE FINAL - DESCOBRIR CAMPO VALOR")
        logging.info(f"NFE: {nfe_record.numero_nf}")
        
        # Campos básicos que sabemos que funcionam
        form_fields = {
            "nome": "Roberto Galdino",
            "matricula": "e7f2q0ulk2s1qwxw1496403470877", 
            "email": "roberto.galdino@betunel.com.br",
            "Hdt_entrada_nf": "11/08/2025",
            "dt_entrada_nf": "11/08/2025",
            "nm_empresa": "BETUNEL INDUSTRIA E COMERCIOS S/A",
            "cod_empresa": "1",
            "cnpj": "60546801000189", 
            "nm_filial": "Montenegro",
            "cod_filial": "19",
            "cnpj_filial": "60546801002980",
            "unid_negoc": "SUPPLY E CUSTOS",
            "cod_un": "0.10.02.01.001",
            "centro_custo": "1.0.3299 - SUPRIMENTOS", 
            "cod_cc": "1.0.3299",
            "tp_doc": "Nota fiscal de serviço eletrônica",
            "numero_NF": nfe_record.numero_nf,
            "serie": "E1", 
            "valor_NF": "2991,75",
            "dt_emissao_NF": "23/01/2023",
            "Hdt_emissao_NF": "23/01/2023",
            "dt_vencimento_NF": "24/01/2023",
            "fornecedor": f"{nfe_record.emitente_nome} - {nfe_record.emitente_cnpj} - 20.0581",
            "cod_fornecedor": "20.0581",
            "fm_pagamento": "DESPACHANTE",
            "chk_boleto": "NAO", 
            "justificativa": "NFe recebida nesta data.",
            "destinacao": "PO475_20225 Exigível",
            "projeto___1": "SEMPROJETO",
            "subprojeto___1": "SEMSUBPROJETO",
            "identificador": f"TESTE FINAL VALOR - NFE {nfe_record.numero_nf}",
            
            # DADOS DA TABELA - as colunas que funcionam
            "column1_1___1": "3301",  # Código
            "column1_2___1": "Serviços de desembaraço aduaneiro",  # Nome
            
            # TESTE INTENSIVO PARA O CAMPO VALOR
            # Baseado na imagem: Código | Nome | Projeto | Sub projeto | Valor
            
            # Tentativa 1: Campo padrão (o que não funciona)
            "column1_5___1": "3187,80",
            
            # Tentativa 2: Campo valor com diferentes sufixos
            "column1_valor___1": "3187,80",
            "valor_column1___1": "3187,80", 
            "vlr_column1___1": "3187,80",
            
            # Tentativa 3: Campo valor standalone
            "valorItem1": "3187,80",
            "valor_item_1": "3187,80",
            "vlr_item_1": "3187,80",
            "item_valor_1": "3187,80",
            
            # Tentativa 4: Formato diferente da numeração
            "column1_5___01": "3187,80",
            "column1_05___1": "3187,80",
            "column1_5___001": "3187,80",
            
            # Tentativa 5: Prefixo diferente
            "col1_5___1": "3187,80", 
            "c1_5___1": "3187,80",
            "field_5___1": "3187,80",
            "tabela_5___1": "3187,80",
        }
        
        logging.info(f"🧪 TESTANDO {len([k for k in form_fields.keys() if '3187,80' in str(form_fields[k])])} VARIAÇÕES DIFERENTES DO CAMPO VALOR")
        
        try:
            payload = {
                "targetState": 59,
                "targetAssignee": "",
                "subProcessTargetState": 0,
                "comment": "TESTE INTENSIVO CAMPO VALOR",
                "formFields": form_fields
            }
            
            response = requests.post(
                f'{fluig.fluig_url}/process-management/api/v2/processes/Processo%20de%20Lançamento%20de%20Nota%20Fiscal/start',
                json=payload,
                auth=fluig.auth,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                process_id = result.get("processInstanceId")
                logging.info(f"✅ PROCESSO CRIADO: {process_id}")
                logging.info(f"")
                logging.info(f"🔍 AGORA VAMOS DESCOBRIR QUAL CAMPO FUNCIONOU!")
                logging.info(f"   Acesse: {user_settings.fluig_url}")
                logging.info(f"   Processo: {process_id}")
                logging.info(f"   Verifique qual das tentativas preencheu o campo Valor")
                return process_id
            else:
                logging.error(f"❌ Erro: {response.status_code} - {response.text}")
                
        except Exception as e:
            logging.error(f"❌ Erro: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    teste_campo_valor_especifico()