"""Single-frame face recognition kernel.

Pure-function surface so the recognition worker (Story 2.3) can call it
in a tight per-frame loop and Story 3.5's hot-reloader can swap registry
instances without restarting the worker process.
"""
