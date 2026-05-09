import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Gov Tech Consultation AI"
    API_V1_STR: str = "/api/v1"
    
    # 知识库路径
    # 注意：这里我们使用绝对路径，避免相对路径带来的困扰
    # __file__ is .../backend/app/core/config.py
    # we want .../ (root)
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    PERSIST_DIRECTORY: str = os.path.join(BASE_DIR, "data", "chroma_db")
    DOCS_DIRECTORY: str = os.path.join(BASE_DIR, "data", "regulations")
    
    # API Key Configuration
    # We use Field to explicitly map to environment variables if needed, 
    # but Pydantic BaseSettings does this automatically.
    # To ensure .env priority, we can use the Config class properly.
    OPENAI_API_KEY: str = ""
    OPENAI_API_BASE: str = "https://api.openai.com/v1"
    ADMIN_PASSWORD: str = "admin123"

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        case_sensitive = True
        extra = "ignore"

settings = Settings()
