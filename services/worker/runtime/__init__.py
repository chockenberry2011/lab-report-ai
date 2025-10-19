"""
Runtime inference modules for Lab AI Worker

Contains lightweight inference wrappers that lazy-load models and dependencies.
"""

from .roles_infer import predict_line_roles
from .testrow_infer import tag_testrow

__all__ = ["predict_line_roles", "tag_testrow"]