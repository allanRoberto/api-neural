# ========== patterns/__init__.py ==========
"""
Padrões de análise
"""

from patterns.base import BasePattern, PatternResult
from patterns.master import PatternMaster

__all__ = [
    'BasePattern',
    'PatternResult',
    'PatternMaster',
]