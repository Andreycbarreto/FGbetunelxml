"""
Filial Management Routes
Routes for creating and managing filiais (branches) linked to companies
"""

import io
import pandas as pd
from flask import render_template, request, redirect, url_for, flash, jsonify, make_response
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import app, db
from models import Filial, Empresa


@app.route('/filiais')
@login_required
def filiais_listar():
    """Listar todas as filiais do usuário atual"""
    filiais = Filial.query.filter_by(user_id=current_user.id).order_by(Filial.coligada, Filial.filial).all()
    return render_template('filiais/list.html', filiais=filiais)


@app.route('/filiais/nova')
@login_required
def filial_nova():
    """Formulário para criar nova filial"""
    # Buscar empresas do usuário para seleção
    empresas = Empresa.query.filter_by(user_id=current_user.id).order_by(Empresa.numero).all()
    return render_template('filiais/form.html', filial=None, empresas=empresas)


@app.route('/filiais/nova', methods=['POST'])
@login_required
def filial_criar():
    """Criar nova filial"""
    try:
        # Buscar a empresa pelo número
        empresa_numero = int(request.form.get('coligada'))
        empresa = Empresa.query.filter_by(numero=empresa_numero, user_id=current_user.id).first()
        
        if not empresa:
            flash('Empresa não encontrada!', 'error')
            return redirect(url_for('filial_nova'))
        
        # Verificar se já existe filial com mesmo coligada+filial
        existing_filial = Filial.query.filter_by(
            coligada=empresa_numero,
            filial=request.form.get('filial'),
            user_id=current_user.id
        ).first()
        
        if existing_filial:
            flash('Já existe uma filial com este código para esta empresa!', 'error')
            return redirect(url_for('filial_nova'))
        
        # Criar nova filial
        filial = Filial(
            coligada=empresa_numero,
            nome_coligada=request.form.get('nome_coligada'),
            cnpj_coligada=request.form.get('cnpj_coligada').replace('.', '').replace('/', '').replace('-', ''),
            filial=request.form.get('filial'),
            nome_filial=request.form.get('nome_filial'),
            cnpj_filial=request.form.get('cnpj_filial').replace('.', '').replace('/', '').replace('-', ''),
            user_id=current_user.id,
            empresa_id=empresa.id
        )
        
        db.session.add(filial)
        db.session.commit()
        
        flash('Filial cadastrada com sucesso!', 'success')
        return redirect(url_for('filiais_listar'))
        
    except Exception as e:
        flash(f'Erro ao cadastrar filial: {str(e)}', 'error')
        return redirect(url_for('filial_nova'))


@app.route('/filiais/<int:filial_id>/editar')
@login_required
def filial_editar(filial_id):
    """Formulário para editar filial"""
    filial = Filial.query.filter_by(id=filial_id, user_id=current_user.id).first_or_404()
    empresas = Empresa.query.filter_by(user_id=current_user.id).order_by(Empresa.numero).all()
    return render_template('filiais/form.html', filial=filial, empresas=empresas)


@app.route('/filiais/<int:filial_id>/editar', methods=['POST'])
@login_required
def filial_atualizar(filial_id):
    """Atualizar filial"""
    try:
        filial = Filial.query.filter_by(id=filial_id, user_id=current_user.id).first_or_404()
        
        # Buscar a empresa pelo número
        empresa_numero = int(request.form.get('coligada'))
        empresa = Empresa.query.filter_by(numero=empresa_numero, user_id=current_user.id).first()
        
        if not empresa:
            flash('Empresa não encontrada!', 'error')
            return redirect(url_for('filial_editar', filial_id=filial_id))
        
        # Verificar se já existe filial com mesmo coligada+filial (exceto a atual)
        existing_filial = Filial.query.filter_by(
            coligada=empresa_numero,
            filial=request.form.get('filial'),
            user_id=current_user.id
        ).filter(Filial.id != filial_id).first()
        
        if existing_filial:
            flash('Já existe uma filial com este código para esta empresa!', 'error')
            return redirect(url_for('filial_editar', filial_id=filial_id))
        
        # Atualizar filial
        filial.coligada = empresa_numero
        filial.nome_coligada = request.form.get('nome_coligada')
        filial.cnpj_coligada = request.form.get('cnpj_coligada').replace('.', '').replace('/', '').replace('-', '')
        filial.filial = request.form.get('filial')
        filial.nome_filial = request.form.get('nome_filial')
        filial.cnpj_filial = request.form.get('cnpj_filial').replace('.', '').replace('/', '').replace('-', '')
        filial.empresa_id = empresa.id
        
        db.session.commit()
        
        flash('Filial atualizada com sucesso!', 'success')
        return redirect(url_for('filiais_listar'))
        
    except Exception as e:
        flash(f'Erro ao atualizar filial: {str(e)}', 'error')
        return redirect(url_for('filial_editar', filial_id=filial_id))


