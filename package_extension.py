#!/usr/bin/env python3
"""
Package the Chrome extension as a .crx file.
Generates a signing key, creates the .crx, and saves it to webapp/static/
"""
import os
import json
import hashlib
import struct
import zipfile
import shutil
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

# Paths
EXTENSION_DIR = Path(__file__).parent / "chrome_extension"
WEBAPP_DIR = Path(__file__).parent / "webapp"
STATIC_DIR = WEBAPP_DIR / "static"
KEY_FILE = STATIC_DIR / "extension_key.pem"
CRX_FILE = STATIC_DIR / "linkedin_autoapply.crx"
TEMP_ZIP = STATIC_DIR / ".extension.zip"

def generate_key():
    """Generate RSA key pair for signing."""
    if KEY_FILE.exists():
        print(f"Using existing key: {KEY_FILE}")
        return
    
    print("Generating RSA key pair...")
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    KEY_FILE.write_bytes(pem)
    print(f"Key saved: {KEY_FILE}")

def create_crx():
    """Create .crx file from extension folder."""
    print(f"Creating .crx from {EXTENSION_DIR}...")
    
    # Create temp ZIP
    if TEMP_ZIP.exists():
        TEMP_ZIP.unlink()
    
    with zipfile.ZipFile(TEMP_ZIP, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(EXTENSION_DIR):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(EXTENSION_DIR)
                zf.write(file_path, arcname=arcname)
    
    zip_data = TEMP_ZIP.read_bytes()
    
    # Load private key and extract public key
    with open(KEY_FILE, 'rb') as f:
        private_key = serialization.load_pem_private_key(
            f.read(),
            password=None,
            backend=default_backend()
        )
    
    public_key_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    # Sign the ZIP data
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    signature = private_key.sign(
        zip_data,
        padding.PKCS1v15(),
        hashes.SHA256()
    )
    
    # Build .crx file: magic + version + pubkey_len + sig_len + pubkey + sig + zip
    crx = b"Cr24"  # Magic number for CRX3
    crx += struct.pack("<I", 3)  # Version 3
    crx += struct.pack("<I", len(public_key_pem))
    crx += struct.pack("<I", len(signature))
    crx += public_key_pem
    crx += signature
    crx += zip_data
    
    # Write .crx file
    STATIC_DIR.mkdir(exist_ok=True)
    CRX_FILE.write_bytes(crx)
    TEMP_ZIP.unlink()
    
    print(f"✓ Extension packaged: {CRX_FILE}")
    print(f"  Size: {len(crx) / 1024:.1f} KB")

if __name__ == "__main__":
    try:
        generate_key()
        create_crx()
        print("\n✓ Done! Users can now download from: /static/linkedin_autoapply.crx")
    except ImportError:
        print("ERROR: cryptography module not found. Install with:")
        print("  pip install cryptography")
        exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        exit(1)
