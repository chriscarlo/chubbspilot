#!/bin/bash
# Test script to check terminal environment settings

echo "=== Terminal Environment Check ==="
echo
echo "Shell: $SHELL"
echo "Bash version: $BASH_VERSION"
echo
echo "=== History Settings ==="
echo "HISTFILE: $HISTFILE"
echo "HISTSIZE: $HISTSIZE"
echo "HISTFILESIZE: $HISTFILESIZE"
echo "HISTCONTROL: $HISTCONTROL"
echo "PROMPT_COMMAND: $PROMPT_COMMAND"
echo
echo "=== History File Check ==="
if [ -f "$HISTFILE" ]; then
    echo "History file exists: $HISTFILE"
    echo "File size: $(ls -lh "$HISTFILE" | awk '{print $5}')"
    echo "Line count: $(wc -l < "$HISTFILE")"
    echo "Last 5 lines:"
    tail -5 "$HISTFILE" | sed 's/^/  /'
else
    echo "History file NOT found: $HISTFILE"
fi
echo
echo "=== Current History ==="
echo "In-memory history count: $(history | wc -l)"
echo "Last 5 commands:"
history | tail -5 | sed 's/^/  /'