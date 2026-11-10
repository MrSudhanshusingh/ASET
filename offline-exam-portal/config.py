import os
import secrets

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    MASTER_ENCRYPTION_KEY = os.environ.get('MASTER_ENCRYPTION_KEY') or 'ASET-Offline-Key-2026'
    
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or f"sqlite:///{os.path.join(BASE_DIR, 'exam_portal.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Uploads directory
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    FACE_UPLOADS = os.path.join(UPLOAD_FOLDER, 'faces')
    AUDIT_UPLOADS = os.path.join(UPLOAD_FOLDER, 'audit')
    
    # Anti-cheating configuration
    MAX_CHEAT_STRIKES = 3
    SESSION_TIMEOUT_MINUTES = 180
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