@app.route('/filiais/<int:filial_id>/excluir', methods=['POST'])
@login_required
def filial_excluir(filial_id):
    """Excluir filial"""
    try:
        filial = Filial.query.filter_by(id=filial_id, user_id=current_user.id).first_or_404()
        
        nome_filial = filial.nome_filial
        db.session.delete(filial)
        db.session.commit()
        
        flash(f'Filial "{nome_filial}" excluída com sucesso!', 'success')
        
    except Exception as e:
        flash(f'Erro ao excluir filial: {str(e)}', 'error')
    
    return redirect(url_for('filiais_listar'))


@app.route('/filiais/importar')
@login_required
def filial_importar():
    """Página para importar filiais via XLSX"""
    return render_template('filiais/import.html')


@app.route('/filiais/importar', methods=['POST'])
@login_required
def filial_processar_importacao():
    """Processar importação de filiais via XLSX"""
    try:
        if 'file' not in request.files:
            flash('Nenhum arquivo selecionado!', 'error')
            return redirect(url_for('filial_importar'))
        
        file = request.files['file']
        if file.filename == '':
            flash('Nenhum arquivo selecionado!', 'error')
            return redirect(url_for('filial_importar'))
        
        if not file.filename.lower().endswith('.xlsx'):
            flash('Apenas arquivos XLSX são permitidos!', 'error')
            return redirect(url_for('filial_importar'))
        
        # Ler arquivo Excel
        df = pd.read_excel(file)
        
        # Validar colunas obrigatórias
        required_columns = ['COLIGADA', 'NOME_COLIGADA', 'CNPJ_COLIGADA', 'FILIAL', 'NOME_FILIAL', 'CNPJ_FILIAL']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            flash(f'Colunas obrigatórias não encontradas: {", ".join(missing_columns)}', 'error')
            return redirect(url_for('filial_importar'))
        
        # Processar cada linha
        success_count = 0
        error_count = 0
        errors = []
        
        for index, row in df.iterrows():
            try:
                # Validar dados da linha
                if pd.isna(row['COLIGADA']) or pd.isna(row['FILIAL']):
                    errors.append(f'Linha {index + 2}: COLIGADA e FILIAL são obrigatórios')
                    error_count += 1
                    continue
                
                # Buscar empresa pelo número
                empresa_numero = int(row['COLIGADA'])
                empresa = Empresa.query.filter_by(numero=empresa_numero, user_id=current_user.id).first()
                
                if not empresa:
                    errors.append(f'Linha {index + 2}: Empresa {empresa_numero} não encontrada')
                    error_count += 1
                    continue
                
                # Verificar se já existe filial
                existing_filial = Filial.query.filter_by(
                    coligada=empresa_numero,
                    filial=str(row['FILIAL']),
                    user_id=current_user.id
                ).first()
                
                if existing_filial:
                    errors.append(f'Linha {index + 2}: Filial {empresa_numero}-{row["FILIAL"]} já existe')
                    error_count += 1
                    continue
                
                # Criar nova filial
                filial = Filial(
                    coligada=empresa_numero,
                    nome_coligada=str(row['NOME_COLIGADA']) if not pd.isna(row['NOME_COLIGADA']) else '',
                    cnpj_coligada=str(row['CNPJ_COLIGADA']).replace('.', '').replace('/', '').replace('-', '') if not pd.isna(row['CNPJ_COLIGADA']) else '',
                    filial=str(row['FILIAL']),
                    nome_filial=str(row['NOME_FILIAL']) if not pd.isna(row['NOME_FILIAL']) else '',
                    cnpj_filial=str(row['CNPJ_FILIAL']).replace('.', '').replace('/', '').replace('-', '') if not pd.isna(row['CNPJ_FILIAL']) else '',
                    user_id=current_user.id,
                    empresa_id=empresa.id
                )
                
                db.session.add(filial)
                success_count += 1
                
            except Exception as e:
                errors.append(f'Linha {index + 2}: {str(e)}')
                error_count += 1
        
        # Salvar mudanças
        if success_count > 0:
            db.session.commit()
            flash(f'{success_count} filiais importadas com sucesso!', 'success')
        
        if error_count > 0:
            flash(f'{error_count} erros encontrados durante a importação.', 'warning')
            # Mostrar apenas os primeiros 10 erros
            for error in errors[:10]:
                flash(error, 'error')
            
            if len(errors) > 10:
                flash(f'E mais {len(errors) - 10} erros...', 'error')
        
        return redirect(url_for('filiais_listar'))
        
    except Exception as e:
        flash(f'Erro ao processar arquivo: {str(e)}', 'error')
        return redirect(url_for('filial_importar'))


