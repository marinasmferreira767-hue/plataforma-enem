"""Camada de IA — Anthropic com fallback OpenAI. Zero dependência web."""

from __future__ import annotations

import json
import os
import re


def _chave_anthropic() -> str:
    return os.environ.get("ANTHROPIC_API_KEY", "").strip()


def _chave_openai() -> str:
    return os.environ.get("OPENAI_API_KEY", "").strip()


def ia_disponivel() -> bool:
    return bool(_chave_anthropic() or _chave_openai())


def provedor() -> str:
    if _chave_anthropic():
        return "anthropic"
    if _chave_openai():
        return "openai"
    return ""


def chamar(system: str, prompt: str, max_tokens: int = 3000) -> str:
    """Manda o par (system, prompt) para o modelo disponível e devolve texto puro."""
    if _chave_anthropic():
        from anthropic import Anthropic

        cliente = Anthropic(api_key=_chave_anthropic())
        modelo = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")
        resp = cliente.messages.create(
            model=modelo,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(bloco.text for bloco in resp.content if getattr(bloco, "type", "") == "text")

    if _chave_openai():
        from openai import OpenAI

        cliente = OpenAI(api_key=_chave_openai())
        modelo = os.environ.get("OPENAI_MODEL", "gpt-4o")
        resp = cliente.chat.completions.create(
            model=modelo,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
        return resp.choices[0].message.content or ""

    raise RuntimeError(
        "Nenhuma chave de IA configurada. "
        "Defina ANTHROPIC_API_KEY ou OPENAI_API_KEY nas variáveis do projeto."
    )


def extrair_json(bruto: str) -> dict:
    """Isola o objeto JSON da resposta, mesmo com cerca de código ou texto extra."""
    limpo = re.sub(r"^```(?:json)?|```$", "", bruto.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(limpo)
    except json.JSONDecodeError:
        ini, fim = limpo.find("{"), limpo.rfind("}")
        if ini == -1 or fim == -1:
            raise ValueError("A IA não devolveu um JSON válido.")
        return json.loads(limpo[ini : fim + 1])
