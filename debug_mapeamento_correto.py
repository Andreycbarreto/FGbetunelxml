#!/usr/bin/env python3
"""
Teste com mapeamento correto baseado na análise da imagem
"""

import logging
from app import app, db
from models import NFERecord, UserSettings
from fluig_integration import FluigIntegration

def teste_mapeamento_correto():
    """Teste com mapeamento visual correto"""
    
    with app.app_context():
        # Buscar NFE
        nfe_record = NFERecord.query.filter(
            NFERecord.numero_nf == '11282'
        ).first()
        
        if not nfe_record:
            logging.error("NFE não encontrada!")
            return
        
        user_settings = UserSettings.query.filter_by(user_id=nfe_record.user_id).first()
        
        logging.info(f"🎯 TESTE MAPEAMENTO CORRETO")
        logging.info(f"")
        logging.info(f"❌ ERRO IDENTIFICADO:")
        logging.info(f"   Estávamos enviando: Código | Nome | Quantidade | ValorUnitário | ValorTotal")
        logging.info(f"   Mas a tabela espera: Código | Nome | Projeto | Sub projeto | Valor")
        logging.info(f"")
        logging.info(f"✅ CORREÇÃO:")
        logging.info(f"   column1_1___1: Código do item")
        logging.info(f"   column1_2___1: Nome do item") 
        logging.info(f"   column1_3___1: SEMPROJETO (texto do projeto)")
        logging.info(f"   column1_4___1: SEMSUBPROJETO (texto do subprojeto)")
        logging.info(f"   column1_5___1: 3187,80 (VALOR MONETÁRIO)")
        
        # Teste usando a integração real
        fluig = FluigIntegration(user_settings)
        
        try:
            process_id = fluig.start_service_process_capture_solicitation_number(nfe_record, None)
            
            if process_id:
                logging.info(f"")
                logging.info(f"✅ PROCESSO CRIADO: {process_id}")
                logging.info(f"")
                logging.info(f"🔍 AGORA VERIFIQUE NO FLUIG:")
                logging.info(f"   A coluna 'Valor' deve aparecer preenchida com: 3187,80")
                logging.info(f"   As colunas 'Projeto' e 'Sub projeto' devem aparecer como: SEMPROJETO, SEMSUBPROJETO")
                
                return process_id
            else:
                logging.error("Falha na criação do processo")
                
        except Exception as e:
            logging.error(f"Erro: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    teste_mapeamento_correto()