from fastapi import HTTPException, Request
import logging

logger = logging.getLogger(__name__)

def get_user_id(request: Request) -> str:
    """Extract user_id from Firebase token"""
    from firebase_admin import auth
    import firebase_admin
    from ..db.firestore import firestore_manager
    
    # Get token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="No authorization header")

    try:
        # Extract token
        scheme, token = auth_header.split()
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid authentication scheme")

        # Get the Firebase app from firestore_manager
        firebase_app = None
        if firestore_manager.app_name:
            try:
                firebase_app = firebase_admin.get_app(firestore_manager.app_name)
            except ValueError:
                pass
        
        if not firebase_app:
            # Fallback: try to get any available Firebase app
            apps = firebase_admin._apps
            if apps:
                firebase_app = list(apps.values())[0]
            else:
                raise HTTPException(status_code=500, detail="No Firebase app available for authentication")

        # Verify token with the specific Firebase app
        decoded_token = auth.verify_id_token(token, app=firebase_app)
        return decoded_token["uid"]

    except auth.InvalidIdTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except auth.ExpiredIdTokenError:
        raise HTTPException(status_code=401, detail="Token expired")
    except auth.RevokedIdTokenError:
        raise HTTPException(status_code=401, detail="Token revoked")
    except Exception as e:
        logger.error(f"Token verification failed: {e}")
        raise HTTPException(status_code=500, detail="Token verification failed")

# Re-export for convenience
__all__ = ['get_user_id'] 