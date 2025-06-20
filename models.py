from datetime import datetime
import enum

from app import db
from flask_dance.consumer.storage.sqla import OAuthConsumerMixin
from flask_login import UserMixin
from sqlalchemy import UniqueConstraint, Numeric

# (IMPORTANT) This table is mandatory for Replit Auth, don't drop it.
class UserRole(enum.Enum):
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.String, primary_key=True)
    email = db.Column(db.String, unique=True, nullable=True)
    first_name = db.Column(db.String, nullable=True)
    last_name = db.Column(db.String, nullable=True)
    profile_image_url = db.Column(db.String, nullable=True)
    
    # Authentication fields
    password_hash = db.Column(db.String(256), nullable=True)  # For local authentication
    auth_method = db.Column(db.String(20), default='oauth')  # 'oauth' or 'local'
    
    # Additional user fields
    role = db.Column(db.Enum(UserRole), default=UserRole.USER)
    active = db.Column(db.Boolean, default=True)
    phone = db.Column(db.String(20), nullable=True)
    company = db.Column(db.String(255), nullable=True)
    last_login = db.Column(db.DateTime, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    uploaded_files = db.relationship('UploadedFile', backref='user', lazy=True)
    nfe_records = db.relationship('NFERecord', backref='user', lazy=True)
    
    @property
    def full_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.email:
            return self.email.split('@')[0]
        return f"User {self.id[:8]}"
    
    @property
    def is_admin(self):
        return self.role == UserRole.ADMIN
    
    def set_password(self, password):
        """Set password hash for local authentication."""
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password)
        self.auth_method = 'local'
    
    def check_password(self, password):
        """Check password for local authentication."""
        from werkzeug.security import check_password_hash
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

# (IMPORTANT) This table is mandatory for Replit Auth, don't drop it.
class OAuth(OAuthConsumerMixin, db.Model):
    user_id = db.Column(db.String, db.ForeignKey(User.id))
    browser_session_key = db.Column(db.String, nullable=False)
    user = db.relationship(User)

    __table_args__ = (UniqueConstraint(
        'user_id',
        'browser_session_key',
        'provider',
        name='uq_user_browser_session_key_provider',
    ),)

class ProcessingStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"

class UploadedFile(db.Model):
    __tablename__ = 'uploaded_files'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    status = db.Column(db.Enum(ProcessingStatus), default=ProcessingStatus.PENDING)
    error_message = db.Column(db.Text, nullable=True)
    processing_started_at = db.Column(db.DateTime, nullable=True)
    processing_completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

