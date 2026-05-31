from __future__ import annotations

import httpx
import time
from typing import List

class EmbeddingService:
    def __init__(self, settings):
        self.api_key = settings.gemini_api_key
        self.model = settings.embeddings_model
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not self.api_key:
            return [[0.0] * 768 for _ in texts]

        # 1. First, try to discover what models are actually available for this key
        available_models = []
        try:
            list_url = f"https://generativelanguage.googleapis.com/v1/models?key={self.api_key}"
            resp = httpx.get(list_url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                for m in data.get("models", []):
                    # Look for models that support 'embedContent'
                    if "embedContent" in m.get("supportedGenerationMethods", []):
                        available_models.append(m.get("name", ""))
            
            if available_models:
                print(f"   [DEBUG] Discovered available models: {available_models}")
        except Exception as e:
            print(f"   [DEBUG] Model discovery failed: {e}")

        # 2. Add standard fallbacks if discovery failed
        models_to_try = available_models + [
            "models/text-embedding-004", 
            "models/embedding-001",
            "models/text-embedding-gecko-001"
        ]
        
        # Remove duplicates while preserving order
        seen = set()
        models_to_try = [x for x in models_to_try if not (x in seen or seen.add(x))]

        for full_model_name in models_to_try:
            if not full_model_name: continue
            
            # Ensure model name starts with models/ for the payload but we use it in the URL too
            if not full_model_name.startswith("models/"):
                full_model_name = f"models/{full_model_name}"
            
            # Use v1 for maximum stability
            url = f"https://generativelanguage.googleapis.com/v1/{full_model_name}:embedContent?key={self.api_key}"
            
            print(f"   [DEBUG] Testing discovered model: {full_model_name}...")
            
            results = []
            try:
                # Test with the first text to see if it works
                payload = {"content": {"parts": [{"text": texts[0]}]}}
                response = httpx.post(url, json=payload, timeout=30)
                
                if response.status_code == 200:
                    # It works! Now process the rest
                    data = response.json()
                    results.append(data.get("embedding", {}).get("values", []))
                    
                    for text in texts[1:]:
                        payload = {"content": {"parts": [{"text": text}]}}
                        r = httpx.post(url, json=payload, timeout=30)
                        results.append(r.json().get("embedding", {}).get("values", []))
                    
                    print(f"   [SUCCESS] Using {full_model_name}")
                    return results
                else:
                    print(f"   [DEBUG] {full_model_name} rejected: {response.status_code}")
            except Exception:
                continue
                    
        print("!!! All embedding models failed. Potential causes: 1. API Key restricted by IP/Referrer. 2. Billing not set up (even for free tier). 3. Region not supported.")
        return [[0.0] * 768 for _ in texts]
