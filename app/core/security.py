from functools import wraps
from fastapi import HTTPException, Request
from firebase_admin import auth
import logging

logger = logging.getLogger(__name__)


def get_firebase_app():
    """Get an available Firebase app for authentication"""
    import firebase_admin
    
    try:
        # Try to get the firestore manager's app first
        from app.db.firestore import firestore_manager
        if firestore_manager.app_name:
            try:
                return firebase_admin.get_app(firestore_manager.app_name)
            except ValueError:
                pass
    except Exception:
        pass
    
    # Fallback: get any available Firebase app
    try:
        apps = firebase_admin._apps
        if apps:
            return list(apps.values())[0]
    except Exception:
        pass
    
    return None


def auth_required():
    """Decorator that validates Firebase token and provides user_id"""
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            # Get token from Authorization header
            auth_header = request.headers.get("Authorization")
            if not auth_header:
                raise HTTPException(status_code=401, detail="No authorization header")

            try:
                # Extract token
                scheme, token = auth_header.split()
                if scheme.lower() != "bearer":
                    raise HTTPException(status_code=401, detail="Invalid authentication scheme")

                # Get Firebase app
                firebase_app = get_firebase_app()
                if not firebase_app:
                    raise HTTPException(status_code=500, detail="No Firebase app available for authentication")

                # Verify token with the specific Firebase app
                decoded_token = auth.verify_id_token(token, app=firebase_app)
                
                # Add user_id to kwargs
                kwargs['user_id'] = decoded_token["uid"]
                
                # Call the route handler
                return await func(request, *args, **kwargs)

            except auth.InvalidIdTokenError:
                raise HTTPException(status_code=401, detail="Invalid token")
            except auth.ExpiredIdTokenError:
                raise HTTPException(status_code=401, detail="Token expired")
            except auth.RevokedIdTokenError:
                raise HTTPException(status_code=401, detail="Token revoked")
            except auth.CertificateFetchError:
                raise HTTPException(status_code=500, detail="Failed to fetch certificates")
            except Exception as e:
                logger.error(f"Token verification failed: {e}")
                raise HTTPException(status_code=500, detail="Token verification failed")
        
        return wrapper
    return decorator 