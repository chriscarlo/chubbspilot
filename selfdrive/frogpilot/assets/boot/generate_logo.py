#!/usr/bin/env python3
"""
Generate Chauffeur ASCII boot logo as PNG for plymouth boot screen.
Creates a retro 1985-style terminal display with venetian blind effect.
"""

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("PIL not available. Logo generation skipped.")
    import sys
    sys.exit(0)
import os
from pathlib import Path

# Configuration
LOGO_TEXT = """▓▓▓▓  ▓  ▓  ▓▓▓▓  ▓  ▓  ▓▓▓▓  ▓▓▓▓  ▓▓▓▓  ▓  ▓  ▓▓▓▓ 
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

# Colors
BACKGROUND = (0, 0, 0)  # Pure black
SALMON_RED = (255, 105, 105)  # #FF6969 - that perfect salmon-red
ACCENT_COLOR = (255, 127, 127)  # Slightly lighter for effects
SCANLINE_COLOR = (0, 0, 0, 25)  # Subtle scanline effect

# Resolutions to generate
RESOLUTIONS = {
    '720p': (1280, 720),
    '1080p': (1920, 1080),
    '4k': (3840, 2160)
}

def add_scanline_effect(img):
    """Add CRT-style scanlines for that authentic 1985 feel."""
    draw = ImageDraw.Draw(img, 'RGBA')
    height = img.height
    
    # Draw thin horizontal scanlines
    for y in range(0, height, 4):
        draw.line([(0, y), (img.width, y)], fill=SCANLINE_COLOR, width=1)
    
    return img

def add_glow_effect(img, text_bounds):
    """Add subtle glow around text for that phosphor monitor effect."""
    # This would require more complex image processing
    # For now, we'll keep it simple
    return img

def generate_logo(resolution_name, width, height):
    """Generate boot logo at specified resolution."""
    # Create base image
    img = Image.new('RGB', (width, height), BACKGROUND)
    draw = ImageDraw.Draw(img)
    
    # Try to use a monospace font, fallback to default if not available
    try:
        # Try common monospace fonts
        font_size = int(height * 0.04)  # Scale font with resolution
        font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf", font_size)
    except:
        # Fallback to default font
        font = ImageFont.load_default()
    
    # Calculate text position (centered)
    text_lines = LOGO_TEXT.split('\n')
    line_height = font_size * 1.2
    total_height = len(text_lines) * line_height
    
    start_y = (height - total_height) // 2
    
    # Draw each line
    for i, line in enumerate(text_lines):
        # Get text bounds
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        
        # Center horizontally
        x = (width - text_width) // 2
        y = start_y + (i * line_height)
        
        # Draw text with salmon-red color
        draw.text((x, y), line, fill=SALMON_RED, font=font)
    
    # Add effects
    img = add_scanline_effect(img)
    
    # Save the image
    output_dir = Path(__file__).parent
    output_path = output_dir / f"chauffeur_boot_logo_{resolution_name}.png"
    img.save(output_path, 'PNG')
    print(f"Generated: {output_path}")
    
    # Also save the main version that will be used
    if resolution_name == '1080p':
        main_path = output_dir / "chauffeur_boot_logo.png"
        img.save(main_path, 'PNG')
        print(f"Generated main logo: {main_path}")

def main():
    """Generate all logo variants."""
    print("Generating Chauffeur boot logos...")
    
    # Create output directory if it doesn't exist
    output_dir = Path(__file__).parent
    output_dir.mkdir(exist_ok=True)
    
    # Generate logos for each resolution
    for name, (width, height) in RESOLUTIONS.items():
        generate_logo(name, width, height)
    
    print("\nBoot logo generation complete!")
    print("The salmon-red (#FF6969) ASCII art is ready to replace that frog!")

if __name__ == "__main__":
    main()