import base64
import hashlib
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from config import Config

# Fixed salt for offline LAN deterministic derivation across sessions
LAN_SALT = b"ASET-OfflineExamSalt2026"

def derive_fernet_key(passcode: str) -> bytes:
    """Derive a URL-safe base64-encoded 32-byte Fernet key from a string passcode."""
    if not passcode:
        passcode = Config.MASTER_ENCRYPTION_KEY
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=LAN_SALT,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(passcode.encode('utf-8')))
    return key

def encrypt_text(plaintext: str, passcode: str = None) -> str:
    """Encrypt a plaintext string using AES-256 Fernet."""
    if plaintext is None:
        return ""
    if not isinstance(plaintext, str):
        plaintext = str(plaintext)
    key = derive_fernet_key(passcode or Config.MASTER_ENCRYPTION_KEY)
    f = Fernet(key)
    encrypted_bytes = f.encrypt(plaintext.encode('utf-8'))
    return encrypted_bytes.decode('utf-8')

def decrypt_text(ciphertext: str, passcode: str = None) -> str:
    """Decrypt a ciphertext string back to plaintext. Fallback to raw text if not encrypted."""
    if not ciphertext:
        return ""
    try:
        key = derive_fernet_key(passcode or Config.MASTER_ENCRYPTION_KEY)
        f = Fernet(key)
        decrypted_bytes = f.decrypt(ciphertext.encode('utf-8'))
        return decrypted_bytes.decode('utf-8')
    except Exception:
        # If decryption fails (e.g. legacy plain text or wrong key), return text safely
        return ciphertext