@app.route('/filiais/modelo-xlsx')
@login_required
def filial_modelo_xlsx():
    """Gerar modelo XLSX para importação de filiais"""
    try:
        # Buscar empresas do usuário
        empresas = Empresa.query.filter_by(user_id=current_user.id).order_by(Empresa.numero).all()
        
        # Criar dados de exemplo
        sample_data = []
        for empresa in empresas[:3]:  # Máximo 3 empresas como exemplo
            sample_data.append({
                'COLIGADA': empresa.numero,
                'NOME_COLIGADA': empresa.nome_fantasia,
                'CNPJ_COLIGADA': empresa.cnpj_formatado,
                'FILIAL': '001',
                'NOME_FILIAL': f'Filial {empresa.nome_fantasia} - Matriz',
                'CNPJ_FILIAL': empresa.cnpj_formatado
            })
        
        # Se não há empresas, criar exemplo genérico
        if not sample_data:
            sample_data = [{
                'COLIGADA': 1,
                'NOME_COLIGADA': 'Empresa Exemplo Ltda',
                'CNPJ_COLIGADA': '12.345.678/0001-90',
                'FILIAL': '001',
                'NOME_FILIAL': 'Filial Matriz',
                'CNPJ_FILIAL': '12.345.678/0001-90'
            }]
        
        # Criar DataFrame
        df = pd.DataFrame(sample_data)
        
        # Criar arquivo Excel em memória
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Filiais')
        
        output.seek(0)
        
        # Retornar arquivo
        response = make_response(output.read())
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        response.headers['Content-Disposition'] = 'attachment; filename=modelo_filiais.xlsx'
        
        return response
        
    except Exception as e:
        flash(f'Erro ao gerar modelo: {str(e)}', 'error')
        return redirect(url_for('filial_importar'))


@app.route('/api/empresas/<int:empresa_numero>/info')
@login_required
def api_empresa_info(empresa_numero):
    """API para buscar informações da empresa pelo número"""
    empresa = Empresa.query.filter_by(numero=empresa_numero, user_id=current_user.id).first()
    
    if not empresa:
        return jsonify({'error': 'Empresa não encontrada'}), 404
    
    return jsonify({
        'numero': empresa.numero,
        'nome_fantasia': empresa.nome_fantasia,
        'cnpj': empresa.cnpj_formatado,
        'razao_social': empresa.razao_social
    })