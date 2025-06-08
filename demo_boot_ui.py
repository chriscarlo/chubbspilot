#!/usr/bin/env python3
"""
Standalone demo of the Chauffeur boot UI showing what it looks like
when everything works vs when there's an error.
"""

import time
import sys

# ANSI color codes
COLOR_RESET = "\033[0m"
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_CYAN = "\033[36m"
COLOR_WHITE = "\033[37m"
COLOR_SALMON = "\033[38;2;255;105;105m"
COLOR_DIM = "\033[2m"
STYLE_BOLD = "\033[1m"
CLEAR_SCREEN = "\033[2J"
CURSOR_HOME = "\033[H"

def clear_screen():
    print(CLEAR_SCREEN + CURSOR_HOME, end='')

def draw_header():
    print(COLOR_SALMON + STYLE_BOLD)
    print("▓▓▓▓  ▓  ▓  ▓▓▓▓  ▓  ▓  ▓▓▓▓  ▓▓▓▓  ▓▓▓▓  ▓  ▓  ▓▓▓▓")
    print("▓     ▓  ▓  ▓  ▓  ▓  ▓  ▓     ▓     ▓     ▓  ▓  ▓  ▓")
    print("▓     ▓▓▓▓  ▓▓▓▓  ▓  ▓  ▓▓▓   ▓▓▓   ▓▓▓   ▓  ▓  ▓▓▓▓")
    print("▓     ▓▓▓▓  ▓▓▓▓  ▓  ▓  ▓▓▓   ▓▓▓   ▓▓▓   ▓  ▓  ▓▓▓▓")
    print("▓     ▓  ▓  ▓  ▓  ▓  ▓  ▓     ▓     ▓     ▓  ▓  ▓ ▓ ")
    print("▓     ▓  ▓  ▓  ▓  ▓  ▓  ▓     ▓     ▓     ▓  ▓  ▓ ▓ ")
    print("▓▓▓▓  ▓  ▓  ▓  ▓  ▓▓▓▓  ▓     ▓     ▓▓▓▓  ▓▓▓▓  ▓  ▓")
    print("▓▓▓▓  ▓  ▓  ▓  ▓  ▓▓▓▓  ▓     ▓     ▓▓▓▓  ▓▓▓▓  ▓  ▓")
    print(COLOR_WHITE + "═══════════════════════════════════════════════════════")
    print(COLOR_SALMON + "      ★ AUTONOMOUS DRIVING SYSTEM v2.0 ★")
    print(COLOR_WHITE + "         ----------------------------" + COLOR_RESET)
    print()

def demo_normal_boot():
    """Demo of normal boot sequence."""
    clear_screen()
    draw_header()
    
    print(COLOR_CYAN + "[SYSTEM]" + COLOR_RESET + " Hardware Detection")
    print("  └─ Platform: " + COLOR_GREEN + "COMMA TICI (larch64)" + COLOR_RESET)
    print("  └─ Serial: " + COLOR_GREEN + "CCF123456789" + COLOR_RESET)
    print("  └─ IMEI: " + COLOR_GREEN + "359876543210987" + COLOR_RESET)
    print()
    
    services = [
        ("Thermal Manager", "thermald", 1.0),
        ("CAN Interface", "pandad", 0.5),
        ("Camera System", "camerad", 1.5),
        ("Vision Model", "modeld", 2.0),
        ("Vehicle Control", "controlsd", 0.5),
        ("User Interface", "ui", 1.0)
    ]
    
    print(COLOR_CYAN + "[SERVICES]" + COLOR_RESET + " Starting core processes:")
    
    # Show all services as pending
    for name, _, _ in services:
        print(f"  ├─ {name:<20} [ ]")
    
    # Animate service startup
    for i, (name, svc, delay) in enumerate(services):
        time.sleep(delay)
        # Redraw with updated status
        clear_screen()
        draw_header()
        
        print(COLOR_CYAN + "[SYSTEM]" + COLOR_RESET + " Hardware Detection")
        print("  └─ Platform: " + COLOR_GREEN + "COMMA TICI (larch64)" + COLOR_RESET)
        print("  └─ Serial: " + COLOR_GREEN + "CCF123456789" + COLOR_RESET)
        print("  └─ IMEI: " + COLOR_GREEN + "359876543210987" + COLOR_RESET)
        print()
        
        print(COLOR_CYAN + "[SERVICES]" + COLOR_RESET + " Starting core processes:")
        for j, (n, _, _) in enumerate(services):
            if j < i:
                print(f"  ├─ {n:<20} {COLOR_GREEN}[✓]{COLOR_RESET}")
            elif j == i:
                print(f"  ├─ {n:<20} {COLOR_YELLOW}[~]{COLOR_RESET} Starting...")
            else:
                print(f"  ├─ {n:<20} [ ]")
        
        print()
        progress = int((i + 1) / len(services) * 50)
        bar = COLOR_GREEN + "█" * progress + "░" * (50 - progress) + COLOR_RESET
        print(COLOR_CYAN + "[PROGRESS]" + COLOR_RESET + f" {bar} {(i+1)*100//len(services)}%")
        print(COLOR_CYAN + "[PHASE]" + COLOR_RESET + f" Starting {name}...")
    
    # Final state
    time.sleep(1)
    clear_screen()
    draw_header()
    print(COLOR_GREEN + STYLE_BOLD + "\n✓ BOOT COMPLETE - SYSTEM READY\n" + COLOR_RESET)
    print("All services started successfully!")
    print("Boot time: 6.5 seconds")

