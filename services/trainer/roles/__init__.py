"""
Line Role Classifier Package

Machine learning classifier for medical document line roles.
"""

__version__ = "1.0.0"

# Conditional imports to allow individual module execution without dependencies
try:
    from .line_classifier import (
        LineRoleClassifier, 
        LineData, 
        FeatureExtractor,
        ROLE_LABELS,
        calculate_y_tertile,
        detect_header_hints
    )
    
    __all__ = [
        "LineRoleClassifier",
        "LineData", 
        "FeatureExtractor",
        "ROLE_LABELS",
        "calculate_y_tertile",
        "detect_header_hints"
    ]
except ImportError:
    # Allow package to be imported even if dependencies are missing
    __all__ = []