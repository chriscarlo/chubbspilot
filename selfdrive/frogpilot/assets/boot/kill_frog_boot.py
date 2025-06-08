#!/usr/bin/env python3
"""
Emergency boot logo killer - creates a black image to replace the frog.
This runs automatically during boot to eliminate the frog without SSH.
"""

import subprocess
from pathlib import Path

def create_black_boot_image():
    """Create a black boot image to replace the frog."""
    output_path = Path(__file__).parent / "black_boot.jpg"
    
    # Try multiple methods to create a black image
    methods_tried = []
    
    # Method 1: Try PIL/Pillow
    try:
        from PIL import Image
        img = Image.new('RGB', (2160, 1080), (0, 0, 0))
        img.save(str(output_path), 'JPEG', quality=1)
        print("✅ Created black boot image with PIL")
        return True
    except Exception as e:
        methods_tried.append(f"PIL failed: {e}")
    
    # Method 2: Try ImageMagick
    try:
        subprocess.run(['convert', '-size', '2160x1080', 'xc:black', str(output_path)], 
                      check=True, capture_output=True)
        print("✅ Created black boot image with ImageMagick")
        return True
    except Exception as e:
        methods_tried.append(f"ImageMagick failed: {e}")
    
    # Method 3: Create minimal valid black JPEG manually
    try:
        # This is a minimal valid 1x1 black JPEG that will be stretched
        black_jpeg_bytes = bytes([
            0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
            0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
            0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
            0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
            0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20,
            0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
            0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
            0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
            0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x14, 0x00, 0x01,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0xFF, 0xC4, 0x00, 0x14, 0x10, 0x01, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01, 0x00, 0x00, 0x3F, 0x00,
            0x7F, 0xFF, 0xD9
        ])
        
        with open(output_path, 'wb') as f:
            f.write(black_jpeg_bytes)
        print("✅ Created minimal black JPEG manually")
        return True
    except Exception as e:
        methods_tried.append(f"Manual JPEG creation failed: {e}")
    
    print("❌ All methods failed to create black boot image:")
    for method in methods_tried:
        print(f"   - {method}")
    return False

def main():
    """Main function called during boot."""
    print("🐸💀 AUTOMATIC FROG ELIMINATION STARTING...")
    
    # Create the black boot image
    if create_black_boot_image():
        # Update the path that will be used by frogpilot_functions.py
        black_image = Path(__file__).parent / "black_boot.jpg"
        
        # Also create it as chauffeur_boot_logo.png so the existing logic picks it up
        try:
            # Copy to expected filename
            import shutil
            chauffeur_logo = Path(__file__).parent / "chauffeur_boot_logo.png"
            shutil.copy(str(black_image), str(chauffeur_logo))
            print(f"✅ Created {chauffeur_logo}")
            
            # Also copy over the frog image directly
            frog_image = Path(__file__).parent.parent / "other_images/frogpilot_boot_logo.png"
            if frog_image.exists():
                shutil.copy(str(black_image), str(frog_image))
                print(f"✅ Replaced frog image at {frog_image}")
        except Exception as e:
            print(f"⚠️  Could not copy black image: {e}")
    
    print("🏁 Frog elimination attempt complete")

if __name__ == "__main__":
    main()