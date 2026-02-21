
import hashlib
from passlib.context import CryptContext

# 模拟 security.py 中的配置
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    sha256_bin = hashlib.sha256(password.encode('utf-8')).digest()
    print(f"SHA256 binary length: {len(sha256_bin)}")
    return pwd_context.hash(sha256_bin)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    sha256_bin = hashlib.sha256(plain_password.encode('utf-8')).digest()
    return pwd_context.verify(sha256_bin, hashed_password)

if __name__ == "__main__":
    test_pass = "very_long_password_that_might_exceed_normal_limits_if_not_hashed_properly_1234567890"
    print(f"Testing with password length: {len(test_pass)}")
    
    try:
        hashed = get_password_hash(test_pass)
        print(f"Hashed successfully: {hashed}")
        
        is_valid = verify_password(test_pass, hashed)
        print(f"Verification result: {is_valid}")
        
        assert is_valid == True
        print("Test passed!")
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()
