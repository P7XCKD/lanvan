from app.aes_utils import encrypt_bytes, decrypt_bytes

if __name__ == "__main__":
    sample = b"Hello AES encryption!"
    encrypted = encrypt_bytes(sample)
    decrypted = decrypt_bytes(encrypted)
    assert decrypted == sample
    print("AES encryption & decryption works!")
