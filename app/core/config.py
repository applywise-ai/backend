from pydantic_settings import BaseSettings
from typing import List
from pydantic import Field, validator


class Settings(BaseSettings):
    """
    Application settings using pure Pydantic approach.
    Environment variables are automatically loaded and validated.
    """
    
    # Redis Configuration
    REDIS_URL: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")
    
    # Firebase Configuration
    FIREBASE_CREDENTIALS_PATH: str = Field(default="", description="Path to Firebase service account JSON")
    FIREBASE_STORAGE_BUCKET: str = Field(default="", description="Firebase Storage bucket name")
    
    # Application Configuration
    DEBUG: bool = Field(default=False, description="Enable debug mode")
    ENVIRONMENT: str = Field(default="development", description="Application environment")
    
    # Selenium Configuration
    HEADLESS_BROWSER: bool = Field(default=True, description="Run browser in headless mode")
    BROWSER_TIMEOUT: int = Field(default=10, description="Browser timeout in seconds")
    
    # Celery Configuration
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/0", description="Celery broker URL")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/0", description="Celery result backend URL")
    
    # PostgreSQL Configuration
    POSTGRES_HOST: str = Field(
        default="172.31.85.170",
        description="PostgreSQL host"
    )
    POSTGRES_PORT: int = Field(default=5432, description="PostgreSQL port")
    POSTGRES_DB: str = Field(default="applywise", description="PostgreSQL database name")
    POSTGRES_USER: str = Field(default="postgres", description="PostgreSQL username")
    POSTGRES_PASSWORD: str = Field(default="", description="PostgreSQL password")
    
    # CORS Configuration
    CORS_ORIGINS: List[str] = Field(default=["*"], description="Allowed CORS origins")
    
    # AWS Configuration
    AWS_REGION: str = Field(default="us-east-1", description="AWS region")
    AWS_ACCESS_KEY_ID: str = Field(default="", description="AWS access key ID")
    AWS_SECRET_ACCESS_KEY: str = Field(default="", description="AWS secret access key")
    
    # WebSocket Configuration
    WEBSOCKET_URL: str = Field(default="", description="WebSocket server URL for notifications")
    
    # OpenAI Configuration
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API key for AI form filling")
    
    @validator('CORS_ORIGINS', pre=True)
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string or list"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',')]
        return v
    
    @validator('POSTGRES_PORT', pre=True)
    def parse_postgres_port(cls, v):
        """Ensure PostgreSQL port is an integer"""
        if isinstance(v, str):
            return int(v)
        return v
    
    @validator('BROWSER_TIMEOUT', pre=True)
    def parse_browser_timeout(cls, v):
        """Ensure browser timeout is an integer"""
        if isinstance(v, str):
            return int(v)
        return v
    
    @property
    def DATABASE_URL(self) -> str:
        """Construct database URL from PostgreSQL parameters"""
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
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