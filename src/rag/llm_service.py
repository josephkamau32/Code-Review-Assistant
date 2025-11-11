from openai import OpenAI
from typing import List, Dict, Any
from loguru import logger
from src.config.settings import settings
from src.models.schemas import CodeChange, ReviewSuggestion
from tenacity import retry, stop_after_attempt, wait_exponential
import json


class LLMService:
    def __init__(self):
        # Use mock mode if no real API key
        api_key = settings.openai_api_key
        if api_key == "your_openai_api_key_here" or not api_key:
            logger.warning("Using mock LLM service - no real API key provided")
            self.mock_mode = True
            self.model = settings.llm_model
        else:
            self.client = OpenAI(api_key=api_key)
            self.mock_mode = False
            self.model = settings.llm_model
        
    def _build_review_prompt(
        self,
        code_change: CodeChange,
        similar_reviews: List[Dict[str, Any]],
        style_guide_context: str = ""
    ) -> str:
        """Build the prompt for code review generation"""
        
        # Format similar reviews
        similar_reviews_text = ""
        if similar_reviews:
            similar_reviews_text = "\n\n### Similar Past Reviews:\n"
            for idx, review in enumerate(similar_reviews[:3], 1):  # Top 3
                similar_reviews_text += f"""
Review {idx}:
Code: {review['document'].split('Review Comment:')[0].strip()}
Comment: {review['document'].split('Review Comment:')[1].strip()}
Was Resolved: {review['metadata'].get('was_resolved', 'Unknown')}
---
"""
        
        prompt = f"""You are an experienced code reviewer. Review the following code change and provide constructive feedback.

### Code Change:
File: {code_change.file_path}
Language: {code_change.language.value}

Diff:
{code_change.diff}

{similar_reviews_text}

{f"### Style Guide Context:\n{style_guide_context}\n" if style_guide_context else ""}

### Instructions:
1. Analyze the code for potential issues (bugs, performance, security, best practices)
2. Consider the similar past reviews to maintain consistency
3. Provide specific, actionable suggestions
4. Categorize each suggestion by severity and type
5. Be constructive and educational

### Output Format (JSON):
{{
    "suggestions": [
        {{
            "line_number": <int or null>,
            "suggestion": "<clear, specific feedback>",
            "severity": "<info|warning|error>",
            "category": "<style|bug|performance|security|best_practice>",
            "confidence": <float 0-1>
        }}
    ],
    "summary": "<brief overall assessment>"
}}

Provide your response as valid JSON only, no additional text."""

        return prompt
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def generate_review(
        self,
        code_change: CodeChange,
        similar_reviews: List[Dict[str, Any]],
        style_guide_context: str = ""
    ) -> Dict[str, Any]:
        """Generate code review using LLM with RAG context"""

        if self.mock_mode:
            # Return mock review for testing
            return {
                "suggestions": [
                    {
                        "line_number": 1,
                        "suggestion": "Consider adding input validation for better robustness.",
                        "severity": "warning",
                        "category": "best_practice",
                        "confidence": 0.8
                    }
                ],
                "summary": "Mock review generated for testing purposes."
            }

        prompt = self._build_review_prompt(code_change, similar_reviews, style_guide_context)

        try:
            logger.debug(f"DEBUG: Generating review for {code_change.file_path}, similar_reviews_count: {len(similar_reviews)}")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert code reviewer. Always respond with valid JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=settings.temperature,
                max_tokens=settings.max_tokens,
                response_format={"type": "json_object"}  # Ensure JSON response
            )

            content = response.choices[0].message.content
            logger.debug(f"DEBUG: LLM response content length: {len(content)}")
            result = json.loads(content)

            logger.info(f"DEBUG: Generated review for {code_change.file_path}, suggestions_count: {len(result.get('suggestions', []))}")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"DEBUG: Failed to parse LLM response as JSON: {e}, content: {content[:500]}...")
            # Fallback response
            return {
                "suggestions": [],
                "summary": "Error generating review. Please try again."
            }
        except Exception as e:
            logger.error(f"DEBUG: Error generating review: {e}")
            raise
    
    def generate_summary(self, all_suggestions: List[ReviewSuggestion]) -> str:
        """Generate overall PR summary"""
        if not all_suggestions:
            return "No issues found. Code looks good!"
        
        # Group by severity
        errors = [s for s in all_suggestions if s.severity == "error"]
        warnings = [s for s in all_suggestions if s.severity == "warning"]
        info = [s for s in all_suggestions if s.severity == "info"]
        
        summary_parts = []
        if errors:
            summary_parts.append(f"{len(errors)} critical issue(s)")
        if warnings:
            summary_parts.append(f"{len(warnings)} warning(s)")
        if info:
            summary_parts.append(f"{len(info)} suggestion(s)")
        
        return f"Found {', '.join(summary_parts)}. Please review the detailed feedback below."