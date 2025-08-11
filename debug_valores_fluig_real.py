#!/usr/bin/env python3
"""
Script para testar uma integração REAL focada em valores
"""

import logging
from app import app, db
from models import NFERecord, UserSettings, User
from fluig_integration import FluigIntegration
import json

def test_real_integration_valores():
    """Faz uma integração real focada nos valores"""
    
    with app.app_context():
        # Buscar NFE 11282 para teste
        nfe_record = NFERecord.query.filter(
            NFERecord.numero_nf == '11282'
        ).first()
        
        if not nfe_record:
            logging.error("NFE 11282 não encontrada!")
            return
        
        # Buscar configurações do usuário
        user_settings = UserSettings.query.filter_by(user_id=nfe_record.user_id).first()
        if not user_settings:
            logging.error("Configurações do usuário não encontradas!")
            return
        
        logging.info(f"🧪 INICIANDO TESTE REAL DE INTEGRAÇÃO")
        logging.info(f"NFE: {nfe_record.numero_nf}")
        logging.info(f"Valor total da NFE: R$ {nfe_record.valor_total_nf or 0:.2f}")
        
        # Criar integração
        fluig = FluigIntegration(user_settings)
        
        # Chamar o método que já funciona para criar processo
        try:
            process_id = fluig.start_service_process_capture_solicitation_number(nfe_record, None)
            
            if process_id:
                logging.info(f"✅ PROCESSO CRIADO: {process_id}")
                logging.info(f"🔍 VERIFICAR NO FLUIG SE OS VALORES DOS ITENS APARECEM!")
                logging.info(f"📋 URL do Fluig: {user_settings.fluig_url}")
            else:
                logging.error("❌ Falha na criação do processo")
                
        except Exception as e:
            logging.error(f"❌ Erro na integração: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_real_integration_valores()