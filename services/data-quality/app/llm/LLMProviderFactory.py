

from .providers import OpenAIProvider


class LLMProviderFactory:
    def __init__(self, config: dict):
        self.config = config


    def create_llm_provider(self,provider:str):
        """Factory function to create the configured LLM provider."""
        if provider.lower() == "openai":
            return OpenAIProvider(
                self.config.OPENAI_API_KEY,
                self.config.OPENAI_API_URL,
                self.config.OPENAI_MODEL,
                self.config.MIN_QUALITY_SCORE,
                self.config.INPUT_DEFAULT_MAX_CHARACTERS
            )
        else:
            raise ValueError(f"Unknown provider: {provider}")
