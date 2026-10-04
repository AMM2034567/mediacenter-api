from typing import Optional
from fastapi import Security, HTTPException, status, Request
from fastapi.security import APIKeyHeader
from app.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False, description="安全访问凭证密钥")

async def verify_api_key(
    request: Request,
    header_key: Optional[str] = Security(api_key_header)
) -> str:
    """
    Validates API key from either:
    1. Header: X-API-Key: your_key
    2. Header: Authorization: Bearer your_key
    3. Query parameter: ?api_key=your_key (convenient for browser tests)
    """
    provided_key = header_key
    
    # Check Authorization header (Bearer token)
    if not provided_key:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            provided_key = auth_header[7:].strip()
            
    # Check query param
    if not provided_key:
        provided_key = request.query_params.get("api_key")
        
    # Allow Vercel automated Cron jobs
    if request.headers.get("x-vercel-cron"):
        return "vercel-cron"
        
    if not provided_key or provided_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Invalid or missing API Key. Please provide valid 'X-API-Key' header.",
            headers={"WWW-Authenticate": "ApiKey"}
        )
        
    return provided_key
