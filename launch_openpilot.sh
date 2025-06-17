#!/usr/bin/bash

# Run SSH fix in background to not block boot
if [ -f "./fix_agnos_ssh.sh" ]; then
  ./fix_agnos_ssh.sh &
fi

exec ./launch_chffrplus.sh
