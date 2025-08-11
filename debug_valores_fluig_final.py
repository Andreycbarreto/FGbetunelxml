#!/usr/bin/env python3
"""
Teste final para verificar se o campo valor está funcionando na integração
"""

import logging
from app import app, db
from models import NFERecord, UserSettings
from fluig_integration import FluigIntegration

def test_final_valor_integration():
    """Teste usando o método real da integração"""
    
    with app.app_context():
        # Buscar NFE 11282
        nfe_record = NFERecord.query.filter(
            NFERecord.numero_nf == '11282'
        ).first()
        
        if not nfe_record:
            logging.error("NFE 11282 não encontrada!")
            return
        
        user_settings = UserSettings.query.filter_by(user_id=nfe_record.user_id).first()
        if not user_settings:
            logging.error("Configurações do usuário não encontradas!")
            return
        
        logging.info(f"🎯 TESTE FINAL - VALOR ITEM NFE {nfe_record.numero_nf}")
        logging.info(f"💰 Valor total NFE: R$ {nfe_record.valor_total_nf or 0:.2f}")
        
        # Criar integração
        fluig = FluigIntegration(user_settings)
        
        try:
            # Usar o método real que já funciona para tudo exceto valor
            process_id = fluig.start_service_process_capture_solicitation_number(nfe_record, None)
            
            if process_id:
                logging.info(f"✅ PROCESSO CRIADO COM SUCESSO: {process_id}")
                logging.info(f"")
                logging.info(f"🔍 AGORA VERIFIQUE NO FLUIG:")
                logging.info(f"   1. Acesse: {user_settings.fluig_url}")
                logging.info(f"   2. Vá para o processo: {process_id}")
                logging.info(f"   3. Veja se a coluna 'Valor' dos itens está preenchida")
                logging.info(f"")
                logging.info(f"📋 Com as mudanças implementadas, testamos:")
                logging.info(f"   - column1_3___1_valor: formatado BR")
                logging.info(f"   - column1_4___1_valor: formatado BR") 
                logging.info(f"   - column1_5___1_valor: formatado BR")
                logging.info(f"   - column1_6___1: formatado BR")
                logging.info(f"   - valorItem1: formatado BR")
                logging.info(f"   - valor1: formatado BR")
                
                return process_id
            else:
                logging.error("❌ Falha na criação do processo")
                
        except Exception as e:
            logging.error(f"❌ Erro na integração: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_final_valor_integration()