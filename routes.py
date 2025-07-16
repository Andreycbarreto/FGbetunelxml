import os
import logging
from datetime import datetime, timezone, timedelta
from functools import wraps
from flask import session, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import current_user, login_user, logout_user
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy import desc
from sqlalchemy.exc import IntegrityError

from app import app, db, init_database
from replit_auth import require_login, make_replit_blueprint
from models import User, UploadedFile, NFERecord, NFEItem, ProcessingStatus, UserRole, Batch, BatchStatus, Empresa, Filial, UserSettings
from xml_processor import NFEXMLProcessor
import batch_routes  # Import batch management routes
import filial_routes  # Import filial management routes
import settings_routes  # Import settings management routes
from ai_agents import process_nfe_with_ai
from fluig_integration import get_fluig_integration_for_user
from pdf_simple_processor import SimplePDFProcessor
from pdf_vision_processor import PDFVisionProcessor
from async_pdf_processor import add_pdf_processing_job, start_async_processor, get_processing_status

app.register_blueprint(make_replit_blueprint(), url_prefix="/auth")

# Initialize async PDF processor
start_async_processor()

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
ALLOWED_EXTENSIONS = {'xml', 'pdf'}

def allowed_file(filename, file_type='xml'):
    """Check if the uploaded file has an allowed extension."""
    if file_type == 'xml':
        return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'xml'
    elif file_type == 'pdf':
        return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'pdf'
    return False

