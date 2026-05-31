from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Generator

import httpx

from app.core.config import Settings


@dataclass
class LLMClient:
    settings: Settings

    def is_available(self) -> bool:
        provider = self.settings.llm_provider.lower()
        if provider == "groq":
            return bool(self.settings.groq_api_key)
        if provider == "ollama":
            return True
        if provider == "gemini":
            return bool(self.settings.gemini_api_key)
        return False

    def generate(self, prompt: str, system: str | None = None, response_format: str | None = None) -> str:
        if not self.is_available():
            raise RuntimeError(f"LLM provider '{self.settings.llm_provider}' is not configured.")

        provider = self.settings.llm_provider.lower()

        if provider == "groq":
            if not self.settings.groq_api_key:
                raise ValueError("GROQ_API_KEY is missing in .env")
            try:
                return self._generate_groq(prompt, system, response_format)
            except Exception as e:
                print(f"\n[FATAL] Groq API Error: {e}")
                raise e 

        if provider == "gemini":
            if not self.settings.gemini_api_key:
                raise ValueError("GEMINI_API_KEY is missing in .env")
            return self._generate_gemini(prompt, system, response_format)

        return self._generate_ollama(prompt, system, response_format)

    def _generate_gemini(self, prompt: str, system: str | None, response_format: str | None) -> str:
        # Using Gemini 1.5 Flash for speed and reliability
        model = "gemini-1.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.settings.gemini_api_key}"

        contents = []
        if system:
            # Gemini system instructions are handled differently, but for simplicity we prepend to prompt
            # or use system_instruction if available in v1beta
            prompt = f"SYSTEM INSTRUCTION: {system}\n\nUSER PROMPT: {prompt}"

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
        }

        if response_format == "json":
            payload["generationConfig"] = {"responseMimeType": "application/json"}

        response = httpx.post(url, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()

        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            return ""

    def stream(self, prompt: str, system: str | None = None) -> Generator[str, None, None]:
        if not self.is_available():
            yield "LLM provider is not configured."
            return

        provider = self.settings.llm_provider.lower()
        if provider == "groq" and self.settings.groq_api_key:
            yield from self._stream_groq(prompt, system)
        elif provider == "gemini":
            # Gemini streaming not implemented here yet, fallback to non-stream for now or implement
            yield self.generate(prompt, system)
        else:
            yield from self._stream_ollama(prompt, system)

    def _generate_ollama(self, prompt: str, system: str | None, response_format: str | None) -> str:
        base_url = self.settings.ollama_base_url.rstrip("/")
        payload = {
            "model": self.settings.ollama_model,
            "messages": [
                {"role": "system", "content": system or "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
        }
        if response_format:
            payload["format"] = response_format

        response = httpx.post(f"{base_url}/api/chat", json=payload, timeout=600)
        response.raise_for_status()
        data = response.json()
        return data.get("message", {}).get("content", "")

    def _stream_ollama(self, prompt: str, system: str | None) -> Generator[str, None, None]:
        base_url = self.settings.ollama_base_url.rstrip("/")
        payload = {
            "model": self.settings.ollama_model,
            "messages": [
                {"role": "system", "content": system or "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
            "stream": True,
        }
        with httpx.stream("POST", f"{base_url}/api/chat", json=payload, timeout=600) as response:
            for line in response.iter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        yield token
                except Exception:
                    continue

    def _generate_groq(self, prompt: str, system: str | None, response_format: str | None) -> str:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.groq_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.settings.groq_model,
            "messages": [
                {"role": "system", "content": system or "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
        }
        if response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        # Exponential backoff retry for Groq (handling 429)
        max_retries = 5
        for attempt in range(max_retries):
            try:
                response = httpx.post(url, headers=headers, json=payload, timeout=120)
                if response.status_code == 429:
                    wait_time = 2 ** attempt
                    print(f"   [!] Groq Rate Limit (429). Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                data = response.json()
                return data.get("choices", [{}])[0].get("message", {}).get("content", "")
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                time.sleep(2 ** attempt)
        return ""

    def _stream_groq(self, prompt: str, system: str | None) -> Generator[str, None, None]:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.groq_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.settings.groq_model,
            "messages": [
                {"role": "system", "content": system or "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
            "stream": True,
        }
        with httpx.stream("POST", url, headers=headers, json=payload, timeout=120) as response:
            for line in response.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    token = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                    if token:
                        yield token
                except Exception:
                    continue

    def generate_json(self, prompt: str, system: str | None = None) -> dict:
        raw = self.generate(prompt, system=system, response_format="json")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Fallback if the LLM returned text with a JSON block anyway
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(raw[start : end + 1])
                except json.JSONDecodeError:
                    pass
            return {}
