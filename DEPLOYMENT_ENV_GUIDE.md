# Environment Variables Setup for Production Deployment

## Overview
This application requires environment variables to be set in your hosting platform (Render, Vercel, Railway, etc.) for production deployment.

## Required Environment Variables

### 1. Google OAuth Configuration
Set these in your hosting platform's environment variables panel:

```
GOOGLE_CLIENT_ID=<your-google-client-id>
GOOGLE_CLIENT_SECRET=<your-google-client-secret>
```

**Where to get these:**
1. Go to Google Cloud Console: https://console.cloud.google.com/apis/credentials
2. Create or select an OAuth 2.0 Client ID
3. Copy the Client ID and Client Secret values

### 2. Application URLs

```
APP_URL=<your-production-url>
FRONTEND_URL=<comma-separated-list-of-allowed-origins>
```

**Example:**
```
APP_URL=https://your-app.onrender.com
FRONTEND_URL=http://localhost:3000,https://your-app.onrender.com
```

### 3. JWT Secret (Important for Security)

```
JWT_SECRET=<generate-a-random-secret-key>
```

**Generate a secure secret:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 4. Database Configuration

```
DATABASE_URL=<your-database-url>
PORTAL_USERS_PATH=/app/fastapi/data/portal_users.json
```

## How to Set Environment Variables

### On Render:
1. Go to your service dashboard
2. Click "Environment" in the left sidebar
3. Click "Add Environment Variable"
4. Enter key and value
5. Click "Save Changes"
6. Redeploy your service

### On Vercel:
1. Go to your project settings
2. Click "Environment Variables"
3. Add each variable
4. Redeploy

### On Railway:
1. Go to your project
2. Click "Variables"
3. Add each variable
4. Railway auto-deploys

## Google OAuth Setup

After setting environment variables, configure your OAuth client:

1. Go to Google Cloud Console
2. Edit your OAuth 2.0 Client ID
3. Add **Authorized JavaScript origins:**
   - Your production URL (e.g., https://your-app.onrender.com)
   - http://localhost:3000 (for local testing)

4. Add **Authorized redirect URIs:**
   - https://your-app.onrender.com/auth/google/callback
   - http://localhost:3000/auth/google/callback

5. Click "Save"

## Security Best Practices

✅ Never commit actual credentials to Git
✅ Use different secrets for dev/staging/production
✅ Rotate secrets regularly
✅ Store secrets only in hosting platform's environment variables
✅ Use `.env.example` for documentation, not `.env`

## Verification

After deployment, verify OAuth is configured:
```
curl https://your-app.onrender.com/auth/google/status
```

Should return:
```json
{
  "configured": true,
  "client_id": "your-client-id..."
}
```

## Need Help?

- Google OAuth docs: https://developers.google.com/identity/protocols/oauth2
- Render environment variables: https://render.com/docs/environment-variables
- See `.env.example` file for template

## Important Files

- `.env.example` - Template with placeholders (safe to commit)
- `.env` - Your actual values (git-ignored, never commit)
- Local credentials stored in your git-ignored files only

Your actual credential values should be noted separately and added to your hosting platform's environment variables panel.
