"""Lógica de domínio pura, sem dependência de banco/HTTP.

Reutilizável por qualquer módulo (importador Monday, API viva, jobs
futuros). Nada aqui deve importar de `app.modules.*` ou `app.models`.
"""
