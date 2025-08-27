from pydantic_settings import BaseSettings


class AgentSettings(BaseSettings):
    """
    Configuration settings for the Agent Zero framework.
    """
    default_model: str = "mixtral-8x7b-instruct"
    # In the future, API keys for external services can be added here.
    # e.g., claude_api_key: str = "your_claude_api_key"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


agent_settings = AgentSettings() 