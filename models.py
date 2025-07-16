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
    file_type = db.Column(db.String(10), nullable=False, default='xml')  # 'xml' or 'pdf'
    status = db.Column(db.Enum(ProcessingStatus), default=ProcessingStatus.PENDING)
    error_message = db.Column(db.Text, nullable=True)
    processing_started_at = db.Column(db.DateTime, nullable=True)
    processing_completed_at = db.Column(db.DateTime, nullable=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batches.id'), nullable=True)  # Link to batch
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

class NFERecord(db.Model):
    __tablename__ = 'nfe_records'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    uploaded_file_id = db.Column(db.Integer, db.ForeignKey('uploaded_files.id'), nullable=False)
    batch_id = db.Column(db.Integer, db.ForeignKey('batches.id'), nullable=True)  # Link to batch
    
    # Identification fields
    chave_nfe = db.Column(db.String(44), nullable=True)  # NFe key
    numero_nf = db.Column(db.String(20), nullable=True)
    serie = db.Column(db.String(10), nullable=True)
    modelo = db.Column(db.String(100), nullable=True)  # Increased from 5 to 100
    data_emissao = db.Column(db.DateTime, nullable=True)
    data_saida_entrada = db.Column(db.DateTime, nullable=True)
    tipo_operacao = db.Column(db.String(50), nullable=True)  # Increased from 10 to 50
    natureza_operacao = db.Column(db.String(200), nullable=True)  # Changed from Text to String(200)
    
    # Emitente fields
    emitente_cnpj = db.Column(db.String(18), nullable=True)
    emitente_nome = db.Column(db.String(255), nullable=True)
    emitente_fantasia = db.Column(db.String(255), nullable=True)
    emitente_ie = db.Column(db.String(20), nullable=True)
    emitente_im = db.Column(db.String(20), nullable=True)  # Inscrição Municipal
    emitente_endereco = db.Column(db.Text, nullable=True)
    emitente_municipio = db.Column(db.String(100), nullable=True)
    emitente_uf = db.Column(db.String(2), nullable=True)
    emitente_cep = db.Column(db.String(10), nullable=True)
    
    # Destinatário fields
    destinatario_cnpj = db.Column(db.String(18), nullable=True)
    destinatario_nome = db.Column(db.String(255), nullable=True)
    destinatario_ie = db.Column(db.String(20), nullable=True)
    destinatario_im = db.Column(db.String(20), nullable=True)  # Inscrição Municipal
    destinatario_endereco = db.Column(db.Text, nullable=True)
    destinatario_municipio = db.Column(db.String(100), nullable=True)
    destinatario_uf = db.Column(db.String(2), nullable=True)
    destinatario_cep = db.Column(db.String(10), nullable=True)
    
    # Valores totais
    valor_total_produtos = db.Column(Numeric(15, 2), nullable=True)
    valor_total_servicos = db.Column(Numeric(15, 2), nullable=True)
    valor_total_nf = db.Column(Numeric(15, 2), nullable=True)
    valor_icms = db.Column(Numeric(15, 2), nullable=True)
    valor_ipi = db.Column(Numeric(15, 2), nullable=True)
    valor_pis = db.Column(Numeric(15, 2), nullable=True)
    valor_cofins = db.Column(Numeric(15, 2), nullable=True)
    valor_issqn = db.Column(Numeric(15, 2), nullable=True)
    valor_issrf = db.Column(Numeric(15, 2), nullable=True)  # ISS Retido na Fonte
    valor_ir = db.Column(Numeric(15, 2), nullable=True)
    valor_inss = db.Column(Numeric(15, 2), nullable=True)
    valor_csll = db.Column(Numeric(15, 2), nullable=True)
    valor_iss_retido = db.Column(Numeric(15, 2), nullable=True)
    valor_frete = db.Column(Numeric(15, 2), nullable=True)
    valor_seguro = db.Column(Numeric(15, 2), nullable=True)
    valor_desconto = db.Column(Numeric(15, 2), nullable=True)
    valor_tributos = db.Column(Numeric(15, 2), nullable=True)
    
    # Transport and payment info
    modalidade_frete = db.Column(db.String(50), nullable=True)
    transportadora_cnpj = db.Column(db.String(18), nullable=True)
    transportadora_nome = db.Column(db.String(255), nullable=True)
    forma_pagamento = db.Column(db.String(150), nullable=True)  # Increased from 100 to 150
    data_vencimento = db.Column(db.DateTime, nullable=True)  # Payment due date
    
    # Protocol and status
    protocolo_autorizacao = db.Column(db.String(100), nullable=True)  # Increased from 50 to 100
    status_autorizacao = db.Column(db.String(50), nullable=True)  # Increased from 20 to 50
    ambiente = db.Column(db.String(50), nullable=True)  # Increased from 20 to 50
    
    # Additional information fields
    informacoes_adicionais = db.Column(db.Text, nullable=True)  # Campo de informações adicionais da NFe
    tipo_documento = db.Column(db.String(20), nullable=True)  # produto, servico, misto
    
    # AI processing metadata
    ai_confidence_score = db.Column(db.Float, nullable=True)
    ai_processing_notes = db.Column(db.Text, nullable=True)
    raw_xml_data = db.Column(db.Text, nullable=True)  # Store original XML for reference
    
    # Original PDF file path (for PDF uploads)
    original_pdf_path = db.Column(db.String(500), nullable=True)
    original_pdf_filename = db.Column(db.String(255), nullable=True)
    
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
    codigo_servico = db.Column(db.String(10), nullable=True)  # Service code (XX.XX format)
    codigo_atividade = db.Column(db.String(20), nullable=True)  # Activity code/CNAE
    descricao_produto = db.Column(db.Text, nullable=True)
    descricao_servico = db.Column(db.Text, nullable=True)  # Service description
    ncm = db.Column(db.String(20), nullable=True)
    cfop = db.Column(db.String(10), nullable=True)
    
    # Service-specific fields from detailed view
    servico_codigo = db.Column(db.String(10), nullable=True)  # Código do serviço (3301)
    servico_local_prestacao = db.Column(db.String(10), nullable=True)  # Local de prestação (7435)
    servico_aliquota = db.Column(Numeric(5, 2), nullable=True)  # Alíquota (2%)
    servico_valor = db.Column(Numeric(15, 2), nullable=True)  # Valor do serviço
    servico_descricao_incondicional = db.Column(Numeric(15, 2), nullable=True)  # Desc. Incondicional
    servico_valor_deducao = db.Column(Numeric(15, 2), nullable=True)  # Valor dedução
    servico_valor_iss = db.Column(Numeric(15, 2), nullable=True)  # Valor ISS
    servico_natureza_operacao = db.Column(db.String(255), nullable=True)  # Natureza da operação
    servico_discriminacao = db.Column(db.Text, nullable=True)  # Discriminação dos serviços
    
    # Tax details from the detailed breakdown
    tax_ir = db.Column(Numeric(15, 2), nullable=True)  # IR
    tax_inss = db.Column(Numeric(15, 2), nullable=True)  # INSS  
    tax_csll = db.Column(Numeric(15, 2), nullable=True)  # CSLL
    tax_cofins = db.Column(Numeric(15, 2), nullable=True)  # COFINS
    tax_pis = db.Column(Numeric(15, 2), nullable=True)  # PIS
    tax_outras_retencoes = db.Column(Numeric(15, 2), nullable=True)  # Outras Retenções
    tax_total_tributos_federais = db.Column(Numeric(15, 2), nullable=True)  # Total Trib. Federais
    tax_descricao_condicional = db.Column(Numeric(15, 2), nullable=True)  # Desc. Condicional
    tax_base_calculo = db.Column(Numeric(15, 2), nullable=True)  # Base de Cálculo
    tax_issqn = db.Column(Numeric(15, 2), nullable=True)  # ISSQN
    tax_valor_liquido = db.Column(Numeric(15, 2), nullable=True)  # Valor Líquido
    
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
    
    # Service taxes
    situacao_tributaria_issqn = db.Column(db.String(10), nullable=True)
    base_calculo_issqn = db.Column(Numeric(15, 2), nullable=True)
    aliquota_issqn = db.Column(Numeric(5, 4), nullable=True)
    valor_issqn = db.Column(Numeric(15, 2), nullable=True)
    
    # Income tax withheld
    base_calculo_ir = db.Column(Numeric(15, 2), nullable=True)
    aliquota_ir = db.Column(Numeric(5, 4), nullable=True)
    valor_ir = db.Column(Numeric(15, 2), nullable=True)
    
    # ISS withheld at source
    base_calculo_iss_retido = db.Column(Numeric(15, 2), nullable=True)
    aliquota_iss_retido = db.Column(Numeric(5, 4), nullable=True)
    valor_iss_retido = db.Column(Numeric(15, 2), nullable=True)
    
    # Additional municipal/federal taxes
    situacao_tributaria_issrf = db.Column(db.String(10), nullable=True)
    base_calculo_issrf = db.Column(Numeric(15, 2), nullable=True)
    aliquota_issrf = db.Column(Numeric(5, 4), nullable=True)
    valor_issrf = db.Column(Numeric(15, 2), nullable=True)
    
    situacao_tributaria_inss = db.Column(db.String(10), nullable=True)
    base_calculo_inss = db.Column(Numeric(15, 2), nullable=True)
    aliquota_inss = db.Column(Numeric(5, 4), nullable=True)
    valor_inss = db.Column(Numeric(15, 2), nullable=True)
    
    situacao_tributaria_csll = db.Column(db.String(10), nullable=True)
    base_calculo_csll = db.Column(Numeric(15, 2), nullable=True)
    aliquota_csll = db.Column(Numeric(5, 4), nullable=True)
    valor_csll = db.Column(Numeric(15, 2), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.now)


class BatchStatus(enum.Enum):
    """Status of a batch/contract"""
    OPEN = "open"           # Batch is open for adding files
    PROCESSING = "processing"  # Files are being processed
    COMPLETED = "completed"    # All files processed
    CLOSED = "closed"         # Batch closed for editing


class Batch(db.Model):
    """Model for grouping NFe documents into batches/contracts"""
    __tablename__ = 'batches'
    
    id = db.Column(db.Integer, primary_key=True)
    nome_contrato = db.Column(db.String(255), nullable=False)     # Contract/process name
    nome_item = db.Column(db.String(255), nullable=False)         # Item name (for RM system)
    unidade_negocio = db.Column(db.String(100), nullable=False)   # Business unit
    centro_custo = db.Column(db.String(50), nullable=False)       # Cost center
    
    # Status and metadata
    status = db.Column(db.Enum(BatchStatus), nullable=False, default=BatchStatus.OPEN)
    descricao = db.Column(db.Text)                                # Optional description
    
    # Ownership and tracking
    created_by = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    closed_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    creator = db.relationship('User', backref='created_batches')
    files = db.relationship('UploadedFile', backref='batch', lazy='dynamic')
    nfe_records = db.relationship('NFERecord', backref='batch', lazy='dynamic')
    
    def __repr__(self):
        return f'<Batch {self.nome_contrato}>'
    
    @property
    def total_files(self):
        """Total number of files in this batch"""
        return self.files.count()
    
    @property
    def processed_files(self):
        """Number of successfully processed files"""
        return self.files.filter_by(status=ProcessingStatus.COMPLETED).count()
    
    @property
    def pending_files(self):
        """Number of files pending processing"""
        return self.files.filter(UploadedFile.status.in_([ProcessingStatus.PENDING, ProcessingStatus.PROCESSING])).count()
    
    @property
    def failed_files(self):
        """Number of files that failed processing"""
        return self.files.filter_by(status=ProcessingStatus.ERROR).count()
    
    @property
    def progress_percentage(self):
        """Processing progress as percentage"""
        if self.total_files == 0:
            return 0
        return (self.processed_files / self.total_files) * 100
    
    @property
    def total_value(self):
        """Total value of all NFe records in this batch"""
        total = db.session.query(db.func.sum(NFERecord.valor_total_servicos)).filter(
            NFERecord.batch_id == self.id
        ).scalar()
        return total or 0
    
    def can_be_edited(self):
        """Check if batch can still be edited"""
        return self.status in [BatchStatus.OPEN, BatchStatus.PROCESSING]
    
    def close_batch(self):
        """Close the batch for editing"""
        self.status = BatchStatus.CLOSED
        self.closed_at = datetime.now()
        db.session.commit()


class Empresa(db.Model):
    """Modelo para gerenciar empresas cadastradas pelo usuário"""
    __tablename__ = 'empresas'
    
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.Integer, nullable=False)
    nome_fantasia = db.Column(db.String(255), nullable=False)
    cnpj = db.Column(db.String(18), nullable=False, unique=True)
    razao_social = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relacionamento com usuário
    user = db.relationship('User', backref='empresas')
    
    # Relacionamento com filiais
    filiais = db.relationship('Filial', backref='empresa', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Empresa {self.numero}: {self.nome_fantasia}>'
    
    @property
    def cnpj_formatado(self):
        """Retorna CNPJ formatado XX.XXX.XXX/XXXX-XX"""
        if len(self.cnpj) == 14:
            return f"{self.cnpj[:2]}.{self.cnpj[2:5]}.{self.cnpj[5:8]}/{self.cnpj[8:12]}-{self.cnpj[12:]}"
        return self.cnpj
    
    @property
    def total_filiais(self):
        """Total de filiais cadastradas para esta empresa"""
        return self.filiais.count()


class Filial(db.Model):
    """Modelo para gerenciar filiais vinculadas às empresas"""
    __tablename__ = 'filiais'
    
    id = db.Column(db.Integer, primary_key=True)
    coligada = db.Column(db.Integer, nullable=False)  # Numero da empresa (FK)
    nome_coligada = db.Column(db.String(255), nullable=False)
    cnpj_coligada = db.Column(db.String(18), nullable=False)
    filial = db.Column(db.String(10), nullable=False)  # Codigo da filial
    nome_filial = db.Column(db.String(255), nullable=False)
    cnpj_filial = db.Column(db.String(18), nullable=False)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relacionamento com empresa (via numero)
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresas.id'), nullable=False)
    
    # Relacionamento com usuário
    user = db.relationship('User', backref='filiais')
    
    # Constraint para garantir que coligada + filial seja único por usuário
    __table_args__ = (UniqueConstraint('coligada', 'filial', 'user_id', name='uq_filial_user'),)
    
    def __repr__(self):
        return f'<Filial {self.coligada}-{self.filial}: {self.nome_filial}>'
    
    @property
    def cnpj_coligada_formatado(self):
        """Retorna CNPJ da coligada formatado XX.XXX.XXX/XXXX-XX"""
        if len(self.cnpj_coligada) == 14:
            return f"{self.cnpj_coligada[:2]}.{self.cnpj_coligada[2:5]}.{self.cnpj_coligada[5:8]}/{self.cnpj_coligada[8:12]}-{self.cnpj_coligada[12:]}"
        return self.cnpj_coligada
    
    @property
    def cnpj_filial_formatado(self):
        """Retorna CNPJ da filial formatado XX.XXX.XXX/XXXX-XX"""
        if len(self.cnpj_filial) == 14:
            return f"{self.cnpj_filial[:2]}.{self.cnpj_filial[2:5]}.{self.cnpj_filial[5:8]}/{self.cnpj_filial[8:12]}-{self.cnpj_filial[12:]}"
        return self.cnpj_filial


class UserSettings(db.Model):
    """Modelo para configurações do usuário"""
    __tablename__ = 'user_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False, unique=True)
    
    # API Keys e Configurações
    openai_api_key = db.Column(db.Text, nullable=True)
    consumer_key = db.Column(db.Text, nullable=True)
    consumer_secret = db.Column(db.Text, nullable=True)
    token_key = db.Column(db.Text, nullable=True)
    token_secret = db.Column(db.Text, nullable=True)
    fluig_url = db.Column(db.String(500), nullable=True)
    ged_folder_id = db.Column(db.String(100), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relacionamento com usuário
    user = db.relationship('User', backref='settings')
    
    def __repr__(self):
        return f'<UserSettings {self.user_id}>'
    
    @property
    def has_openai_key(self):
        """Verifica se tem OpenAI API Key configurada"""
        return bool(self.openai_api_key and self.openai_api_key.strip())
    
    @property
    def has_twitter_config(self):
        """Verifica se tem configuração Twitter/X completa"""
        return all([
            self.consumer_key and self.consumer_key.strip(),
            self.consumer_secret and self.consumer_secret.strip(),
            self.token_key and self.token_key.strip(),
            self.token_secret and self.token_secret.strip()
        ])
    
    @property
    def has_fluig_config(self):
        """Verifica se tem configuração Fluig completa"""
        return all([
            self.fluig_url and self.fluig_url.strip(),
            self.ged_folder_id and self.ged_folder_id.strip()
        ])
    
    @classmethod
    def get_or_create_for_user(cls, user_id):
        """Busca ou cria configurações para o usuário"""
        settings = cls.query.filter_by(user_id=user_id).first()
        if not settings:
            settings = cls(user_id=user_id)
            db.session.add(settings)
            db.session.commit()
        return settings
