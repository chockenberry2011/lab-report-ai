"""
TEST_ROW Token Classifier Package

Within-line token classification micro-NER for parsing test result lines.
"""

__version__ = "1.0.0"

# Conditional imports to allow individual module execution without dependencies
try:
    from .token_classifier import (
        TestRowNER, 
        TOKEN_LABELS,
        TestRowTokenClassifier,
        TestRowDataset
    )
    from .rule_splitter import RuleBasedSplitter
    
    __all__ = [
        "TestRowNER",
        "TOKEN_LABELS", 
        "TestRowTokenClassifier",
        "TestRowDataset",
        "RuleBasedSplitter"
    ]
except ImportError:
    # Allow package to be imported even if dependencies are missing
    __all__ = []