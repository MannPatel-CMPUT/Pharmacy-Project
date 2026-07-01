"""Google OAuth 2.0 authentication router."""

import os
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from authlib.integrations.starlette_client import OAuth
from services import auth_service

router = APIRouter(prefix="/auth/google", tags=["google-auth"])

# REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
APP_URL = os.getenv("APP_URL", "http://localhost:8000")

if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
    print("⚠️  Google OAuth credentials not configured. Google Sign-in will not work.")
    print("   Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env file")

# Configure OAuth
oauth = OAuth()
oauth.register(
    name='google',
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)


@router.get("/login")
async def google_login(request: Request):
    """
    Initiate Google OAuth login.
    Redirects user to Google's OAuth consent screen.
    """
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Google OAuth not configured. Please contact administrator."
        )
    
    # REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    # Use the APP_URL from environment for the redirect
    redirect_uri = f"{APP_URL}/auth/google/callback"
    
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/callback")
async def google_callback(request: Request):
    """
    Google OAuth callback endpoint.
    Receives authorization code from Google, exchanges it for user info,
    creates/updates user account, and issues JWT token.
    """
    try:
        # Exchange authorization code for access token
        token = await oauth.google.authorize_access_token(request)
        
        # Get user info from Google
        user_info = token.get('userinfo')
        if not user_info:
            raise HTTPException(status_code=400, detail="Failed to get user info from Google")
        
        email = user_info.get('email')
        name = user_info.get('name', email.split('@')[0] if email else 'User')
        picture = user_info.get('picture')
        
        if not email:
            raise HTTPException(status_code=400, detail="Email not provided by Google")
        
        # Check if user exists
        existing_user = auth_service.find_user_by_email(email)
        
        if existing_user:
            # User exists - just log them in
            user = existing_user
        else:
            # Create new user account
            # Generate username from email
            base_username = email.split('@')[0].lower()
            username = base_username
            
            # Ensure username is unique
            counter = 1
            while auth_service.find_user_by_username(username):
                username = f"{base_username}{counter}"
                counter += 1
            
            try:
                user = auth_service.create_user(
                    username=username,
                    email=email,
                    phone="",  # Google doesn't provide phone
                    password="google_oauth_" + os.urandom(16).hex()  # Random password (won't be used)
                )
            except ValueError as e:
                # Should not happen since we checked, but just in case
                raise HTTPException(status_code=409, detail=str(e))
        
        # Create JWT token
        token = auth_service.create_token(int(user["id"]), user["username"])
        
        # Redirect to workspace with token in cookie
        response = RedirectResponse(url="/workspace")
        auth_service.set_auth_cookie(response, token)
        
        return response
        
    except Exception as e:
        print(f"Google OAuth error: {e}")
        # Redirect to login page with error
        return RedirectResponse(url="/login?error=oauth_failed")


@router.get("/status")
async def google_oauth_status():
    """Check if Google OAuth is configured."""
    return {
        "configured": bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET),
        "client_id": GOOGLE_CLIENT_ID[:20] + "..." if GOOGLE_CLIENT_ID else None
    }
