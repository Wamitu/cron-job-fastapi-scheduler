import secrets
from log_config import logger


def generate_invite_token():
    """
    Generate a secure, URL-safe token for user invitations.

    Returns:
        str: A securely generated random token (Base64 URL-safe, 32 bytes of entropy)
    """
    # Generate a random token using the secrets module (secure for cryptographic use)
    token = secrets.token_urlsafe(32)

    # Log token creation event (avoid logging actual token for security reasons)
    logger.info("Invite token generated successfully.")

    return token
