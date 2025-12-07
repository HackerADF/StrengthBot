"""
verbose.py - Lightweight verbose logging utility.

This module provides a simple logging interface for conditional verbose output,
intended for development and debugging purposes. Logging can be toggled via
a configuration file or dynamically using the set_logging function.

Public Interface:
    logging (bool)         - Flag to check if verbose logging is enabled.
    set_logging(bool)      - Enable or disable verbose logging at runtime.
    send(message: str)     - Print a verbose log message with timestamp.

Depends on:
    config.enableVerboseLogging - Boolean flag in a separate config module.

Designed by ADF
"""
from datetime import datetime

logging = False
PREFIX = "[VERBOSE]"
timestampEnabled = True

def set_logging(enabled: bool):
    global logging
    logging = enabled

def send(message):
    if logging:
        timestamp = datetime.now().isoformat(sep=' ', timespec='seconds')
        print(f"[{timestamp if timestampEnabled == True else None}] - {PREFIX} {message}")

def log(message):
    if logging:
        timestamp = datetime.now().isoformat(sep=' ', timespec='seconds')
        print(f"[{timestamp if timestampEnabled == True else None}] - {PREFIX} {message}")

def disable():
    global logging
    if logging:
        logging = False
        timestamp = datetime.now().isoformat(sep=' ', timespec='seconds')
        print(f"[{timestamp if timestampEnabled == True else None}] - {PREFIX} Logger disabled.")