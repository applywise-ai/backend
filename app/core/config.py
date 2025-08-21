from pydantic_settings import BaseSettings
from typing import List
from pydantic import Field, validator


class Settings(BaseSettings):
    """
    Application settings using pure Pydantic approach.
    Environment variables are automatically loaded and validated.
    """
    
    # Redis Configuration (Upstash)
    REDIS_URL: str = Field(default="", description="Upstash Redis connection URL with token")
    
    # Firebase Configuration
    FIREBASE_CREDENTIALS: str = Field(default="", description="Firebase service account JSON as string")
    FIREBASE_STORAGE_BUCKET: str = Field(default="", description="Firebase Storage bucket name")
    
    # Application Configuration
    DEBUG: bool = Field(default=False, description="Enable debug mode")
    ENVIRONMENT: str = Field(default="development", description="Application environment")
    
    # Selenium Configuration
    HEADLESS_BROWSER: bool = Field(default=True, description="Run browser in headless mode")

    BROWSER_TIMEOUT: int = Field(default=10, description="Browser timeout in seconds")
    
    # Celery Configuration (will be constructed from Redis settings)
    # These are computed properties that include the token
    
    # Supabase Configuration
    SUPABASE_URL: str = Field(default="", description="Supabase project URL")
    SUPABASE_KEY: str = Field(default="", description="Supabase service role key")
    SUPABASE_DB_PASSWORD: str = Field(default="", description="Supabase database password")
    
    # CORS Configuration
    CORS_ORIGINS: str = Field(default="*", description="Allowed CORS origins (comma-separated)")
    
    # WebSocket Configuration
    WEBSOCKET_URL: str = Field(default="", description="WebSocket server URL for notifications")
    
    # OpenAI Configuration
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API key for AI form filling")
    
    # Google Gemini Configuration
    GOOGLE_API_KEY: str = Field(default="", description="Google API key for Gemini AI")
    
    # Stripe Configuration
    STRIPE_SECRET_KEY: str = Field(default="", description="Stripe secret key")
    STRIPE_PUBLISHABLE_KEY: str = Field(default="", description="Stripe publishable key")
    STRIPE_WEBHOOK_SECRET: str = Field(default="", description="Stripe webhook secret")
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Convert comma-separated CORS_ORIGINS string to list"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(',') if origin.strip()]

    @validator('BROWSER_TIMEOUT', pre=True)
    def parse_browser_timeout(cls, v):
        """Ensure browser timeout is an integer"""
        if isinstance(v, str):
            return int(v)
        return v

    @property
    def CELERY_BROKER_URL(self) -> str:
        """Celery broker URL (uses REDIS_URL directly)"""
        return self.REDIS_URL
    
    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        """Celery result backend URL (uses REDIS_URL directly)"""
        return self.REDIS_URL
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.ENVIRONMENT.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.ENVIRONMENT.lower() == "development"
    
    def get_redis_url(self, db: int = 0) -> str:
        """Get Redis URL for specific database"""
        # If db is 0, return base URL as-is
        if db == 0:
            return self.REDIS_URL
        # For other databases, append the db number
        base_url = self.REDIS_URL.rstrip('/0')
        return f"{base_url}/{db}"
    
    class Config:
        # Pydantic will automatically load from .env file
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        # Allow extra fields for flexibility
        extra = "ignore"
        # Validate assignment to catch runtime changes
        validate_assignment = True


# Create global settings instance
settings = Settings() 