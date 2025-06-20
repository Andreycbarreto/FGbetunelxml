import os
import logging
from datetime import datetime
from flask import session, render_template, request, redirect, url_for, flash, jsonify
from flask_login import current_user
from werkzeug.utils import secure_filename
from sqlalchemy import desc

from app import app, db, init_database
from replit_auth import require_login, make_replit_blueprint
from models import User, UploadedFile, NFERecord, NFEItem, ProcessingStatus, UserRole
from xml_processor import NFEXMLProcessor
from ai_agents import process_nfe_with_ai

app.register_blueprint(make_replit_blueprint(), url_prefix="/auth")

logger = logging.getLogger(__name__)

# Initialize database flag
_database_initialized = False

# Make session permanent and ensure database is initialized
@app.before_request
def make_session_permanent():
    global _database_initialized
    if not _database_initialized:
        init_database()
        _database_initialized = True
    session.permanent = True

# Allowed file extensions
ALLOWED_EXTENSIONS = {'xml'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    """Landing page - shows login for anonymous users, dashboard for logged-in users."""
    if not current_user.is_authenticated:
        return render_template('index.html')
    
    # Get user's processing statistics
    total_files = UploadedFile.query.filter_by(user_id=current_user.id).count()
    processed_files = UploadedFile.query.filter_by(
        user_id=current_user.id, 
        status=ProcessingStatus.COMPLETED
    ).count()
    pending_files = UploadedFile.query.filter_by(
        user_id=current_user.id, 
        status=ProcessingStatus.PENDING
    ).count()
    error_files = UploadedFile.query.filter_by(
        user_id=current_user.id, 
        status=ProcessingStatus.ERROR
    ).count()
    
    total_records = NFERecord.query.filter_by(user_id=current_user.id).count()
    
    # Get recent files
    recent_files = UploadedFile.query.filter_by(user_id=current_user.id)\
        .order_by(desc(UploadedFile.created_at))\
        .limit(5)\
        .all()
    
    stats = {
        'total_files': total_files,
        'processed_files': processed_files,
        'pending_files': pending_files,
        'error_files': error_files,
        'total_records': total_records,
        'recent_files': recent_files
    }
    
    return render_template('dashboard.html', stats=stats)

@app.route('/upload')
@require_login
def upload_page():
    """File upload page."""
    return render_template('upload.html')

@app.route('/upload', methods=['POST'])
@require_login
def upload_files():
    """Handle multiple XML file uploads."""
    if 'files' not in request.files:
        flash('No files selected', 'error')
        return redirect(request.url)
    
    files = request.files.getlist('files')
    
    if not files or all(file.filename == '' for file in files):
        flash('No files selected', 'error')
        return redirect(request.url)
    
    uploaded_count = 0
    error_count = 0
    
    for file in files:
        if file and file.filename and allowed_file(file.filename):
            try:
                filename = secure_filename(file.filename)
                # Add timestamp to avoid conflicts
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{timestamp}_{filename}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                
                # Save file
                file.save(file_path)
                
                # Create database record
                uploaded_file = UploadedFile(
                    user_id=current_user.id,
                    filename=filename,
                    original_filename=file.filename,
                    file_path=file_path,
                    file_size=os.path.getsize(file_path),
                    status=ProcessingStatus.PENDING
                )
                
                db.session.add(uploaded_file)
                db.session.commit()
                
                uploaded_count += 1
                logger.info(f"File uploaded successfully: {filename} by user {current_user.id}")
                
            except Exception as e:
                error_count += 1
                logger.error(f"Error uploading file {file.filename}: {str(e)}")
        else:
            error_count += 1
    
    if uploaded_count > 0:
        flash(f'Successfully uploaded {uploaded_count} file(s)', 'success')
    if error_count > 0:
        flash(f'Failed to upload {error_count} file(s)', 'error')
    
    return redirect(url_for('processing_queue'))

@app.route('/processing')
@require_login
def processing_queue():
    """Show processing queue and start processing."""
    # Get all user's files ordered by status and creation date
    files = UploadedFile.query.filter_by(user_id=current_user.id)\
        .order_by(UploadedFile.status.asc(), UploadedFile.created_at.asc())\
        .all()
    
    return render_template('processing.html', files=files)

@app.route('/process_all', methods=['POST'])
@require_login
def process_all_files():
    """Process all pending XML files."""
    # Get all pending files for the user
    pending_files = UploadedFile.query.filter_by(
        user_id=current_user.id,
        status=ProcessingStatus.PENDING
    ).order_by(UploadedFile.created_at.asc()).all()
    
    if not pending_files:
        return jsonify({
            'success': False,
            'message': 'Nenhum arquivo pendente para processar'
        })
    
    processed_count = 0
    error_count = 0
    
    for pending_file in pending_files:
        try:
            # Update status to processing
            pending_file.status = ProcessingStatus.PROCESSING
            pending_file.processing_started_at = datetime.now()
            db.session.commit()
            
            # Process the XML file
            processor = NFEXMLProcessor()
            
            # Read XML content
            with open(pending_file.file_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()
            
            # Extract data using XML processor
            raw_data = processor.process_xml_file(pending_file.file_path)
            
            # Create NFE record using raw XML data
            nfe_record = NFERecord(
                user_id=pending_file.user_id,
                uploaded_file_id=pending_file.id,
                **{k: v for k, v in raw_data.items() if k != 'items' and hasattr(NFERecord, k)}
            )
            
            # Store raw XML and processing info
            nfe_record.raw_xml_data = xml_content
            nfe_record.ai_confidence_score = 0.3
            nfe_record.ai_processing_notes = 'Processed using basic XML parser'
            
            db.session.add(nfe_record)
            db.session.flush()
            
            # Create NFE items from raw data
            items_data = raw_data.get('items', [])
            for item_data in items_data:
                nfe_item = NFEItem(
                    nfe_record_id=nfe_record.id,
                    **{k: v for k, v in item_data.items() if hasattr(NFEItem, k)}
                )
                db.session.add(nfe_item)
            
            # Update file status
            pending_file.status = ProcessingStatus.COMPLETED
            pending_file.processing_completed_at = datetime.now()
            db.session.commit()
            
            processed_count += 1
            logger.info(f"Successfully processed file {pending_file.filename} using basic XML parser")
            
        except Exception as e:
            error_count += 1
            pending_file.status = ProcessingStatus.ERROR
            pending_file.error_message = f'Erro no processamento: {str(e)}'
            pending_file.processing_completed_at = datetime.now()
            db.session.commit()
            logger.error(f"Erro ao processar arquivo {pending_file.filename}: {str(e)}")
    
    return jsonify({
        'success': True,
        'message': f'Processamento concluído: {processed_count} arquivos processados com sucesso',
        'processed_count': processed_count,
        'error_count': error_count
    })

@app.route('/process_next', methods=['POST'])
@require_login
def process_next_file():
    """Process the next pending XML file."""
    # Get the next pending file
    pending_file = UploadedFile.query.filter_by(
        user_id=current_user.id,
        status=ProcessingStatus.PENDING
    ).order_by(UploadedFile.created_at.asc()).first()
    
    if not pending_file:
        return jsonify({'success': False, 'message': 'Nenhum arquivo pendente para processar'})
    
    return process_single_file_internal(pending_file)

def process_file_internal(pending_file):
    """Internal function to process a single file - returns boolean."""
    try:
        # Update status to processing
        pending_file.status = ProcessingStatus.PROCESSING
        pending_file.processing_started_at = datetime.now()
        db.session.commit()
        
        # Process the XML file
        processor = NFEXMLProcessor()
        
        # Read XML content
        with open(pending_file.file_path, 'r', encoding='utf-8') as f:
            xml_content = f.read()
        
        # Extract data using XML processor
        raw_data = processor.process_xml_file(pending_file.file_path)
        
        # Fallback to basic XML processing when AI fails
        # Create NFE record using raw XML data
        nfe_record = NFERecord(
            user_id=pending_file.user_id,
            uploaded_file_id=pending_file.id,
            **{k: v for k, v in raw_data.items() if k != 'items' and hasattr(NFERecord, k)}
        )
        
        # Store raw XML and processing info
        nfe_record.raw_xml_data = xml_content
        nfe_record.ai_confidence_score = 0.3  # Low confidence for basic processing
        nfe_record.ai_processing_notes = 'Processed using basic XML parser (AI unavailable)'
        
        db.session.add(nfe_record)
        db.session.flush()  # Get the ID
        
        # Create NFE items from raw data
        items_data = raw_data.get('items', [])
        for item_data in items_data:
            nfe_item = NFEItem(
                nfe_record_id=nfe_record.id,
                **{k: v for k, v in item_data.items() if hasattr(NFEItem, k)}
            )
            db.session.add(nfe_item)
        
        # Update file status
        pending_file.status = ProcessingStatus.COMPLETED
        pending_file.processing_completed_at = datetime.now()
        
        db.session.commit()
        
        logger.info(f"Successfully processed file {pending_file.filename} using basic XML parser")
        return True
        
    except Exception as e:
        # Complete processing failure
        pending_file.status = ProcessingStatus.ERROR
        pending_file.error_message = f'XML processing failed: {str(e)}'
        pending_file.processing_completed_at = datetime.now()
        
        db.session.commit()
        
        logger.error(f"Failed to process file {pending_file.filename}: {str(e)}")
        return False

def process_single_file_internal(pending_file):
    """Internal function to process a single file - returns HTTP response."""
    
    try:
        # Update status to processing
        pending_file.status = ProcessingStatus.PROCESSING
        pending_file.processing_started_at = datetime.now()
        db.session.commit()
        
        # Process the XML file
        processor = NFEXMLProcessor()
        
        # Read XML content
        with open(pending_file.file_path, 'r', encoding='utf-8') as f:
            xml_content = f.read()
        
        # Extract data using XML processor
        raw_data = processor.process_xml_file(pending_file.file_path)
        
        # Use basic XML processing for now (AI processing disabled due to connectivity issues)
        use_ai_data = False
        ai_result = None
        
        if use_ai_data:
            # Create NFE record
            nfe_record = NFERecord(
                user_id=current_user.id,
                uploaded_file_id=pending_file.id,
                **{k: v for k, v in ai_result.data.items() if k != 'items' and k != 'raw_xml'}
            )
            
            # Store raw XML
            nfe_record.raw_xml_data = ai_result.data.get('raw_xml', xml_content)
            nfe_record.ai_confidence_score = ai_result.confidence_score
            nfe_record.ai_processing_notes = '\n'.join(ai_result.processing_notes)
            
            db.session.add(nfe_record)
            db.session.flush()  # Get the ID
            
            # Create NFE items
            items_data = ai_result.data.get('items', [])
            for item_data in items_data:
                nfe_item = NFEItem(
                    nfe_record_id=nfe_record.id,
                    **{k: v for k, v in item_data.items() if hasattr(NFEItem, k)}
                )
                db.session.add(nfe_item)
            
            # Update file status
            pending_file.status = ProcessingStatus.COMPLETED
            pending_file.processing_completed_at = datetime.now()
            
            db.session.commit()
            
            logger.info(f"Successfully processed file {pending_file.filename} for user {current_user.id}")
            
            return jsonify({
                'success': True,
                'message': f'Successfully processed {pending_file.original_filename}',
                'confidence_score': ai_result.confidence_score,
                'processing_notes': ai_result.processing_notes
            })
        
        else:
            # Fallback to basic XML processing when AI fails
            try:
                # Create NFE record using raw XML data
                nfe_record = NFERecord(
                    user_id=current_user.id,
                    uploaded_file_id=pending_file.id,
                    **{k: v for k, v in raw_data.items() if k != 'items' and hasattr(NFERecord, k)}
                )
                
                # Store raw XML and processing info
                nfe_record.raw_xml_data = xml_content
                nfe_record.ai_confidence_score = 0.3  # Low confidence for basic processing
                nfe_record.ai_processing_notes = 'Processed using basic XML parser (AI unavailable)'
                
                db.session.add(nfe_record)
                db.session.flush()  # Get the ID
                
                # Create NFE items from raw data
                items_data = raw_data.get('items', [])
                for item_data in items_data:
                    nfe_item = NFEItem(
                        nfe_record_id=nfe_record.id,
                        **{k: v for k, v in item_data.items() if hasattr(NFEItem, k)}
                    )
                    db.session.add(nfe_item)
                
                # Update file status
                pending_file.status = ProcessingStatus.COMPLETED
                pending_file.processing_completed_at = datetime.now()
                
                db.session.commit()
                
                logger.info(f"Successfully processed file {pending_file.filename} using basic XML parser")
                
                return jsonify({
                    'success': True,
                    'message': f'Successfully processed {pending_file.original_filename} (basic mode)',
                    'confidence_score': 0.3,
                    'processing_notes': ['Processed using basic XML parser']
                })
                
            except Exception as fallback_error:
                # Complete processing failure
                pending_file.status = ProcessingStatus.ERROR
                pending_file.error_message = f'XML processing failed: {str(fallback_error)}'
                pending_file.processing_completed_at = datetime.now()
                
                db.session.commit()
                
                logger.error(f"Failed to process file {pending_file.filename}: {pending_file.error_message}")
                
                return jsonify({
                    'success': False,
                    'message': f'Failed to process {pending_file.original_filename}',
                    'errors': [str(fallback_error)]
                })
    
    except Exception as e:
        # Handle unexpected errors
        pending_file.status = ProcessingStatus.ERROR
        pending_file.error_message = str(e)
        pending_file.processing_completed_at = datetime.now()
        
        db.session.commit()
        
        logger.error(f"Unexpected error processing file {pending_file.filename}: {str(e)}")
        
        return jsonify({
            'success': False,
            'message': f'Unexpected error processing {pending_file.original_filename}',
            'error': str(e)
        })

@app.route('/data')
@require_login
def data_view():
    """View processed NFe data."""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Get user's NFe records with pagination
    records = NFERecord.query.filter_by(user_id=current_user.id)\
        .order_by(desc(NFERecord.created_at))\
        .paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
    
    return render_template('data_view.html', records=records)

# Admin routes for user management
@app.route('/admin')
@require_login
def admin_dashboard():
    """Admin dashboard."""
    if not current_user.is_admin:
        flash('Acesso negado. Apenas administradores podem acessar esta área.', 'error')
        return redirect(url_for('index'))
    
    # Get statistics
    total_users = User.query.count()
    active_users = User.query.filter_by(active=True).count()
    total_files = UploadedFile.query.count()
    total_records = NFERecord.query.count()
    
    # Recent users
    recent_users = User.query.order_by(desc(User.created_at)).limit(5).all()
    
    stats = {
        'total_users': total_users,
        'active_users': active_users,
        'total_files': total_files,
        'total_records': total_records
    }
    
    return render_template('admin/dashboard.html', stats=stats, recent_users=recent_users)

@app.route('/admin/users')
@require_login
def admin_users():
    """Manage users."""
    if not current_user.is_admin:
        flash('Acesso negado.', 'error')
        return redirect(url_for('index'))
    
    page = request.args.get('page', 1, type=int)
    users = User.query.order_by(desc(User.created_at))\
        .paginate(page=page, per_page=20, error_out=False)
    
    return render_template('admin/users.html', users=users)

@app.route('/admin/users/register', methods=['GET', 'POST'])
@require_login
def admin_register_user():
    """Register a new user."""
    if not current_user.is_admin:
        flash('Acesso negado.', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        company = request.form.get('company')
        role = request.form.get('role')
        active = bool(request.form.get('active'))
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Já existe um usuário com este email.', 'error')
            return render_template('admin/register_user.html')
        
        # Create new user with a generated ID (since we don't have the actual Replit user ID yet)
        import uuid
        new_user = User(
            id=str(uuid.uuid4()),  # Temporary ID, will be replaced when user first logs in
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            company=company,
            role=UserRole(role.lower()),
            active=active,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        try:
            db.session.add(new_user)
            db.session.commit()
            flash(f'Usuário {first_name} {last_name} cadastrado com sucesso! O usuário pode fazer login quando tiver uma conta Replit com o email {email}.', 'success')
            return redirect(url_for('admin_users'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao cadastrar usuário: {str(e)}', 'error')
    
    return render_template('admin/register_user.html')

@app.route('/admin/users/<user_id>/toggle_status', methods=['POST'])
@require_login
def admin_toggle_user_status(user_id):
    """Toggle user active status."""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Acesso negado'})
    
    user = User.query.get_or_404(user_id)
    user.active = not user.active
    db.session.commit()
    
    status = 'ativado' if user.active else 'desativado'
    return jsonify({
        'success': True, 
        'message': f'Usuário {status} com sucesso',
        'active': user.active
    })

@app.route('/admin/users/<user_id>/edit', methods=['GET', 'POST'])
@require_login
def admin_edit_user(user_id):
    """Edit user."""
    if not current_user.is_admin:
        flash('Acesso negado.', 'error')
        return redirect(url_for('index'))
    
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        user.first_name = request.form.get('first_name')
        user.last_name = request.form.get('last_name')
        user.email = request.form.get('email')
        user.phone = request.form.get('phone')
        user.company = request.form.get('company')
        user.role = UserRole(request.form.get('role'))
        user.active = request.form.get('active') == 'on'
        
        db.session.commit()
        flash('Usuário atualizado com sucesso!', 'success')
        return redirect(url_for('admin_users'))
    
    return render_template('admin/edit_user.html', user=user, roles=UserRole)

@app.route('/profile')
@require_login
def user_profile():
    """User profile page."""
    return render_template('profile.html', user=current_user)

@app.route('/profile/edit', methods=['GET', 'POST'])
@require_login
def edit_profile():
    """Edit user profile."""
    if request.method == 'POST':
        current_user.first_name = request.form.get('first_name')
        current_user.last_name = request.form.get('last_name')
        current_user.phone = request.form.get('phone')
        current_user.company = request.form.get('company')
        
        db.session.commit()
        flash('Perfil atualizado com sucesso!', 'success')
        return redirect(url_for('user_profile'))
    
    return render_template('edit_profile.html', user=current_user)

@app.route('/data/<int:record_id>')
@require_login
def view_record(record_id):
    """View detailed NFe record with items."""
    record = NFERecord.query.filter_by(
        id=record_id,
        user_id=current_user.id
    ).first_or_404()
    
    return render_template('record_detail.html', record=record)

@app.route('/delete_file/<int:file_id>', methods=['POST'])
@require_login
def delete_file(file_id):
    """Delete an uploaded file and its associated records."""
    uploaded_file = UploadedFile.query.filter_by(
        id=file_id,
        user_id=current_user.id
    ).first_or_404()
    
    try:
        # Delete associated NFE records and items
        nfe_records = NFERecord.query.filter_by(uploaded_file_id=uploaded_file.id).all()
        for record in nfe_records:
            # Delete items first
            NFEItem.query.filter_by(nfe_record_id=record.id).delete()
            db.session.delete(record)
        
        # Delete physical file
        if os.path.exists(uploaded_file.file_path):
            os.remove(uploaded_file.file_path)
        
        # Delete database record
        db.session.delete(uploaded_file)
        db.session.commit()
        
        flash(f'File {uploaded_file.original_filename} deleted successfully', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting file: {str(e)}', 'error')
        logger.error(f"Error deleting file {file_id}: {str(e)}")
    
    return redirect(url_for('processing_queue'))

@app.route('/api/processing_status')
@require_login
def api_processing_status():
    """API endpoint to get current processing status."""
    total_files = UploadedFile.query.filter_by(user_id=current_user.id).count()
    processed_files = UploadedFile.query.filter_by(
        user_id=current_user.id, 
        status=ProcessingStatus.COMPLETED
    ).count()
    pending_files = UploadedFile.query.filter_by(
        user_id=current_user.id, 
        status=ProcessingStatus.PENDING
    ).count()
    processing_files = UploadedFile.query.filter_by(
        user_id=current_user.id, 
        status=ProcessingStatus.PROCESSING
    ).count()
    error_files = UploadedFile.query.filter_by(
        user_id=current_user.id, 
        status=ProcessingStatus.ERROR
    ).count()
    
    return jsonify({
        'total_files': total_files,
        'processed_files': processed_files,
        'pending_files': pending_files,
        'processing_files': processing_files,
        'error_files': error_files
    })

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500
