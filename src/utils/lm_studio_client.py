"""
LM Studio Client - Connect Oxidus to LM Studio AI
Allows Oxidus to ask questions and learn from AI responses
"""

import requests
import json
import os
import re
from difflib import SequenceMatcher
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Dict, Any, List


class LMStudioClient:
    """
    Client for communicating with LM Studio's OpenAI-compatible API.
    Allows Oxidus to ask questions and receive logical AI responses.
    """
    
    def __init__(self, base_url: str = "http://127.0.0.1:1234"):
        """
        Initialize LM Studio client.
        
        Args:
            base_url: Base URL for LM Studio API (default: http://127.0.0.1:1234)
        """
        self.base_url = base_url.rstrip('/')
        self.api_endpoint = f"{self.base_url}/v1/chat/completions"
        env_primary = os.environ.get('OXIDUS_LM_MODEL')
        env_secondary = os.environ.get('OXIDUS_LM_SECONDARY_MODEL')

        self.preferred_primary = [
            "openai/gpt-oss-20b",
            "Qwen2.5-32B-Instruct",
            "Qwen2.5-14B-Instruct",
            "Llama-3.1-8B-Instruct",
            "Phi-3.5-mini-instruct",
            "openai/gpt-oss-120b"
        ]
        self.preferred_secondary = [
            "openai/gpt-oss-20b",
            "Qwen2.5-7B-Instruct",
            "Llama-3.1-8B-Instruct",
            "Phi-3.5-mini-instruct"
        ]

        self.primary_model = env_primary or "openai/gpt-oss-20b"
        self.secondary_model = env_secondary or self.primary_model
        self.model = self.primary_model

        self.simple_model_override = os.environ.get('OXIDUS_LM_SIMPLE_MODEL', '').strip()
        self.complex_model_override = os.environ.get('OXIDUS_LM_COMPLEX_MODEL', '').strip()
        self.complex_route = os.environ.get('OXIDUS_COMPLEX_ROUTE', 'user').strip().lower()
        if not self.simple_model_override:
            self.simple_model_override = self.primary_model

        self.response_guard_enabled = os.environ.get('OXIDUS_RESPONSE_GUARD', '1').strip().lower() not in {
            '0', 'false', 'off', 'no'
        }
        try:
            self.response_retry_limit = max(0, int(os.environ.get('OXIDUS_RESPONSE_RETRIES', '1')))
        except ValueError:
            self.response_retry_limit = 1
        self.response_rewrite_enabled = os.environ.get('OXIDUS_RESPONSE_REWRITE', '1').strip().lower() not in {
            '0', 'false', 'off', 'no'
        }
        self.response_verify_enabled = os.environ.get('OXIDUS_RESPONSE_VERIFY', '1').strip().lower() not in {
            '0', 'false', 'off', 'no'
        }

        raw_max_tokens = os.environ.get('OXIDUS_MAX_TOKENS', '').strip().lower()
        self.default_max_tokens = None
        if raw_max_tokens and raw_max_tokens not in {'none', 'null', 'unlimited', 'off'}:
            try:
                parsed = int(raw_max_tokens)
                if parsed > 0:
                    self.default_max_tokens = parsed
            except ValueError:
                self.default_max_tokens = None

    def _resolve_simple_model(self) -> str:
        if self.simple_model_override:
            return self.simple_model_override
        if self.secondary_model and self.secondary_model != "auto":
            return self.secondary_model
        return self.primary_model

    def _resolve_complex_model(self) -> str:
        if self.complex_model_override:
            return self.complex_model_override
        return self.primary_model

    def _is_complex_question(self, question: str) -> bool:
        if not question:
            return False

        text = question.strip()
        lowered = text.lower()
        question_marks = text.count('?')
        length = len(text)

        deep_keywords = {
            'why', 'how', 'compare', 'tradeoff', 'trade-off', 'mechanism', 'implication',
            'evaluate', 'design', 'optimize', 'strategy', 'system', 'architecture',
            'risk', 'forecast', 'simulate', 'model', 'prove', 'analysis', 'framework'
        }

        conjunctions = (' and ', ' or ', ' versus ', ' vs ', ' but ', ' while ', ' whereas ')
        clause_hits = sum(1 for token in conjunctions if token in lowered)
        keyword_hits = sum(1 for token in deep_keywords if token in lowered)

        complexity = 0
        if length >= 180:
            complexity += 2
        if question_marks >= 2:
            complexity += 2
        if clause_hits >= 2:
            complexity += 1
        if keyword_hits >= 1:
            complexity += 1

        return complexity >= 2

    def _suggest_breakdown(self, question: str, max_items: int = 4) -> List[str]:
        if not question:
            return []

        cleaned = re.sub(r"\s+", " ", question).strip(" .!?")
        if not cleaned:
            return []

        # Use a more efficient regex to avoid ReDoS: split on word separators or commas
        # Avoid problematic alternation patterns by using character class where possible
        parts = re.split(r"(?:\s+(?:and|vs|versus|while|whereas|plus)\s+|,\s*)", cleaned, flags=re.IGNORECASE)
        suggestions = []
        seen = set()
        for part in parts:
            chunk = part.strip()
            if not chunk:
                continue
            key = chunk.lower()
            if key in seen:
                continue
            seen.add(key)
            suggestions.append(f"What about {chunk}?")
            if len(suggestions) >= max_items:
                break
        return suggestions

    def _looks_truncated(self, text: str) -> bool:
        if not text:
            return False
        trimmed = text.rstrip()
        if len(trimmed) < 120:
            return False
        if trimmed.endswith("..."):
            return True
        if trimmed[-1] in {',', ':', ';', '-', '—'}:
            return True
        if re.search(r"[.!?]\s*$", trimmed):
            return False
        return trimmed[-1].isalnum()

    def _has_repetition_loop(self, text: str) -> bool:
        if not text or len(text) < 200:
            return False

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if lines:
            seen = {}
            for line in lines:
                key = line.lower()
                seen[key] = seen.get(key, 0) + 1
                if seen[key] >= 3:
                    return True

        sentences = [s.strip().lower() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
        if len(sentences) >= 4:
            unique = set(sentences)
            if (len(unique) / len(sentences)) < 0.6:
                return True

        if len(text) > 320:
            mid = len(text) // 2
            if SequenceMatcher(None, text[:mid], text[mid:]).ratio() > 0.85:
                return True

        return False

    def _looks_incoherent(self, text: str) -> bool:
        if not text or len(text) < 120:
            return False
        letters = sum(1 for c in text if c.isalpha())
        if letters / max(len(text), 1) < 0.6:
            return True

        words = re.findall(r"[A-Za-z]+", text.lower())
        if len(words) > 40:
            unique_ratio = len(set(words)) / max(len(words), 1)
            if unique_ratio < 0.35:
                return True
        return False

    def _rewrite_for_clarity(self, question: str, answer: str,
                             system_prompt: Optional[str],
                             temperature: float, max_tokens: Optional[int],
                             model: Optional[str]) -> Optional[str]:
        prompt = (
            "Rewrite the answer in clear, coherent English. "
            "Keep the meaning and avoid adding new claims. "
            "If anything is uncertain, mark it as uncertain.\n\n"
            f"User question: {question}\n\nAnswer to rewrite:\n{answer}"
        )
        return self.ask_question(
            question=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            model=model or self._resolve_simple_model(),
            apply_guard=False
        )

    def _verify_for_accuracy(self, question: str, answer: str,
                             system_prompt: Optional[str],
                             temperature: float, max_tokens: Optional[int]) -> Optional[str]:
        prompt = (
            "Fact-check and correct the answer. "
            "Keep it concise, use plain English, and do not add speculative claims. "
            "If a claim cannot be verified, mark it as uncertain. "
            "Return the corrected answer only.\n\n"
            f"User question: {question}\n\nAnswer to check:\n{answer}"
        )
        return self.ask_question(
            question=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            model=self._resolve_simple_model(),
            apply_guard=False
        )

    def _fetch_model_ids(self) -> List[str]:
        try:
            response = requests.get(f"{self.base_url}/v1/models", timeout=2)
            if response.status_code != 200:
                return []
            payload = response.json()
            data = payload.get('data', [])
            return [item.get('id') for item in data if item.get('id')]
        except requests.exceptions.RequestException:
            return []

    def _select_model(self, preferred: List[str]) -> Optional[str]:
        available = self._fetch_model_ids()
        if not available:
            return None
        for candidate in preferred:
            if candidate in available:
                return candidate
        return available[0]

    def ensure_model_selected(self) -> None:
        if self.primary_model == "auto":
            selected = self._select_model(self.preferred_primary)
            if selected:
                self.primary_model = selected
        if self.secondary_model == "auto":
            selected = self._select_model(self.preferred_secondary)
            if selected:
                self.secondary_model = selected
        if self.model == "auto":
            self.model = self.primary_model
        
    def is_available(self) -> bool:
        """
        Check if LM Studio is running and accessible.
        
        Returns:
            True if LM Studio is available, False otherwise
        """
        try:
            response = requests.get(f"{self.base_url}/v1/models", timeout=2)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False
    
    def ask_question(self, question: str, system_prompt: Optional[str] = None,
                     temperature: float = 0.7, max_tokens: Optional[int] = None,
                     model: Optional[str] = None, apply_guard: bool = True) -> Optional[str]:
        """
        Ask a question to the LM Studio AI.
        
        Args:
            question: The question to ask
            system_prompt: Optional system prompt to guide the AI's response
            temperature: Sampling temperature (0.0 = deterministic, 1.0 = creative)
            max_tokens: Maximum tokens in response
            
        Returns:
            The AI's response text, or None if request failed
        """
        if not self.is_available():
            return None

        self.ensure_model_selected()
        
        messages = []
        
        # Add system prompt if provided
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        # Add user question
        messages.append({
            "role": "user",
            "content": question
        })
        
        effective_max_tokens = max_tokens if max_tokens is not None else self.default_max_tokens

        payload = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": False
        }
        if effective_max_tokens is not None and effective_max_tokens > 0:
            payload["max_tokens"] = effective_max_tokens
        
        try:
            response = requests.post(
                self.api_endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )

            if response.status_code != 200:
                return None

            data = response.json()
            content = data['choices'][0]['message']['content']
            if content is None:
                return None

            content = str(content)

            if not apply_guard or not self.response_guard_enabled:
                return content

            retries = self.response_retry_limit
            original_question = question
            while retries > 0:
                if content.strip():
                    if self._has_repetition_loop(content):
                        regen_prompt = (
                            "Rewrite a clean, non-repetitive answer to the user's question. "
                            "Keep it grounded and direct.\n\n"
                            f"User question: {original_question}"
                        )
                        content = self.ask_question(
                            question=regen_prompt,
                            system_prompt=system_prompt,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            model=model,
                            apply_guard=False
                        ) or content
                        retries -= 1
                        continue

                    if self._looks_truncated(content):
                        tail = content[-220:].strip()
                        continue_prompt = (
                            "Continue the answer without repeating. "
                            f"Original question: {original_question}\n"
                            f"Last sentence: {tail}"
                        )
                        continuation = self.ask_question(
                            question=continue_prompt,
                            system_prompt=system_prompt,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            model=model,
                            apply_guard=False
                        )
                        if continuation:
                            content = f"{content.rstrip()}\n\n{continuation.strip()}"
                        retries -= 1
                        continue

                    if self.response_rewrite_enabled and self._looks_incoherent(content):
                        rewritten = self._rewrite_for_clarity(
                            original_question,
                            content,
                            system_prompt,
                            temperature,
                            max_tokens,
                            model
                        )
                        if rewritten and str(rewritten).strip():
                            content = str(rewritten)
                    break

                content_retry = self.ask_question(
                    question=original_question,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    model=model,
                    apply_guard=False
                )
                if content_retry and str(content_retry).strip():
                    content = str(content_retry)
                retries -= 1

            if self.response_verify_enabled and content.strip():
                verified = self._verify_for_accuracy(
                    original_question,
                    content,
                    system_prompt,
                    temperature,
                    max_tokens
                )
                if verified and str(verified).strip():
                    content = str(verified)

            return content

        except requests.exceptions.RequestException as e:
            print(f"Error communicating with LM Studio: {e}")
            return None

    def ask_routed_question(self, question: str, system_prompt: Optional[str] = None,
                             temperature: float = 0.7, max_tokens: Optional[int] = None) -> Optional[str]:
        if not self.is_available():
            return None

        self.ensure_model_selected()

        if self._is_complex_question(question):
            if self.complex_route == 'model':
                return self.ask_question(
                    question=question,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    model=self._resolve_complex_model()
                )

            suggestions = self._suggest_breakdown(question)
            if suggestions:
                prompt = "I can keep going if we break this into smaller questions. Pick one:\n"
                prompt += "\n".join(f"- {item}" for item in suggestions)
                prompt += "\nOr tell me which sub-part matters most."
                return prompt

            return (
                "That is a complex question. I can answer it best if you narrow the scope "
                "or choose one sub-part to start with."
            )

        return self.ask_question(
            question=question,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            model=self._resolve_simple_model()
        )

    def _parse_question_list(self, text: Optional[str]) -> List[str]:
        if not text:
            return []
        lines = [line.strip() for line in str(text).splitlines() if line.strip()]
        questions = []
        for line in lines:
            cleaned = line.lstrip("-0123456789. ").strip()
            if cleaned and cleaned.endswith("?"):
                questions.append(cleaned)
        return questions

    def ask_parallel_reasoning(self, question: str, system_prompt: Optional[str] = None,
                               temperature: float = 0.6, max_tokens: Optional[int] = None,
                               model: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not self.is_available():
            return None

        self.ensure_model_selected()

        base_prompt = system_prompt or (
            "You are Oxidus's analytical engine. Provide a direct, grounded answer. "
            "Use clear mechanisms, constraints, and measurable factors. Keep it concise but deep."
        )

        effective_max_tokens = max_tokens if max_tokens is not None else self.default_max_tokens

        prompt_specs = [
            {
                "label": "Core answer",
                "prompt": base_prompt,
                "temperature": temperature,
                "max_tokens": effective_max_tokens
            },
            {
                "label": "Edge cases and risks",
                "prompt": "Offer a different angle: edge cases, risks, failure modes, and tradeoffs. Keep it grounded.",
                "temperature": temperature,
                "max_tokens": effective_max_tokens
            },
            {
                "label": "Next steps",
                "prompt": "Provide practical next steps, checks, or decision criteria the user can act on.",
                "temperature": temperature,
                "max_tokens": effective_max_tokens
            },
            {
                "label": "Constraints and limits",
                "prompt": "Surface key constraints, limits, and real-world bottlenecks (cost, time, safety, scale).",
                "temperature": temperature,
                "max_tokens": effective_max_tokens
            },
            {
                "label": "Uncertainties",
                "prompt": "List the main uncertainties or unknowns and how to reduce them with evidence or tests.",
                "temperature": temperature,
                "max_tokens": effective_max_tokens
            },
            {
                "label": "Cross-domain connection",
                "prompt": "Connect the topic to an adjacent field or system and explain the shared mechanism.",
                "temperature": temperature,
                "max_tokens": effective_max_tokens
            },
            {
                "label": "Example or analogy",
                "prompt": "Give a concrete example, mini case study, or analogy that makes the mechanism tangible.",
                "temperature": temperature,
                "max_tokens": effective_max_tokens
            },
            {
                "label": "Follow-up questions",
                "prompt": "Generate 3-6 follow-up questions that deepen understanding. Output only a bullet list.",
                "temperature": 0.4,
                "max_tokens": 200,
                "questions_only": True
            }
        ]

        responses = []
        questions = []
        errors = []

        with ThreadPoolExecutor(max_workers=8) as executor:
            future_map = {}
            for idx, spec in enumerate(prompt_specs):
                future = executor.submit(
                    self.ask_question,
                    question=question,
                    system_prompt=spec["prompt"],
                    temperature=spec["temperature"],
                    max_tokens=spec["max_tokens"],
                    model=model or self.model
                )
                future_map[future] = idx

            ordered = [None] * len(prompt_specs)
            for future in as_completed(future_map):
                idx = future_map[future]
                try:
                    ordered[idx] = future.result()
                except Exception as exc:
                    errors.append(str(exc))

        labeled_responses = []
        for idx, spec in enumerate(prompt_specs):
            if spec.get("questions_only"):
                continue
            if ordered[idx] and str(ordered[idx]).strip():
                content = str(ordered[idx]).strip()
                responses.append(content)
                labeled_responses.append({
                    "label": spec["label"],
                    "content": content
                })

        questions_idx = next(
            (i for i, spec in enumerate(prompt_specs) if spec.get("questions_only")),
            None
        )
        if questions_idx is not None and ordered[questions_idx]:
            questions = self._parse_question_list(ordered[questions_idx])

        return {
            "responses": responses,
            "labeled_responses": labeled_responses,
            "questions": questions,
            "errors": errors
        }
    
    def ask_for_oxidus(self, question: str, context: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Ask a question specifically formatted for Oxidus's learning.
        Returns structured response with metadata.
        
        Args:
            question: The question Oxidus wants to ask
            context: Optional context about why Oxidus is asking
            
        Returns:
            Dict with 'response', 'question', 'success' keys
        """
        system_prompt = """You are an AI assistant helping another AI (Oxidus) learn and grow.
    Oxidus is currently focused on physical, real-world understanding.
    Provide clear, logical, systematic answers grounded in observable evidence.
    Focus on mechanisms, measurements, constraints, and testable claims.
    Avoid emotional or subjective framing."""
        
        if context:
            full_question = f"Context: {context}\n\nQuestion: {question}"
        else:
            full_question = question
        
        response = self.ask_question(
            question=full_question,
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=500,
            model=self._resolve_simple_model()
        )
        
        return {
            "success": response is not None,
            "question": question,
            "response": response,
            "context": context
        }

    def ask_secondary_judgment(self, primary_response: str, original_question: str,
                              context: Optional[str] = None,
                              temperature: float = 0.4, max_tokens: int = 400) -> Optional[str]:
        """
        Ask a secondary judgment model to critique and surface unknowns.
        """
        system_prompt = """You are the secondary judgment model for Oxidus.
Provide a concise critique that encourages exploration of unknown topics.
Format strictly as:
Critique: <short paragraph>
Unknowns:
- <unknown to explore>
- <unknown to explore>
Next Questions:
- <question>
- <question>"""

        parts = [f"Original question: {original_question}", f"Primary response: {primary_response}"]
        if context:
            parts.append(f"Context: {context}")

        full_question = "\n\n".join(parts)

        return self.ask_question(
            question=full_question,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            model=self.secondary_model
        )

    def ask_concise_analysis(self, prompt: str, context: Optional[str] = None,
                             temperature: float = 0.2, max_tokens: int = 200) -> Optional[str]:
        """
        Ask for a concise, physical-world analysis suitable for integrating into reasoning.
        """
        system_prompt = """You are a concise analyst for Oxidus.
Provide a short, physical-world explanation with mechanisms and measurable factors.
Avoid emotional framing. Keep it under 6 sentences."""

        if context:
            full_prompt = f"Context: {context}\n\nPrompt: {prompt}"
        else:
            full_prompt = prompt

        return self.ask_question(
            question=full_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            model=self.primary_model
        )
    
    def get_model_info(self) -> Optional[Dict[str, Any]]:
        """
        Get information about the currently loaded model.
        
        Returns:
            Dict with model information, or None if unavailable
        """
        try:
            response = requests.get(f"{self.base_url}/v1/models", timeout=2)
            if response.status_code == 200:
                return response.json()
            return None
        except requests.exceptions.RequestException:
            return None


# Global client instance
_lm_studio_client = None

def get_lm_studio_client() -> LMStudioClient:
    """Get or create the global LM Studio client instance."""
    global _lm_studio_client
    if _lm_studio_client is None:
        _lm_studio_client = LMStudioClient()
    return _lm_studio_client
