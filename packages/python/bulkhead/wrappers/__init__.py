"""Optional SDK wrappers.

Each wrapper imports its third-party SDK lazily (inside the module) so the
bulkhead core never requires openai / anthropic to be installed.
Install the extra you need, e.g. ``pip install bulkhead-ai[openai]``.
"""
