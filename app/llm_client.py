import re
import json
import asyncio
import httpx
from typing import List, Dict, Any, Optional, AsyncGenerator

class LLMClient:
    """
    Unified client for communicating with local LLM engines:
    - Ollama (http://127.0.0.1:11434) with live token streaming
    - OpenAI-Compatible servers (LM Studio, Jan, vLLM at http://127.0.0.1:1234/v1) with live streaming
    - Offline Grounded Synthesizer (instant)
    """

    @staticmethod
    async def list_models(provider: str, base_url: str) -> List[str]:
        """Queries local provider to list available models."""
        base_url = base_url.rstrip("/")
        models = []

        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                if provider == "ollama":
                    res = await client.get(f"{base_url}/api/tags")
                    if res.status_code == 200:
                        data = res.json()
                        models = [m.get("name") for m in data.get("models", []) if m.get("name")]
                elif provider == "openai_compatible":
                    res = await client.get(f"{base_url}/models")
                    if res.status_code == 200:
                        data = res.json()
                        models = [m.get("id") for m in data.get("data", []) if m.get("id")]
        except Exception:
            pass

        return models

    @staticmethod
    async def check_health(provider: str, base_url: str) -> Dict[str, Any]:
        """Checks if the local LLM server is reachable."""
        base_url = base_url.rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                if provider == "ollama":
                    res = await client.get(f"{base_url}/")
                    return {"reachable": res.status_code == 200, "message": "Ollama is online"}
                elif provider == "openai_compatible":
                    res = await client.get(f"{base_url}/models")
                    return {"reachable": res.status_code == 200, "message": "OpenAI-compatible server is online"}
        except Exception as e:
            return {"reachable": False, "message": f"Connection failed: {str(e)}"}

        return {"reachable": False, "message": "Unknown provider"}

    @staticmethod
    async def generate_stream(
        provider: str,
        base_url: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 512,
        num_ctx: int = 2048,
        retrieved_chunks: Optional[List[Dict[str, Any]]] = None
    ) -> AsyncGenerator[str, None]:
        """
        Streams generated tokens in real-time as they are produced by the local LLM.
        """
        base_url = base_url.rstrip("/")

        if provider == "offline":
            full_ans = LLMClient._offline_grounded_answer(user_prompt, retrieved_chunks)["answer"]
            words = full_ans.split(" ")
            for i, word in enumerate(words):
                yield word + (" " if i < len(words) - 1 else "")
                await asyncio.sleep(0.015)
            return

        if provider == "ollama":
            url = f"{base_url}/api/generate"
            payload = {
                "model": model,
                "prompt": user_prompt,
                "system": system_prompt,
                "stream": True,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                    "num_ctx": num_ctx
                }
            }

            try:
                async with httpx.AsyncClient(timeout=90.0) as client:
                    async with client.stream("POST", url, json=payload) as response:
                        if response.status_code != 200:
                            err_body = await response.aread()
                            yield f"⚠️ Ollama error ({response.status_code}): {err_body.decode('utf-8', errors='ignore')}"
                            return

                        async for line in response.aiter_lines():
                            if not line.strip():
                                continue
                            try:
                                chunk_json = json.loads(line)
                                token = chunk_json.get("response", "")
                                if token:
                                    yield token
                                if chunk_json.get("done", False):
                                    break
                            except Exception:
                                continue
            except httpx.ConnectError:
                yield f"⚠️ Could not connect to Ollama at {base_url}. Ensure Ollama is running (`ollama serve`)."
            except Exception as e:
                yield f"⚠️ Request error: {str(e)}"
            return

        elif provider == "openai_compatible":
            url = f"{base_url}/chat/completions"
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True
            }

            try:
                async with httpx.AsyncClient(timeout=90.0) as client:
                    async with client.stream("POST", url, json=payload) as response:
                        if response.status_code != 200:
                            err_body = await response.aread()
                            yield f"⚠️ Local LLM error ({response.status_code}): {err_body.decode('utf-8', errors='ignore')}"
                            return

                        async for line in response.aiter_lines():
                            line_str = line.strip()
                            if not line_str or line_str == "data: [DONE]":
                                continue
                            if line_str.startswith("data: "):
                                data_payload = line_str[6:]
                                try:
                                    chunk_json = json.loads(data_payload)
                                    choices = chunk_json.get("choices", [])
                                    if choices:
                                        delta = choices[0].get("delta", {})
                                        content = delta.get("content", "")
                                        if content:
                                            yield content
                                except Exception:
                                    continue
            except httpx.ConnectError:
                yield f"⚠️ Could not connect to local server at {base_url}. Verify LM Studio / vLLM is active."
            except Exception as e:
                yield f"⚠️ Request error: {str(e)}"
            return

        yield f"⚠️ Unsupported provider: {provider}"

    @staticmethod
    async def generate_response(
        provider: str,
        base_url: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 512,
        retrieved_chunks: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Non-streaming fallback."""
        tokens = []
        async for token in LLMClient.generate_stream(
            provider=provider,
            base_url=base_url,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            retrieved_chunks=retrieved_chunks
        ):
            tokens.append(token)

        full_answer = "".join(tokens)
        is_error = full_answer.startswith("⚠️")
        return {
            "success": not is_error,
            "answer": full_answer,
            "model": model,
            "provider": provider,
            "error": full_answer if is_error else None
        }

    @staticmethod
    def _offline_grounded_answer(user_augmented_prompt: str, retrieved_chunks: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
        """Extractive Grounded Response generator when offline / testing mode is selected."""
        if not retrieved_chunks:
            return {
                "success": True,
                "answer": "The uploaded document does not contain information to answer this question.",
                "model": "offline-grounded-engine",
                "provider": "offline"
            }

        query_match = re.search(r'USER QUESTION:\s*(.*?)\s*ANSWER', user_augmented_prompt, re.DOTALL)
        user_query = query_match.group(1).strip() if query_match else ""
        query_words = set(re.findall(r'\b[a-zA-Z0-9]+\b', user_query.lower()))
        stop_words = {"how", "many", "who", "what", "where", "when", "which", "are", "is", "the", "in", "of", "this", "project", "a", "an"}
        meaningful_query_words = query_words - stop_words

        matched_lines = []
        for chunk in retrieved_chunks:
            text = chunk.get("text", "")
            lines = [l.strip() for l in text.split("\n") if l.strip() and not l.startswith("[Section:")]
            for line in lines:
                line_words = set(re.findall(r'\b[a-zA-Z0-9]+\b', line.lower()))
                overlap = meaningful_query_words.intersection(line_words)
                if len(overlap) >= 1:
                    matched_lines.append((line, chunk["chunk_id"], len(overlap)))

        matched_lines.sort(key=lambda x: x[2], reverse=True)

        if matched_lines:
            seen = set()
            unique_findings = []
            for line, cid, _ in matched_lines:
                if line not in seen:
                    seen.add(line)
                    unique_findings.append(f"- {line} [Chunk {cid}]")
                if len(unique_findings) >= 5:
                    break

            findings_text = "\n\n".join(unique_findings)
            answer = f"Based on the document context:\n\n{findings_text}"
        else:
            top_chunk = retrieved_chunks[0]
            clean_text = top_chunk['text'].replace("[Section: ", "Section: ")
            answer = f"Based on the relevant section [Chunk {top_chunk['chunk_id']}]:\n\n{clean_text[:350]}..."

        return {
            "success": True,
            "answer": answer,
            "model": "offline-grounded-engine",
            "provider": "offline"
        }
