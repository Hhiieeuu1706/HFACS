import time
import sys

# A simple script to create a delay.
# It takes the number of seconds as a command-line argument.

try:
    # Try to get the delay from the command-line argument
    delay_seconds = int(sys.argv[1])
    print(f"Waiting for {delay_seconds} seconds...")
    time.sleep(delay_seconds)
except (IndexError, ValueError):
    # If no argument is given or it's invalid, default to a 5-second delay
    print("No valid delay specified, waiting for 5 seconds by default...")
    time.sleep(5)
