#!/usr/bin/env python3
"""
Claude-Gemini Collaboration Tool
Simple direct API integration for Claude to work with Gemini
"""

import sys
import os

# Add the persistent Python path as per CLAUDE.md
sys.path.insert(0, "/data/openpilot/.local/lib/python3.11/site-packages")
sys.path.insert(0, "/data/openpilot")

import google.generativeai as genai
from typing import Optional

class GeminiCollaborator:
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Gemini API client"""
        self.api_key = api_key or os.environ.get('GEMINI_API_KEY')
        
        # Try to read from persistent storage if not provided
        if not self.api_key:
            secrets_paths = [
                "/persist/comma/gemini_api_key",  # Persistent secrets location
            ]
            for path in secrets_paths:
                try:
                    with open(path, 'r') as f:
                        self.api_key = f.read().strip()
                        break
                except FileNotFoundError:
                    continue
        
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found in environment or persistent storage")
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-2.5-pro-preview-06-05')
    
    def ask_gemini(self, prompt: str, context: str = "") -> str:
        """Ask Gemini a question with optional context"""
        full_prompt = f"{context}\n\n{prompt}" if context else prompt
        
        try:
            response = self.model.generate_content(full_prompt)
            return response.text
        except Exception as e:
            return f"Error from Gemini: {str(e)}"
    
    def code_review(self, code: str, focus_areas: str = "general quality") -> str:
        """Get Gemini's code review"""
        prompt = f"""
Please review this code focusing on {focus_areas}:

```
{code}
```

Provide specific feedback on:
1. Potential issues or bugs
2. Code quality and best practices
3. Security concerns
4. Suggestions for improvement
"""
        return self.ask_gemini(prompt)
    
    def collaborative_analysis(self, claude_analysis: str, question: str) -> str:
        """Get Gemini's perspective on Claude's analysis"""
        prompt = f"""
Claude (another AI) provided this analysis:

{claude_analysis}

Now I'd like your perspective on: {question}

Please provide your own independent analysis and note where you agree/disagree with Claude's points.
"""
        return self.ask_gemini(prompt)
    
    def brainstorm_solutions(self, problem: str, constraints: str = "") -> str:
        """Brainstorm solutions with Gemini"""
        prompt = f"""
Problem: {problem}

{f'Constraints: {constraints}' if constraints else ''}

Please brainstorm 3-5 different approaches to solve this problem. 
For each approach, briefly explain:
- The core idea
- Main advantages
- Potential drawbacks
- Implementation complexity (1-5 scale)
"""
        return self.ask_gemini(prompt)


def main():
    """CLI interface for testing"""
    if len(sys.argv) < 2:
        print("Usage: python3 claude_gemini_collab.py <command> [args...]")
        print("Commands:")
        print("  ask 'question'")
        print("  review 'code'")
        print("  brainstorm 'problem'")
        return
    
    try:
        gemini = GeminiCollaborator()
        command = sys.argv[1]
        
        if command == "ask" and len(sys.argv) >= 3:
            response = gemini.ask_gemini(sys.argv[2])
            print(f"Gemini: {response}")
            
        elif command == "review" and len(sys.argv) >= 3:
            response = gemini.code_review(sys.argv[2])
            print(f"Gemini Code Review:\n{response}")
            
        elif command == "brainstorm" and len(sys.argv) >= 3:
            response = gemini.brainstorm_solutions(sys.argv[2])
            print(f"Gemini Brainstorm:\n{response}")
            
        else:
            print("Invalid command or missing arguments")
            
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()