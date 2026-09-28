from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()

def hash_password(password: str) -> str:
    """
    Hashes a password using the recommended hashing algorithm.
    """
    hashed_password = password_hash.hash(password)
    return hashed_password

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a password against a hashed password.
    """
    return password_hash.verify(plain_password, hashed_password)