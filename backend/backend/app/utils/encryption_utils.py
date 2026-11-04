from cryptography.fernet import Fernet
from app.config import settings

def get_fernet() -> Fernet:
    """Returns a Fernet instance using the configured encryption key."""
    # Ensure the key is bytes
    key = settings.FILE_ENCRYPTION_KEY.encode('utf-8')
    return Fernet(key)

def encrypt_file(data: bytes) -> bytes:
    """Encrypts raw bytes using Fernet."""
    f = get_fernet()
    return f.encrypt(data)

def decrypt_file(data: bytes) -> bytes:
    """Decrypts Fernet-encrypted bytes."""
    f = get_fernet()
    return f.decrypt(data)

import io

def is_pdf_encrypted(file_bytes: bytes) -> bool:
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(file_bytes))
        return reader.is_encrypted
    except Exception:
        return False

def decrypt_pdf(file_bytes: bytes, password: str) -> bytes:
    from PyPDF2 import PdfReader, PdfWriter
    reader = PdfReader(io.BytesIO(file_bytes))
    
    if not reader.is_encrypted:
        return file_bytes
        
    reader.decrypt(password)
    writer = PdfWriter()
    
    for page in reader.pages:
        writer.add_page(page)
        
    out_stream = io.BytesIO()
    writer.write(out_stream)
    return out_stream.getvalue()

def is_docx_encrypted(file_bytes: bytes) -> bool:
    try:
        import msoffcrypto
        office_file = msoffcrypto.OfficeFile(io.BytesIO(file_bytes))
        return office_file.is_encrypted()
    except Exception:
        return False

def decrypt_docx(file_bytes: bytes, password: str) -> bytes:
    import msoffcrypto
    office_file = msoffcrypto.OfficeFile(io.BytesIO(file_bytes))
    
    if not office_file.is_encrypted():
        return file_bytes
        
    office_file.load_key(password=password)
    out_stream = io.BytesIO()
    office_file.decrypt(out_stream)
    return out_stream.getvalue()
