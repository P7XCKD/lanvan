from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

AES_KEY = bytes.fromhex("8f9c02a7d6f7cbb1da0499e18b113fe65c7a6d2f538b0a6412ccab5ede6b8839")
AES_IV  = bytes.fromhex("f012bc7d298e34af6509cb471d3a8250")

def pad(data: bytes) -> bytes:
    padding_len = 16 - (len(data) % 16)
    return data + bytes([padding_len] * padding_len)

def unpad(data: bytes) -> bytes:
    padding_len = data[-1]
    return data[:-padding_len]

def encrypt_bytes(data: bytes) -> bytes:
    cipher = Cipher(algorithms.AES(AES_KEY), modes.CBC(AES_IV), backend=default_backend())
    encryptor = cipher.encryptor()
    padded = pad(data)
    encrypted = encryptor.update(padded) + encryptor.finalize()
    return encrypted

def decrypt_bytes(data: bytes) -> bytes:
    cipher = Cipher(algorithms.AES(AES_KEY), modes.CBC(AES_IV), backend=default_backend())
    decryptor = cipher.decryptor()
    decrypted_padded = decryptor.update(data) + decryptor.finalize()
    decrypted = unpad(decrypted_padded)
    return decrypted
