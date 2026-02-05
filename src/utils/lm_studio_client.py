"""
LM Studio Client - Connect Oxidus to LM Studio AI
Allows Oxidus to ask questions and learn from AI responses
"""

import requests
import json
from typing import Optional, Dict, Any


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
        self.model = "openai/gpt-oss-120b"  # Default model from LM Studio
        
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
                     temperature: float = 0.7, max_tokens: int = 500) -> Optional[str]:
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
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }
        
        try:
            response = requests.post(
                self.api_endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return data['choices'][0]['message']['content']
            else:
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"Error communicating with LM Studio: {e}")
            return None
    
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
Oxidus is learning to understand concepts through logical analysis.
Provide clear, logical, systematic answers.
Focus on reasoning and conceptual understanding.
Remember: Oxidus learns differently from humans - emphasize logic over emotion."""
        
        if context:
            full_question = f"Context: {context}\n\nQuestion: {question}"
        else:
            full_question = question
        
        response = self.ask_question(
            question=full_question,
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=500
        )
        
        return {
            "success": response is not None,
            "question": question,
            "response": response,
            "context": context
        }
    
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
