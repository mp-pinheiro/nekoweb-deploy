import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


def compute_md5(file_path):
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def encode_key(key):
    return base64.urlsafe_b64encode(key.encode())


def encrypt_data(data, key):
    encodded_key = encode_key(key)
    f = Fernet(encodded_key)
    return f.encrypt(data.encode())


def decrypt_data(encrypted_data, key):
    encodded_key = encode_key(key)
    f = Fernet(encodded_key)
    try:
        return f.decrypt(encrypted_data).decode()
    except InvalidToken:
        raise ValueError("Invalid encryption key. Please provide the correct key or do a fresh deployment.")
