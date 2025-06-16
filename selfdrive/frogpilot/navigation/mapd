#!/usr/bin/env python3
"""
Stub mapd for x86_64 development environments.
This prevents boot hangs when the real ARM64 mapd binary isn't available.
"""
import time
import sys

def main():
    print("mapd stub running (x86_64 development mode)", file=sys.stderr)
    # Just sleep forever to simulate mapd running
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("mapd stub shutting down", file=sys.stderr)

if __name__ == "__main__":
    main()