class NFERecord(db.Model):
    __tablename__ = 'nfe_records'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    uploaded_file_id = db.Column(db.Integer, db.ForeignKey('uploaded_files.id'), nullable=False)
    
    # Identification fields
    chave_nfe = db.Column(db.String(44), nullable=True)  # NFe key
    numero_nf = db.Column(db.String(20), nullable=True)
    serie = db.Column(db.String(10), nullable=True)
    modelo = db.Column(db.String(5), nullable=True)
    data_emissao = db.Column(db.DateTime, nullable=True)
    data_saida_entrada = db.Column(db.DateTime, nullable=True)
    tipo_operacao = db.Column(db.String(10), nullable=True)  # Entrada/Saída
    natureza_operacao = db.Column(db.Text, nullable=True)
    
    # Emitente fields
    emitente_cnpj = db.Column(db.String(18), nullable=True)
    emitente_nome = db.Column(db.String(255), nullable=True)
    emitente_fantasia = db.Column(db.String(255), nullable=True)
    emitente_ie = db.Column(db.String(20), nullable=True)
    emitente_endereco = db.Column(db.Text, nullable=True)
    emitente_municipio = db.Column(db.String(100), nullable=True)
    emitente_uf = db.Column(db.String(2), nullable=True)
    emitente_cep = db.Column(db.String(10), nullable=True)
    
    # Destinatário fields
    destinatario_cnpj = db.Column(db.String(18), nullable=True)
    destinatario_nome = db.Column(db.String(255), nullable=True)
    destinatario_ie = db.Column(db.String(20), nullable=True)
    destinatario_endereco = db.Column(db.Text, nullable=True)
    destinatario_municipio = db.Column(db.String(100), nullable=True)
    destinatario_uf = db.Column(db.String(2), nullable=True)
    destinatario_cep = db.Column(db.String(10), nullable=True)
    
    # Valores totais
    valor_total_produtos = db.Column(Numeric(15, 2), nullable=True)
    valor_total_nf = db.Column(Numeric(15, 2), nullable=True)
    valor_icms = db.Column(Numeric(15, 2), nullable=True)
    valor_ipi = db.Column(Numeric(15, 2), nullable=True)
    valor_pis = db.Column(Numeric(15, 2), nullable=True)
    valor_cofins = db.Column(Numeric(15, 2), nullable=True)
    valor_frete = db.Column(Numeric(15, 2), nullable=True)
    valor_seguro = db.Column(Numeric(15, 2), nullable=True)
    valor_desconto = db.Column(Numeric(15, 2), nullable=True)
    valor_tributos = db.Column(Numeric(15, 2), nullable=True)
    
    # Transport and payment info
    modalidade_frete = db.Column(db.String(50), nullable=True)
    transportadora_cnpj = db.Column(db.String(18), nullable=True)
    transportadora_nome = db.Column(db.String(255), nullable=True)
    forma_pagamento = db.Column(db.String(100), nullable=True)
    
    # Protocol and status
    protocolo_autorizacao = db.Column(db.String(50), nullable=True)
    status_autorizacao = db.Column(db.String(20), nullable=True)
    ambiente = db.Column(db.String(20), nullable=True)  # Produção/Homologação
    
    # AI processing metadata
    ai_confidence_score = db.Column(db.Float, nullable=True)
    ai_processing_notes = db.Column(db.Text, nullable=True)
    raw_xml_data = db.Column(db.Text, nullable=True)  # Store original XML for reference
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    uploaded_file = db.relationship('UploadedFile', backref='nfe_records')
    items = db.relationship('NFEItem', backref='nfe_record', lazy=True)

class NFEItem(db.Model):
    __tablename__ = 'nfe_items'
    id = db.Column(db.Integer, primary_key=True)
    nfe_record_id = db.Column(db.Integer, db.ForeignKey('nfe_records.id'), nullable=False)
    
    # Item identification
    numero_item = db.Column(db.Integer, nullable=True)
    codigo_produto = db.Column(db.String(100), nullable=True)
    descricao_produto = db.Column(db.Text, nullable=True)
    ncm = db.Column(db.String(20), nullable=True)
    cfop = db.Column(db.String(10), nullable=True)
    
    # Commercial quantities and values
    unidade_comercial = db.Column(db.String(10), nullable=True)
    quantidade_comercial = db.Column(Numeric(15, 4), nullable=True)
    valor_unitario_comercial = db.Column(Numeric(15, 4), nullable=True)
    valor_total_produto = db.Column(Numeric(15, 2), nullable=True)
    
    # Tax quantities and values
    unidade_tributavel = db.Column(db.String(10), nullable=True)
    quantidade_tributavel = db.Column(Numeric(15, 4), nullable=True)
    valor_unitario_tributavel = db.Column(Numeric(15, 4), nullable=True)
    
    # Tax information
    origem_mercadoria = db.Column(db.String(5), nullable=True)
    situacao_tributaria_icms = db.Column(db.String(10), nullable=True)
    base_calculo_icms = db.Column(Numeric(15, 2), nullable=True)
    aliquota_icms = db.Column(Numeric(5, 2), nullable=True)
    valor_icms = db.Column(Numeric(15, 2), nullable=True)
    
    situacao_tributaria_ipi = db.Column(db.String(10), nullable=True)
    valor_ipi = db.Column(Numeric(15, 2), nullable=True)
    
    situacao_tributaria_pis = db.Column(db.String(10), nullable=True)
    base_calculo_pis = db.Column(Numeric(15, 2), nullable=True)
    aliquota_pis = db.Column(Numeric(5, 4), nullable=True)
    valor_pis = db.Column(Numeric(15, 2), nullable=True)
    
    situacao_tributaria_cofins = db.Column(db.String(10), nullable=True)
    base_calculo_cofins = db.Column(Numeric(15, 2), nullable=True)
    aliquota_cofins = db.Column(Numeric(5, 4), nullable=True)
    valor_cofins = db.Column(Numeric(15, 2), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.now)
