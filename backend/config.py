"""Configuration management for AI Virtual Try-On service."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Local Diffusion settings
    diffusion_model_id: str = Field(
        default="runwayml/stable-diffusion-v1-5",
        env="DIFFUSION_MODEL_ID"
    )
    diffusion_inpaint_model_id: str = Field(
        default="runwayml/stable-diffusion-inpainting",
        env="DIFFUSION_INPAINT_MODEL_ID"
    )
    diffusion_device: str = Field(
        default="cpu",
        env="DIFFUSION_DEVICE"
    )
    
    # Storage paths
    storage_path: Path = Field(default=Path("./storage"), env="STORAGE_PATH")
    
    # Image constraints
    max_image_size_mb: int = Field(default=10, env="MAX_IMAGE_SIZE_MB")
    max_image_dimension: int = Field(default=2048, env="MAX_IMAGE_DIMENSION")
    work_image_size: int = Field(default=1536, env="WORK_IMAGE_SIZE")
    
    # Quality control
    quality_threshold: float = Field(default=0.5, env="QUALITY_THRESHOLD")
    max_retries: int = Field(default=2, env="MAX_RETRIES")
    
    # Server
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    workers: int = Field(default=1, env="WORKERS")
    
    # Debug
    debug: bool = Field(default=False, env="DEBUG")
    save_debug_artifacts: bool = Field(default=False, env="SAVE_DEBUG_ARTIFACTS")
    
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")
    
    @property
    def uploads_path(self) -> Path:
        return self.storage_path / "uploads"
    
    @property
    def products_path(self) -> Path:
        return self.storage_path / "products"
    
    @property
    def results_path(self) -> Path:
        return self.storage_path / "results"
    
    @property
    def artifacts_path(self) -> Path:
        return self.storage_path / "artifacts"
    
    def ensure_directories(self):
        """Create all storage directories if they don't exist."""
        for path in [
            self.uploads_path,
            self.products_path,
            self.results_path,
            self.artifacts_path
        ]:
            path.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()
