#!/bin/bash
# Start Xvfb in the background
Xvfb :99 -screen 0 1280x1024x24 &

# Give Xvfb a moment to start
sleep 2

# Execute the passed command (from CMD)
exec "$@"
