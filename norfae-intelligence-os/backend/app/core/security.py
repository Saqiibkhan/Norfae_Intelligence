import bcrypt

MIN_PASSWORD_LENGTH = 12
MAX_BCRYPT_PASSWORD_BYTES = 72


class PasswordValidationError(ValueError):
    """Raised when a new password does not meet the configured policy."""


class SecurityManager:

    # ===================================
    # HASH PASSWORD
    # ===================================

    @staticmethod
    def validate_password(password: str) -> str:
        if not isinstance(password, str):
            raise PasswordValidationError("Password must be a string.")
        if len(password) < MIN_PASSWORD_LENGTH:
            raise PasswordValidationError(
                f"Password must contain at least {MIN_PASSWORD_LENGTH} characters."
            )
        try:
            encoded_password = password.encode("utf-8")
        except UnicodeEncodeError:
            raise PasswordValidationError("Password contains invalid characters.") from None
        if len(encoded_password) > MAX_BCRYPT_PASSWORD_BYTES:
            raise PasswordValidationError(
                "Password must not exceed 72 UTF-8 bytes when using bcrypt."
            )
        return password

    @staticmethod
    def hash_password(password: str) -> str:
        validated_password = SecurityManager.validate_password(password)
        return bcrypt.hashpw(
            validated_password.encode("utf-8"), bcrypt.gensalt()
        ).decode("ascii")

    # ===================================
    # VERIFY PASSWORD
    # ===================================

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        if not isinstance(plain_password, str) or not isinstance(hashed_password, str):
            return False
        try:
            password_bytes = plain_password.encode("utf-8")
            if not password_bytes or len(password_bytes) > MAX_BCRYPT_PASSWORD_BYTES:
                return False
            return bcrypt.checkpw(password_bytes, hashed_password.encode("ascii"))
        except (UnicodeEncodeError, ValueError, TypeError):
            return False