def demo_error_boot():
    """Demo of boot sequence with error."""
    clear_screen()
    draw_header()
    
    print(COLOR_CYAN + "[SERVICES]" + COLOR_RESET + " Starting core processes:")
    print(f"  ├─ Thermal Manager      {COLOR_GREEN}[✓]{COLOR_RESET}")
    print(f"  ├─ CAN Interface        {COLOR_GREEN}[✓]{COLOR_RESET}")
    print(f"  ├─ Camera System        {COLOR_GREEN}[✓]{COLOR_RESET}")
    print(f"  ├─ Vision Model         {COLOR_GREEN}[✓]{COLOR_RESET}")
    print(f"  ├─ Vehicle Control      {COLOR_RED}[✗]{COLOR_RESET} CAN Error: No messages received from panda")
    print(f"  ├─ Path Planning        {COLOR_RED}[✗]{COLOR_RESET} Dependency controlsd failed")
    print(f"  └─ User Interface       [ ]")
    print()
    
    print(COLOR_RED + STYLE_BOLD + "[ERRORS DETECTED]" + COLOR_RESET + " Boot halted due to failures:\n")
    
    print(COLOR_RED + "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" + COLOR_RESET)
    print(COLOR_RED + STYLE_BOLD + "FAILED: Vehicle Control" + COLOR_RESET)
    print(COLOR_YELLOW + "Error: " + COLOR_RESET + "RuntimeError: CAN Error: No messages received from panda")
    print(COLOR_CYAN + "Location: " + COLOR_RESET + "/data/openpilot/selfdrive/car/car_helpers.py:142")
    print()
    print(COLOR_DIM + "Stack Trace:" + COLOR_RESET)
    print(COLOR_CYAN + "  #0 File \"/data/openpilot/selfdrive/controls/controlsd.py\", line 742" + COLOR_RESET)
    print(COLOR_DIM + "     in main: controls = Controls(sm, pm, CP)" + COLOR_RESET)
    print(COLOR_CYAN + "  #1 File \"/data/openpilot/selfdrive/controls/controlsd.py\", line 168" + COLOR_RESET)
    print(COLOR_DIM + "     in __init__: self.CI = get_car_interface(self.CP)" + COLOR_RESET)
    print(COLOR_CYAN + "  #2 File \"/data/openpilot/selfdrive/car/car_helpers.py\", line 142" + COLOR_RESET)
    print(COLOR_DIM + "     in get_car_interface: raise RuntimeError(\"CAN Error: No messages received from panda\")" + COLOR_RESET)
    print()
    print(COLOR_GREEN + STYLE_BOLD + "SUGGESTED FIX:" + COLOR_RESET)
    print(COLOR_GREEN + "CAN communication issue. Check panda connection and power." + COLOR_RESET)
    print()
    
    print(COLOR_YELLOW + "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" + COLOR_RESET)
    print(COLOR_YELLOW + STYLE_BOLD + "DEBUGGING TIPS:" + COLOR_RESET)
    print("• Check " + COLOR_CYAN + "/data/log/" + COLOR_RESET + " for detailed logs")
    print("• Try: " + COLOR_CYAN + "cd /data/openpilot && ./launch_openpilot.sh" + COLOR_RESET)
    print("• Common issues: permissions, missing deps, CAN errors")
    print("• SSH will be available after thermald starts")
    print(COLOR_WHITE + "═══════════════════════════════════════════════════════" + COLOR_RESET)

if __name__ == "__main__":
    print("\n" + COLOR_SALMON + STYLE_BOLD + "CHAUFFEUR BOOT UI DEMO" + COLOR_RESET)
    print("======================\n")
    
    print("This demo shows what the boot screen looks like.\n")
    print("1. Normal boot sequence (6 seconds)")
    print("2. Boot with error condition\n")
    
    input("Press Enter to see normal boot sequence...")
    demo_normal_boot()
    
    print("\n")
    input("Press Enter to see error condition...")
    demo_error_boot()
    
    print("\n\n" + COLOR_GREEN + "Demo complete!" + COLOR_RESET)
    print("The frog is dead. Long live Chauffeur! 🔥\n")