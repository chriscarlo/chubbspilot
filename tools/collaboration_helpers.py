#!/usr/bin/env python3
"""
Helper functions for Claude-Gemini collaboration during development
"""

import sys
import os

# Add the persistent Python path as per CLAUDE.md
sys.path.insert(0, "/data/openpilot/.local/lib/python3.11/site-packages")
sys.path.insert(0, "/data/openpilot")

from tools.claude_gemini_collab import GeminiCollaborator

def get_gemini_perspective(question: str, context: str = "") -> str:
    """Quick function to get Gemini's input on something"""
    try:
        gemini = GeminiCollaborator()
        return gemini.ask_gemini(question, context)
    except Exception as e:
        return f"Gemini unavailable: {str(e)}"

def get_second_opinion(my_analysis: str, question: str) -> str:
    """Get Gemini's take on my analysis"""
    try:
        gemini = GeminiCollaborator()
        return gemini.collaborative_analysis(my_analysis, question)
    except Exception as e:
        return f"Gemini unavailable: {str(e)}"

def dual_code_review(code: str, focus: str = "general quality") -> dict:
    """Get both my analysis and Gemini's review"""
    # Claude's analysis (placeholder - in real use, this would be my actual analysis)
    claude_review = "I would analyze the code structure, logic, and potential issues..."
    
    try:
        gemini = GeminiCollaborator()
        gemini_review = gemini.code_review(code, focus)
        
        return {
            "claude": claude_review,
            "gemini": gemini_review
        }
    except Exception as e:
        return {
            "claude": claude_review,
            "gemini": f"Gemini unavailable: {str(e)}"
        }

def collaborative_brainstorm(problem: str, constraints: str = "") -> dict:
    """Get brainstorming ideas from both AIs"""
    try:
        gemini = GeminiCollaborator()
        gemini_ideas = gemini.brainstorm_solutions(problem, constraints)
        
        return {
            "claude": "I would focus on practical implementation and existing patterns in the codebase...",
            "gemini": gemini_ideas
        }
    except Exception as e:
        return {
            "claude": "I would focus on practical implementation and existing patterns in the codebase...",
            "gemini": f"Gemini unavailable: {str(e)}"
        }