"""
JWT Token Service
==================
Handles JWT token generation, validation, and refresh for secure authentication.

Token Types:
1. Access Token: Short-lived (15 minutes), used for API authentication
2. Refresh Token: Long-lived (7 days), used to obtain new access tokens

Security Features:
- HS256 algorithm with secret key
- Token expiration validation
- Payload validation
- Optional token blacklist support
"""
import os
import jwt
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class TokenPayload(BaseModel):
    """JWT token payload schema"""
    sub: str  # Subject (username)
    exp: int  # Expiration timestamp
    iat: int  # Issued at timestamp
    type: str  # Token type: 'access' or 'refresh'
    store: Optional[str] = None  # Bringo store


class TokenPair(BaseModel):
    """Access and refresh token pair"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # Seconds until access token expires


class TokenService:
    """JWT token generation and validation service"""
    
    def __init__(
        self,
        secret_key: Optional[str] = None,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 15,
        refresh_token_expire_days: int = 7
    ):
        """
        Initialize token service
        
        Args:
            secret_key: Secret key for signing tokens (from env or Secret Manager)
            algorithm: JWT signing algorithm (default: HS256)
            access_token_expire_minutes: Access token expiry in minutes
            refresh_token_expire_days: Refresh token expiry in days
        """
        self.secret_key = secret_key or self._get_jwt_secret()
        self.algorithm = algorithm
        self.access_token_expire_minutes = access_token_expire_minutes
        self.refresh_token_expire_days = refresh_token_expire_days
        
        # Validate secret key
        if not self.secret_key or len(self.secret_key) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters")
    
    def _get_jwt_secret(self) -> str:
        """
        Get JWT secret key from environment or Secret Manager
        
        Returns:
            JWT secret key
            
        Raises:
            ValueError: If secret key not found or too weak
        """
        # Try Secret Manager first
        try:
            from config.secrets import _secret_manager
            secret = _secret_manager.get_secret("jwt-secret-key")
            if secret:
                return secret
        except Exception as e:
            logger.debug(f"Secret Manager not available for JWT secret: {e}")
        
        # Fallback to environment variable
        secret = os.getenv("JWT_SECRET_KEY")
        if not secret:
            raise ValueError(
                "JWT_SECRET_KEY not found. "
                "Set in environment or create 'jwt-secret-key' in Secret Manager. "
                "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )
        
        return secret
    
    def create_access_token(
        self,
        username: str,
        store: Optional[str] = None,
        additional_claims: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create JWT access token
        
        Args:
            username: Username (subject)
            store: Bringo store (optional)
            additional_claims: Additional JWT claims (optional)
            
        Returns:
            Encoded JWT access token
        """
        now = datetime.utcnow()
        expires = now + timedelta(minutes=self.access_token_expire_minutes)
        
        payload = {
            "sub": username,
            "exp": int(expires.timestamp()),
            "iat": int(now.timestamp()),
            "type": "access",
        }
        
        if store:
            payload["store"] = store
        
        if additional_claims:
            payload.update(additional_claims)
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        logger.info(f"✅ Created access token for user: {username}")
        
        return token
    
    def create_refresh_token(
        self,
        username: str,
        store: Optional[str] = None
    ) -> str:
        """
        Create JWT refresh token
        
        Args:
            username: Username (subject)
            store: Bringo store (optional)
            
        Returns:
            Encoded JWT refresh token
        """
        now = datetime.utcnow()
        expires = now + timedelta(days=self.refresh_token_expire_days)
        
        payload = {
            "sub": username,
            "exp": int(expires.timestamp()),
            "iat": int(now.timestamp()),
            "type": "refresh",
        }
        
        if store:
            payload["store"] = store
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        logger.info(f"✅ Created refresh token for user: {username}")
        
        return token
    
    def create_token_pair(
        self,
        username: str,
        store: Optional[str] = None
    ) -> TokenPair:
        """
        Create access and refresh token pair
        
        Args:
            username: Username
            store: Bringo store
            
        Returns:
            TokenPair with both tokens
        """
        access_token = self.create_access_token(username, store)
        refresh_token = self.create_refresh_token(username, store)
        
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self.access_token_expire_minutes * 60
        )
    
    def decode_token(self, token: str) -> TokenPayload:
        """
        Decode and validate JWT token
        
        Args:
            token: Encoded JWT token
            
        Returns:
            TokenPayload with validated claims
            
        Raises:
            jwt.ExpiredSignatureError: If token is expired
            jwt.InvalidTokenError: If token is invalid
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            
            return TokenPayload(**payload)
            
        except jwt.ExpiredSignatureError:
            logger.warning("⚠️  Token expired")
            raise
        except jwt.InvalidTokenError as e:
            logger.error(f"❌ Invalid token: {e}")
            raise
    
    def verify_access_token(self, token: str) -> TokenPayload:
        """
        Verify access token and return payload
        
        Args:
            token: Access token
            
        Returns:
            TokenPayload
            
        Raises:
            ValueError: If token type is not 'access'
            jwt.ExpiredSignatureError: If token is expired
            jwt.InvalidTokenError: If token is invalid
        """
        payload = self.decode_token(token)
        
        if payload.type != "access":
            raise ValueError(f"Expected access token, got {payload.type}")
        
        return payload
    
    def verify_refresh_token(self, token: str) -> TokenPayload:
        """
        Verify refresh token and return payload
        
        Args:
            token: Refresh token
            
        Returns:
            TokenPayload
            
        Raises:
            ValueError: If token type is not 'refresh'
            jwt.ExpiredSignatureError: If token is expired
            jwt.InvalidTokenError: If token is invalid
        """
        payload = self.decode_token(token)
        
        if payload.type != "refresh":
            raise ValueError(f"Expected refresh token, got {payload.type}")
        
        return payload
    
    def refresh_access_token(self, refresh_token: str) -> str:
        """
        Generate new access token from valid refresh token
        
        Args:
            refresh_token: Valid refresh token
            
        Returns:
            New access token
            
        Raises:
            jwt.ExpiredSignatureError: If refresh token is expired
            jwt.InvalidTokenError: If refresh token is invalid
        """
        payload = self.verify_refresh_token(refresh_token)
        
        # Create new access token with same claims
        new_access_token = self.create_access_token(
            username=payload.sub,
            store=payload.store
        )
        
        logger.info(f"🔄 Refreshed access token for user: {payload.sub}")
        
        return new_access_token


# Global token service instance
_token_service: Optional[TokenService] = None

def get_token_service() -> TokenService:
    """Get or create global token service instance"""
    global _token_service
    if _token_service is None:
        _token_service = TokenService()
    return _token_service