# Hybrid authentication decorator for both OAuth and local auth
def login_required_hybrid(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Admin-only access decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        if not current_user.is_admin:
            flash('Acesso negado. Apenas administradores podem acessar esta página.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    """Landing page - shows login for anonymous users, dashboard for logged-in users."""
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    
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
@login_required_hybrid
def upload_page():
    """File upload page with batch selection."""
    # Get open batches for current user
    open_batches = Batch.query.filter_by(
        created_by=current_user.id,
        status=BatchStatus.OPEN
    ).order_by(Batch.updated_at.desc()).all()
    
    return render_template('upload.html', open_batches=open_batches)

@app.route('/upload', methods=['POST'])
@login_required_hybrid
def upload_files():
    """Handle multiple file uploads (XML or PDF)."""
    if 'files' not in request.files:
        flash('Nenhum arquivo selecionado', 'error')
        return redirect(request.url)
    
    files = request.files.getlist('files')
    file_type = request.form.get('file_type', 'xml')  # Default to XML
    batch_id = request.form.get('batch_id')  # Optional batch ID
    
    # Validate batch if provided
    batch = None
    if batch_id:
        try:
            batch = Batch.query.get(int(batch_id))
            if not batch or batch.created_by != current_user.id:
                flash('Lote inválido ou acesso negado', 'error')
                return redirect(request.url)
            if not batch.can_be_edited():
                flash('Este lote não permite mais adições de arquivos', 'error')
                return redirect(request.url)
        except (ValueError, TypeError):
            flash('ID de lote inválido', 'error')
            return redirect(request.url)
    
    if not files or all(file.filename == '' for file in files):
        flash('Nenhum arquivo selecionado', 'error')
        return redirect(request.url)
    
    uploaded_count = 0
    error_count = 0
    
    for file in files:
        if file and file.filename and allowed_file(file.filename, file_type):
            try:
                filename = secure_filename(file.filename)
                # Add timestamp to avoid conflicts
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{timestamp}_{filename}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                
                # Save file
                file.save(file_path)
                
                # Create database record
                uploaded_file = UploadedFile()
                uploaded_file.user_id = current_user.id
                uploaded_file.filename = filename
                uploaded_file.original_filename = file.filename
                uploaded_file.file_path = file_path
                uploaded_file.file_size = os.path.getsize(file_path)
                uploaded_file.file_type = file_type
                uploaded_file.status = ProcessingStatus.PENDING
                uploaded_file.batch_id = batch.id if batch else None
                
                db.session.add(uploaded_file)
                db.session.commit()
                
                uploaded_count += 1
                logger.info(f"{file_type.upper()} file uploaded successfully: {filename} by user {current_user.id}")
                
            except Exception as e:
                error_count += 1
                logger.error(f"Error uploading file {file.filename}: {str(e)}")
        else:
            error_count += 1
            logger.warning(f"File rejected: {file.filename} (type: {file_type})")
    
    if uploaded_count > 0:
        flash(f'Successfully uploaded {uploaded_count} file(s)', 'success')
    if error_count > 0:
        flash(f'Failed to upload {error_count} file(s)', 'error')
    
    return redirect(url_for('processing_queue'))

@app.route('/processing')
@login_required_hybrid
def processing_queue():
    """Show processing queue and start processing."""
    # Get all user's files ordered by status and creation date
    files = UploadedFile.query.filter_by(user_id=current_user.id)\
        .order_by(UploadedFile.status.asc(), UploadedFile.created_at.asc())\
        .all()
    
    return render_template('processing.html', files=files)

@app.route('/process_all', methods=['POST'])
@login_required_hybrid
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
            
            # Process the file based on type
            if pending_file.file_type == 'pdf':
                # Add PDF to async processing queue instead of processing immediately
                add_pdf_processing_job(
                    file_id=pending_file.id,
                    file_path=pending_file.file_path,
                    original_filename=pending_file.original_filename,
                    user_id=pending_file.user_id
                )
                logger.info(f"PDF {pending_file.original_filename} added to async processing queue")
                
                # Skip the rest of the processing for PDFs as it will be handled asynchronously
                processed_count += 1
                continue
            else:
                # Process XML file
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
            
            # Store data and processing info based on file type
            if pending_file.file_type == 'pdf':
                nfe_record.raw_xml_data = f"PDF processed with GPT-4 Vision: {pending_file.original_filename}"
                nfe_record.ai_confidence_score = 0.9  # Very high confidence for Vision processing
                nfe_record.ai_processing_notes = 'Processed using GPT-4 Vision (image analysis)'
            else:
                nfe_record.raw_xml_data = xml_content
                nfe_record.ai_confidence_score = 0.3  # Low confidence for basic processing
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
            if pending_file.file_type == 'pdf':
                logger.info(f"Successfully processed file {pending_file.filename} using GPT-4 Vision (image analysis)")
            else:
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

@app.route('/processing_status', methods=['GET'])
@login_required_hybrid
def get_processing_status():
    """Get current processing queue status."""
    status = get_processing_status()
    return jsonify(status)

@app.route('/process_next', methods=['POST'])
@login_required_hybrid
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
        
        # Initialize variables
        nfe_record = NFERecord()
        nfe_record.user_id = pending_file.user_id
        nfe_record.uploaded_file_id = pending_file.id
        items_data = []
        
        # Determine processing method based on file type
        if pending_file.file_type == 'pdf':
            # Process PDF file with simplified processor
            pdf_processor = SimplePDFProcessor()
            pdf_result = pdf_processor.process_pdf_to_nfe_data(pending_file.file_path)
            
            if pdf_result['success']:
                # Map AI-extracted data to NFE record fields
                extracted_data = pdf_result['data']
                for field, value in extracted_data.items():
                    if hasattr(nfe_record, field) and field != 'items':
                        setattr(nfe_record, field, value)
                
                # Store processing metadata
                nfe_record.raw_xml_data = pdf_result.get('markdown_content', '')
                nfe_record.ai_confidence_score = pdf_result.get('confidence_score', 0.85)
                nfe_record.ai_processing_notes = f"PDF processed with AI. Notes: {'; '.join(pdf_result.get('processing_notes', []))}"
                
                # Get items data
                items_data = extracted_data.get('items', [])
                
            else:
                raise Exception(f"Falha no processamento do PDF: {pdf_result.get('error', 'Erro desconhecido')}")
        
        else:
            # Process XML file (existing logic)
            processor = NFEXMLProcessor()
            
            # Read XML content (only for XML files)
            if pending_file.file_type == 'xml':
                with open(pending_file.file_path, 'r', encoding='utf-8') as f:
                    xml_content = f.read()
                
                # Extract data using XML processor
                raw_data = processor.process_xml_file(pending_file.file_path)
            else:
                # This shouldn't happen, but handle gracefully
                xml_content = f"Non-XML file: {pending_file.original_filename}"
                raw_data = {}
            
            # Map raw data to NFE record fields
            for field, value in raw_data.items():
                if hasattr(nfe_record, field) and field != 'items':
                    setattr(nfe_record, field, value)
            
            # Store raw XML and processing info
            nfe_record.raw_xml_data = xml_content
            nfe_record.ai_confidence_score = 0.8  # High confidence for XML processing
            nfe_record.ai_processing_notes = 'Processed using XML parser'
            
            # Get items data
            items_data = raw_data.get('items', [])
        
        db.session.add(nfe_record)
        db.session.flush()  # Get the ID
        
        for item_data in items_data:
            nfe_item = NFEItem()
            nfe_item.nfe_record_id = nfe_record.id
            
            # Map item data to NFE item fields
            for field, value in item_data.items():
                if hasattr(nfe_item, field):
                    setattr(nfe_item, field, value)
            
            db.session.add(nfe_item)
        
        # Update file status
        pending_file.status = ProcessingStatus.COMPLETED
        pending_file.processing_completed_at = datetime.now()
        
        db.session.commit()
        
        file_type_desc = "PDF with AI" if pending_file.file_type == 'pdf' else "XML parser"
        logger.info(f"Successfully processed file {pending_file.filename} using {file_type_desc}")
        return True
        
    except Exception as e:
        # Complete processing failure
        pending_file.status = ProcessingStatus.ERROR
        error_desc = f'{pending_file.file_type.upper()} processing failed: {str(e)}'
        pending_file.error_message = error_desc
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
        
        # Read file content based on type
        if pending_file.file_type == 'pdf':
            # Process PDF file
            pdf_processor = SimplePDFProcessor()
            pdf_result = pdf_processor.process_pdf_to_nfe_data(pending_file.file_path)
            
            if not pdf_result['success']:
                raise Exception(f"PDF processing failed: {pdf_result.get('error', 'Unknown error')}")
            
            # Use PDF processing results
            raw_data = pdf_result['data']
            xml_content = pdf_result.get('markdown_content', '')
            
        else:
            # Read XML content (only for XML files)
            if pending_file.file_type == 'xml':
                with open(pending_file.file_path, 'r', encoding='utf-8') as f:
                    xml_content = f.read()
                
                # Extract data using XML processor
                raw_data = processor.process_xml_file(pending_file.file_path)
            else:
                # This shouldn't happen in this branch, but handle gracefully
                xml_content = f"Non-XML file: {pending_file.original_filename}"
                raw_data = {}
        
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
                
                # Store raw data and processing info
                if pending_file.file_type == 'pdf':
                    nfe_record.raw_xml_data = f"PDF processed: {pending_file.original_filename}"
                    nfe_record.ai_confidence_score = 0.5  # Medium confidence for PDF processing
                    nfe_record.ai_processing_notes = 'Processed using PDF parser'
                else:
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
@login_required_hybrid
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
@admin_required
def admin_dashboard():
    """Admin dashboard."""
    
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
@admin_required
def admin_users():
    """Manage users."""
    
    page = request.args.get('page', 1, type=int)
    users = User.query.order_by(desc(User.created_at))\
        .paginate(page=page, per_page=20, error_out=False)
    
    return render_template('admin/users.html', users=users)

@app.route('/admin/users/register', methods=['GET', 'POST'])
@admin_required
def admin_register_user():
    """Register a new user."""
    
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        company = request.form.get('company')
        role = request.form.get('role')
        password = request.form.get('password')
        active = bool(request.form.get('active'))
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Já existe um usuário com este email.', 'error')
            return render_template('admin/register_user.html')
        
        # Validate password
        if not password or len(password) < 6:
            flash('A senha deve ter pelo menos 6 caracteres.', 'error')
            return render_template('admin/register_user.html')
        
        # Create new user with a generated ID
        import uuid
        new_user = User(
            id=str(uuid.uuid4()),
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            company=company,
            role=UserRole(role.lower()),
            active=active,
            auth_method='local',
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        # Set password for local authentication
        new_user.set_password(password)
        
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
@admin_required
def admin_toggle_user_status(user_id):
    """Toggle user active status."""
    
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
@admin_required
def admin_edit_user(user_id):
    """Edit user."""
    
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
@login_required_hybrid
def user_profile():
    """User profile page."""
    return render_template('profile.html', user=current_user)

@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required_hybrid
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
@login_required_hybrid
def view_record(record_id):
    """View detailed NFe record with items."""
    record = NFERecord.query.filter_by(
        id=record_id,
        user_id=current_user.id
    ).first_or_404()
    
    return render_template('record_detail.html', record=record)

@app.route('/delete_file/<int:file_id>', methods=['POST'])
@login_required_hybrid
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
@login_required_hybrid
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

@app.route('/download_pdf/<int:record_id>')
@login_required_hybrid
def download_pdf(record_id):
    """Download original PDF file for a specific NFE record."""
    record = NFERecord.query.filter_by(
        id=record_id,
        user_id=current_user.id
    ).first_or_404()
    
    # Check if the record has an original PDF path
    if not record.original_pdf_path or not record.original_pdf_filename:
        flash('PDF original não encontrado para este lançamento.', 'error')
        return redirect(url_for('view_record', record_id=record_id))
    
    # Check if the file exists
    if not os.path.exists(record.original_pdf_path):
        flash('Arquivo PDF não encontrado no sistema.', 'error')
        return redirect(url_for('view_record', record_id=record_id))
    
    try:
        # Send the file with the original filename
        return send_file(
            record.original_pdf_path,
            as_attachment=True,
            download_name=record.original_pdf_filename,
            mimetype='application/pdf'
        )
    except Exception as e:
        logger.error(f"Error downloading PDF for record {record_id}: {str(e)}")
        flash('Erro ao fazer download do PDF.', 'error')
        return redirect(url_for('view_record', record_id=record_id))

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500


# Rotas para gerenciamento de empresas
@app.route('/empresas')
@login_required_hybrid
def empresas_list():
    """Lista todas as empresas do usuário"""
    empresas = Empresa.query.filter_by(user_id=current_user.id).order_by(Empresa.numero).all()
    return render_template('empresas/list.html', empresas=empresas)


@app.route('/empresas/nova', methods=['GET', 'POST'])
@login_required_hybrid
def empresa_nova():
    """Criar nova empresa"""
    if request.method == 'POST':
        try:
            # Validar se já existe empresa com mesmo número para o usuário
            numero = int(request.form.get('numero'))
            existing_numero = Empresa.query.filter_by(
                user_id=current_user.id,
                numero=numero
            ).first()
            
            if existing_numero:
                flash('Já existe uma empresa com este número.', 'error')
                return render_template('empresas/form.html')
            
            # Validar se CNPJ já existe
            cnpj = request.form.get('cnpj').replace('.', '').replace('/', '').replace('-', '')
            existing_cnpj = Empresa.query.filter_by(cnpj=cnpj).first()
            
            if existing_cnpj:
                flash('CNPJ já cadastrado no sistema.', 'error')
                return render_template('empresas/form.html')
            
            # Criar nova empresa
            empresa = Empresa(
                numero=numero,
                nome_fantasia=request.form.get('nome_fantasia'),
                cnpj=cnpj,
                razao_social=request.form.get('razao_social'),
                user_id=current_user.id
            )
            
            db.session.add(empresa)
            db.session.commit()
            
            flash('Empresa criada com sucesso!', 'success')
            return redirect(url_for('empresas_list'))
            
        except ValueError:
            flash('Número deve ser um valor numérico.', 'error')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar empresa: {str(e)}', 'error')
    
    return render_template('empresas/form.html')


@app.route('/empresas/<int:empresa_id>/editar', methods=['GET', 'POST'])
@login_required_hybrid
def empresa_editar(empresa_id):
    """Editar empresa existente"""
    empresa = Empresa.query.filter_by(
        id=empresa_id,
        user_id=current_user.id
    ).first_or_404()
    
    if request.method == 'POST':
        try:
            numero = int(request.form.get('numero'))
            
            # Validar se já existe empresa com mesmo número (exceto a atual)
            existing_numero = Empresa.query.filter(
                Empresa.user_id == current_user.id,
                Empresa.numero == numero,
                Empresa.id != empresa_id
            ).first()
            
            if existing_numero:
                flash('Já existe uma empresa com este número.', 'error')
                return render_template('empresas/form.html', empresa=empresa)
            
            # Validar se CNPJ já existe (exceto o atual)
            cnpj = request.form.get('cnpj').replace('.', '').replace('/', '').replace('-', '')
            existing_cnpj = Empresa.query.filter(
                Empresa.cnpj == cnpj,
                Empresa.id != empresa_id
            ).first()
            
            if existing_cnpj:
                flash('CNPJ já cadastrado no sistema.', 'error')
                return render_template('empresas/form.html', empresa=empresa)
            
            # Atualizar empresa
            empresa.numero = numero
            empresa.nome_fantasia = request.form.get('nome_fantasia')
            empresa.cnpj = cnpj
            empresa.razao_social = request.form.get('razao_social')
            empresa.updated_at = datetime.now()
            
            db.session.commit()
            
            flash('Empresa atualizada com sucesso!', 'success')
            return redirect(url_for('empresas_list'))
            
        except ValueError:
            flash('Número deve ser um valor numérico.', 'error')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar empresa: {str(e)}', 'error')
    
    return render_template('empresas/form.html', empresa=empresa)


@app.route('/empresas/<int:empresa_id>/excluir', methods=['POST'])
@login_required_hybrid
def empresa_excluir(empresa_id):
    """Excluir empresa"""
    empresa = Empresa.query.filter_by(
        id=empresa_id,
        user_id=current_user.id
    ).first_or_404()
    
    try:
        db.session.delete(empresa)
        db.session.commit()
        flash('Empresa excluída com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir empresa: {str(e)}', 'error')
    
    return redirect(url_for('empresas_list'))

# Traditional Login Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Traditional email/password login."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not email or not password:
            flash('Email e senha são obrigatórios.', 'error')
            return render_template('auth/login.html')
        
        # Find user by email
        user = User.query.filter_by(email=email, active=True).first()
        
        if user and user.check_password(password):
            # Update last login
            user.last_login = datetime.now()
            db.session.commit()
            
            # Log user in
            login_user(user, remember=True)
            flash(f'Bem-vindo, {user.full_name}!', 'success')
            
            # Redirect to next page or home
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Email ou senha incorretos.', 'error')
    
    return render_template('auth/login.html')

@app.route('/logout')
def local_logout():
    """Traditional logout."""
    logout_user()
    flash('Você foi desconectado com sucesso.', 'info')
    return redirect(url_for('login'))


# Rotas de integração com Fluig
@app.route('/nfe/integrar-fluig/<int:nfe_id>')
@require_login
def integrar_fluig(nfe_id):
    """Integrar NFE com o sistema Fluig"""
    nfe_record = NFERecord.query.get_or_404(nfe_id)
    
    # Verificar se o usuário tem permissão para acessar este arquivo
    if nfe_record.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Acesso negado!'})
    
    # Verificar se já foi integrado
    if nfe_record.fluig_process_id:
        return jsonify({
            'success': False, 
            'message': f'NFE já integrada ao Fluig! Processo ID: {nfe_record.fluig_process_id}'
        })
    
    # Obter integração Fluig para o usuário
    fluig_integration = get_fluig_integration_for_user(current_user.id)
    
    if not fluig_integration:
        return jsonify({
            'success': False, 
            'message': 'Configuração do Fluig não encontrada. Configure suas credenciais nas configurações do sistema.'
        })
    
    # Executar integração
    result = fluig_integration.integrate_nfe_with_fluig(nfe_id)
    
    if result['success']:
        return jsonify({
            'success': True,
            'message': result['message'],
            'process_id': result['process_id'],
            'document_id': result['document_id']
        })
    else:
        return jsonify({
            'success': False,
            'message': result['message']
        })


@app.route('/nfe/status-fluig/<int:nfe_id>')
@require_login
def status_fluig(nfe_id):
    """Verificar status da integração Fluig"""
    nfe_record = NFERecord.query.get_or_404(nfe_id)
    
    # Verificar se o usuário tem permissão para acessar este arquivo
    if nfe_record.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Acesso negado!'})
    
    if nfe_record.fluig_process_id:
        return jsonify({
            'success': True,
            'integrated': True,
            'process_id': nfe_record.fluig_process_id,
            'document_id': nfe_record.fluig_document_id,
            'integration_date': nfe_record.fluig_integration_date.strftime('%d/%m/%Y %H:%M:%S') if nfe_record.fluig_integration_date else None
        })
    else:
        return jsonify({
            'success': True,
            'integrated': False,
            'message': 'NFE não integrada ao Fluig'
        })
