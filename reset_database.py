#!/usr/bin/env python3
"""Script para zerar o banco de dados e recriar as tabelas"""
import os
import sys
from app import app, db
import logging

logging.basicConfig(level=logging.INFO)

def reset_database():
    """Drop all tables and recreate them."""
    with app.app_context():
        try:
            logging.info("🗑️  Iniciando reset do banco de dados...")
            
            # Import models to ensure all tables are registered
            import models  # noqa: F401
            
            # Drop all tables
            logging.info("⚠️  Removendo todas as tabelas...")
            db.drop_all()
            logging.info("✅ Todas as tabelas removidas")
            
            # Create all tables
            logging.info("📦 Criando todas as tabelas novamente...")
            db.create_all()
            logging.info("✅ Todas as tabelas criadas")
            
            # Create default admin (will be called automatically by init_database)
            from app import create_default_admin
            create_default_admin()
            
            logging.info("\n" + "="*60)
            logging.info("✅ BANCO DE DADOS RESETADO COM SUCESSO!")
            logging.info("="*60)
            logging.info("\n📧 Admin criado:")
            logging.info("   Email: admin@admin.com")
            logging.info("   Senha: admin123")
            logging.info("\n⚠️  IMPORTANTE: Altere a senha após o primeiro login!")
            logging.info("="*60 + "\n")
            
        except Exception as e:
            logging.error(f"❌ Erro ao resetar banco de dados: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == '__main__':
    print("\n" + "="*60)
    print("⚠️  ATENÇÃO: Este script vai APAGAR TODOS OS DADOS do banco!")
    print("="*60)
    confirm = input("\nDigite 'CONFIRMAR' para continuar: ")
    
    if confirm == 'CONFIRMAR':
        reset_database()
    else:
        print("\n❌ Operação cancelada.")
        sys.exit(0)
