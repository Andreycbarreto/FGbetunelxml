#!/usr/bin/env python3
"""
Test to verify async processing is working correctly
"""

import os
import sys
import logging
from app import app, db
from models import UploadedFile, NFERecord, User, ProcessingStatus

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_recent_records():
    """Test recent records to see if tipo_operacao is being saved"""
    
    with app.app_context():
        # Get the most recent 5 records
        recent_records = NFERecord.query.order_by(NFERecord.created_at.desc()).limit(5).all()
        
        print(f"Found {len(recent_records)} recent records:")
        
        for record in recent_records:
            print(f"\nRecord ID: {record.id}")
            print(f"  File: {record.uploaded_file.original_filename if record.uploaded_file else 'N/A'}")
            print(f"  Created: {record.created_at}")
            print(f"  Number: {record.numero_nf}")
            print(f"  Tipo Operação: '{record.tipo_operacao}'")
            print(f"  Emitente: {record.emitente_nome}")
            print(f"  AI Confidence: {record.ai_confidence_score}")
            print(f"  Processing Notes: {record.ai_processing_notes}")
            
            # Check if tipo_operacao is None, empty, or has value
            if record.tipo_operacao is None:
                print("  ❌ tipo_operacao is None")
            elif record.tipo_operacao == '':
                print("  ❌ tipo_operacao is empty string")
            elif record.tipo_operacao in ['CT-e (Transporte)', 'Serviços e Produtos']:
                print(f"  ✅ tipo_operacao is valid: {record.tipo_operacao}")
            else:
                print(f"  ⚠️ tipo_operacao has unexpected value: '{record.tipo_operacao}'")

def test_uploaded_files():
    """Test uploaded files to see processing status"""
    
    with app.app_context():
        recent_files = UploadedFile.query.order_by(UploadedFile.created_at.desc()).limit(5).all()
        
        print(f"\nFound {len(recent_files)} recent uploaded files:")
        
        for file in recent_files:
            print(f"\nFile ID: {file.id}")
            print(f"  Name: {file.original_filename}")
            print(f"  Status: {file.status}")
            print(f"  Processing started: {file.processing_started_at}")
            print(f"  Processing completed: {file.processing_completed_at}")
            print(f"  Error: {file.error_message}")
            
            # Check if there's an NFE record for this file
            nfe_record = NFERecord.query.filter_by(uploaded_file_id=file.id).first()
            if nfe_record:
                print(f"  NFE Record: {nfe_record.id}")
                print(f"  Tipo Operação: '{nfe_record.tipo_operacao}'")
            else:
                print(f"  ❌ No NFE record found")

if __name__ == "__main__":
    print("=== TESTING RECENT RECORDS ===")
    test_recent_records()
    
    print("\n=== TESTING UPLOADED FILES ===")
    test_uploaded_files()