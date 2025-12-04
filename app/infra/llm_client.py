"""Cliente para integração com LLM (OpenAI ou compatível)."""
from __future__ import annotations

from typing import List, Optional

from app.config import OPENAI_API_BASE, OPENAI_API_KEY, OPENAI_MODEL
from app.infra.logging_config import get_logger

logger = get_logger(__name__)


class LLMClient:
    """Cliente para chamadas ao LLM."""

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None, api_base: Optional[str] = None):
        """
        Inicializa o cliente LLM.

        Args:
            model: Nome do modelo (padrão: OPENAI_MODEL)
            api_key: Chave da API (padrão: OPENAI_API_KEY do .env)
            api_base: Base URL da API (padrão: OPENAI_API_BASE do .env)
        """
        self.model = model or OPENAI_MODEL
        self.api_key = api_key or OPENAI_API_KEY
        self.api_base = api_base or OPENAI_API_BASE

        if not self.api_key:
            logger.warning("OPENAI_API_KEY não configurada. Funcionalidades de IA estarão desabilitadas.")

    def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> str:
        """
        Gera texto usando o LLM.

        Args:
            system_prompt: Prompt do sistema
            user_prompt: Prompt do usuário
            temperature: Temperatura para geração (0.0-1.0)

        Returns:
            Texto gerado pelo LLM
        """
        if not self.api_key:
            return "⚠️ Funcionalidade de IA não configurada. Configure OPENAI_API_KEY no .env"

        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.api_key, base_url=self.api_base) if self.api_base else OpenAI(api_key=self.api_key)

            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
            )

            return response.choices[0].message.content or ""
        except ImportError:
            logger.error("Biblioteca 'openai' não instalada. Execute: pip install openai")
            return "⚠️ Biblioteca OpenAI não instalada"
        except Exception as e:
            logger.error(f"Erro ao chamar LLM: {e}")
            return f"⚠️ Erro ao gerar resposta: {str(e)}"

    def chat(self, messages: List[dict], temperature: float = 0.7) -> str:
        """
        Chat com histórico de mensagens.

        Args:
            messages: Lista de mensagens no formato [{"role": "user", "content": "..."}, ...]
            temperature: Temperatura para geração

        Returns:
            Resposta do LLM
        """
        if not self.api_key:
            return "⚠️ Funcionalidade de IA não configurada"

        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.api_key, base_url=self.api_base) if self.api_base else OpenAI(api_key=self.api_key)

            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
            )

            return response.choices[0].message.content or ""
        except ImportError:
            logger.error("Biblioteca 'openai' não instalada")
            return "⚠️ Biblioteca OpenAI não instalada"
        except Exception as e:
            logger.error(f"Erro ao chamar LLM: {e}")
            return f"⚠️ Erro ao gerar resposta: {str(e)}"


