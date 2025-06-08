#!/usr/bin/env python3
"""Test script to verify boot logo displays correctly in terminal."""

import sys

# Our badass arcade-style logo
LOGO = """▓▓▓▓  ▓  ▓  ▓▓▓▓  ▓  ▓  ▓▓▓▓  ▓▓▓▓  ▓▓▓▓  ▓  ▓  ▓▓▓▓ 
▓     ▓  ▓  ▓  ▓  ▓  ▓  ▓     ▓     ▓     ▓  ▓  ▓  ▓ 
▓     ▓▓▓▓  ▓▓▓▓  ▓  ▓  ▓▓▓   ▓▓▓   ▓▓▓   ▓  ▓  ▓▓▓▓ 
▓     ▓▓▓▓  ▓▓▓▓  ▓  ▓  ▓▓▓   ▓▓▓   ▓▓▓   ▓  ▓  ▓▓▓▓ 
▓     ▓  ▓  ▓  ▓  ▓  ▓  ▓     ▓     ▓     ▓  ▓  ▓ ▓  
▓     ▓  ▓  ▓  ▓  ▓  ▓  ▓     ▓     ▓     ▓  ▓  ▓ ▓  
▓▓▓▓  ▓  ▓  ▓  ▓  ▓▓▓▓  ▓     ▓     ▓▓▓▓  ▓▓▓▓  ▓  ▓ 
▓▓▓▓  ▓  ▓  ▓  ▓  ▓▓▓▓  ▓     ▓     ▓▓▓▓  ▓▓▓▓  ▓  ▓ 
═══════════════════════════════════════════════════════
      ★ AUTONOMOUS DRIVING SYSTEM v2.0 ★
         ----------------------------"""

# ANSI color codes
SALMON_RED = "\033[38;2;255;105;105m"
WHITE = "\033[37m"
RESET = "\033[0m"

def test_display():
    """Display the logo with colors to verify it looks correct."""
    print("\nTesting Chauffeur boot logo display:\n")
    
    lines = LOGO.split('\n')
    for i, line in enumerate(lines):
        if '▓' in line:
            # Logo lines in salmon-red
            print(f"{SALMON_RED}{line}{RESET}")
        elif '═' in line or '─' in line:
            # Separator lines in white
            print(f"{WHITE}{line}{RESET}")
        elif '★' in line:
            # Tagline with red stars
            colored_line = line.replace('★', f'{SALMON_RED}★{WHITE}')
            print(f"{WHITE}{colored_line}{RESET}")
        else:
            # Other lines in white
            print(f"{WHITE}{line}{RESET}")
    
    print("\n✓ Logo display test complete!")
    print("  The logo should appear in salmon-red (#FF6969)")
    print("  with white separator lines and tagline.")

if __name__ == "__main__":
    test_display()