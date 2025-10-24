import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from datetime import datetime, timezone, timedelta

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1) # needed for url_for to generate with https

# configure the database, relative to the app instance folder
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Maximum file size for uploads (50MB)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

# Upload folder configuration
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create upload directory if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# initialize the app with the extension, flask-sqlalchemy >= 3.0.x
db.init_app(app)

# Template filters for better formatting
@app.template_filter('currency')
def currency_filter(value):
    """Format number as Brazilian currency with thousands separator."""
    if value is None:
        return 'R$ 0,00'
    try:
        # Format with thousands separator and 2 decimal places
        return f"R$ {float(value):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    except (ValueError, TypeError):
        return 'R$ 0,00'

@app.template_filter('brazil_time')
def brazil_time_filter(utc_datetime):
    """Convert UTC datetime to Brazil time (GMT-3)."""
    if not utc_datetime:
        return 'N/A'
    try:
        # Create Brazil timezone (GMT-3)
        brazil_tz = timezone(timedelta(hours=-3))
        # Convert UTC to Brazil time
        if utc_datetime.tzinfo is None:
            utc_datetime = utc_datetime.replace(tzinfo=timezone.utc)
        brazil_time = utc_datetime.astimezone(brazil_tz)
        return brazil_time.strftime('%d/%m/%Y %H:%M')
    except Exception:
        return utc_datetime.strftime('%d/%m/%Y %H:%M') if utc_datetime else 'N/A'

@app.template_filter('brazilian_decimal')
def brazilian_decimal_filter(value):
    """Format decimal number with Brazilian decimal separator."""
    if value is None:
        return '0,00'
    try:
        # Format with 2 decimal places and replace . with ,
        return f"{float(value):.2f}".replace('.', ',')
    except (ValueError, TypeError):
        return '0,00'

def create_default_admin():
    """Create default admin user if it doesn't exist."""
    from models import User, UserRole
    import uuid
    
    try:
        # Check if admin already exists
        admin = User.query.filter_by(email='admin@admin.com').first()
        if admin:
            logging.info("Default admin user already exists")
            return
        
        # Create default admin
        admin = User(
            id=str(uuid.uuid4()),
            email='admin@admin.com',
            first_name='Administrador',
            last_name='Sistema',
            role=UserRole.ADMIN,
            auth_method='local',
            active=True
        )
        admin.set_password('admin123')
        
        db.session.add(admin)
        db.session.commit()
        logging.info("✅ Default admin user created (admin@admin.com / admin123)")
    except Exception as e:
        logging.error(f"Error creating default admin: {e}")
        db.session.rollback()

def init_database():
    """Initialize database tables safely."""
    try:
        with app.app_context():
            # Make sure to import the models here or their tables won't be created
            import models  # noqa: F401
            db.create_all()
            logging.info("Database tables created")
            
            # Create default admin user
            create_default_admin()
    except Exception as e:
        logging.warning(f"Could not initialize database on startup: {e}")
        logging.info("Database will be initialized on first request")
