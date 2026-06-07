"""Optional scorer/judge backends.

The core package has zero runtime dependencies. Each backend in this package
imports its heavy dependency lazily (inside the factory), so importing
``bulkhead`` never pulls onnxruntime / llama-cpp / an HTTP client. Backends
register themselves with :mod:`bulkhead.scorers.registry` when imported.
"""
