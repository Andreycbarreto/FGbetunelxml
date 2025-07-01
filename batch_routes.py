"""
Batch Management Routes
Routes for creating and managing batches/contracts for NFe documents
"""

from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import app, db
from models import Batch, BatchStatus, UploadedFile, NFERecord
from datetime import datetime


@app.route('/batches')
@login_required
def batches_list():
    """List all batches for current user"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    batches = Batch.query.filter_by(created_by=current_user.id)\
                   .order_by(Batch.created_at.desc())\
                   .paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('batches/list.html', batches=batches)


@app.route('/batch/new', methods=['GET', 'POST'])
@login_required
def batch_new():
    """Create a new batch"""
    if request.method == 'POST':
        try:
            batch = Batch()
            batch.nome_contrato = request.form.get('nome_contrato')
            batch.nome_item = request.form.get('nome_item')
            batch.unidade_negocio = request.form.get('unidade_negocio')
            batch.centro_custo = request.form.get('centro_custo')
            batch.descricao = request.form.get('descricao')
            batch.created_by = current_user.id
            batch.status = BatchStatus.OPEN
            
            db.session.add(batch)
            db.session.commit()
            
            flash(f'Lote "{batch.nome_contrato}" criado com sucesso!', 'success')
            return redirect(url_for('batch_detail', batch_id=batch.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar lote: {str(e)}', 'error')
    
    return render_template('batches/new.html')


@app.route('/batch/<int:batch_id>')
@login_required
def batch_detail(batch_id):
    """View batch details"""
    batch = Batch.query.get_or_404(batch_id)
    
    # Check if user owns this batch or is admin
    if batch.created_by != current_user.id and not current_user.is_admin:
        flash('Acesso negado ao lote solicitado.', 'error')
        return redirect(url_for('batches_list'))
    
    # Get files in this batch
    files = batch.files.order_by(UploadedFile.created_at.desc()).all()
    
    # Get NFe records in this batch
    nfe_records = batch.nfe_records.order_by(NFERecord.created_at.desc()).all()
    
    return render_template('batches/detail.html', 
                         batch=batch, 
                         files=files, 
                         nfe_records=nfe_records)


@app.route('/batch/<int:batch_id>/edit', methods=['GET', 'POST'])
@login_required
def batch_edit(batch_id):
    """Edit batch information"""
    batch = Batch.query.get_or_404(batch_id)
    
    # Check permissions
    if batch.created_by != current_user.id and not current_user.is_admin:
        flash('Acesso negado ao lote solicitado.', 'error')
        return redirect(url_for('batches_list'))
    
    if not batch.can_be_edited():
        flash('Este lote não pode mais ser editado.', 'warning')
        return redirect(url_for('batch_detail', batch_id=batch_id))
    
    if request.method == 'POST':
        try:
            batch.nome_contrato = request.form.get('nome_contrato')
            batch.nome_item = request.form.get('nome_item')
            batch.unidade_negocio = request.form.get('unidade_negocio')
            batch.centro_custo = request.form.get('centro_custo')
            batch.descricao = request.form.get('descricao')
            batch.updated_at = datetime.now()
            
            db.session.commit()
            flash('Lote atualizado com sucesso!', 'success')
            return redirect(url_for('batch_detail', batch_id=batch_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar lote: {str(e)}', 'error')
    
    return render_template('batches/edit.html', batch=batch)


@app.route('/batch/<int:batch_id>/close', methods=['POST'])
@login_required
def batch_close(batch_id):
    """Close a batch"""
    batch = Batch.query.get_or_404(batch_id)
    
    # Check permissions
    if batch.created_by != current_user.id and not current_user.is_admin:
        flash('Acesso negado ao lote solicitado.', 'error')
        return redirect(url_for('batches_list'))
    
    try:
        batch.close_batch()
        flash('Lote fechado com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao fechar lote: {str(e)}', 'error')
    
    return redirect(url_for('batch_detail', batch_id=batch_id))


@app.route('/batch/<int:batch_id>/reopen', methods=['POST'])
@login_required
def batch_reopen(batch_id):
    """Reopen a closed batch"""
    batch = Batch.query.get_or_404(batch_id)
    
    # Check permissions
    if batch.created_by != current_user.id and not current_user.is_admin:
        flash('Acesso negado ao lote solicitado.', 'error')
        return redirect(url_for('batches_list'))
    
    try:
        batch.status = BatchStatus.OPEN
        batch.closed_at = None
        batch.updated_at = datetime.now()
        db.session.commit()
        
        flash('Lote reaberto com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao reabrir lote: {str(e)}', 'error')
    
    return redirect(url_for('batch_detail', batch_id=batch_id))


@app.route('/api/batches')
@login_required
def api_batches():
    """API endpoint to get available batches for current user"""
    open_batches = Batch.query.filter_by(
        created_by=current_user.id,
        status=BatchStatus.OPEN
    ).order_by(Batch.updated_at.desc()).all()
    
    return jsonify([{
        'id': batch.id,
        'nome_contrato': batch.nome_contrato,
        'nome_item': batch.nome_item,
        'unidade_negocio': batch.unidade_negocio,
        'centro_custo': batch.centro_custo,
        'total_files': batch.total_files,
        'progress_percentage': batch.progress_percentage
    } for batch in open_batches])


@app.route('/api/batch/<int:batch_id>/stats')
@login_required
def api_batch_stats(batch_id):
    """API endpoint to get batch statistics"""
    batch = Batch.query.get_or_404(batch_id)
    
    # Check permissions
    if batch.created_by != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Acesso negado'}), 403
    
    return jsonify({
        'id': batch.id,
        'nome_contrato': batch.nome_contrato,
        'status': batch.status.value,
        'total_files': batch.total_files,
        'processed_files': batch.processed_files,
        'pending_files': batch.pending_files,
        'failed_files': batch.failed_files,
        'progress_percentage': batch.progress_percentage,
        'total_value': float(batch.total_value),
        'can_be_edited': batch.can_be_edited()
    })