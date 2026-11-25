from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "NexovAI Doctor Assistant"
    MONGODB_URI: str
    MONGODB_DB_NAME: str = "nexovai_doctor"
    GROQ_API_KEY: str = ""
    ELEVENLABS_API_KEY: str = ""
    ELEVENLABS_VOICE_ID: str = ""
    FRONTEND_URL: str = "http://localhost:5173"
    
    model_config = SettingsConfigDict(
      env_file=".env",
      env_file_encoding="utf-8",
      extra="ignore"
    )
    
settings = Settings()