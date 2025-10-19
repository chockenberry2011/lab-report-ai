"""
Runtime inference module for test row token classification

Loads the pre-trained model and provides inference without importing training dependencies.
"""

import os
import json
import re
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

@dataclass
class TokenTag:
    """Token with its predicted tag"""
    token: str
    tag: str
    confidence: float
    start_pos: int
    end_pos: int

# Token labels for TEST_ROW NER
TOKEN_LABELS = [
    'O',           # Outside/Other
    'B-TEST_NAME', # Beginning of test name
    'I-TEST_NAME', # Inside test name
    'B-VALUE',     # Beginning of value
    'I-VALUE',     # Inside value
    'B-UNIT',      # Beginning of unit
    'I-UNIT',      # Inside unit
    'B-REF_RANGE', # Beginning of reference range
    'I-REF_RANGE', # Inside reference range
    'B-FLAG',      # Beginning of flag
    'I-FLAG'       # Inside flag
]

# Global model cache
_model_cache = {}

def _lazy_load_dependencies():
    """Lazy import heavy dependencies"""
    try:
        import torch
        import joblib
        import numpy as np
        return torch, joblib, np
    except ImportError as e:
        raise ImportError(f"Required dependencies not available for testrow inference: {e}")

def _lazy_load_transformers():
    """Lazy import transformers"""
    try:
        from transformers import AutoTokenizer, AutoModel
        return AutoTokenizer, AutoModel
    except ImportError:
        return None, None

def _load_testrow_model(model_path: str) -> Dict[str, Any]:
    """Load the testrow classification model from disk"""
    torch, joblib, np = _lazy_load_dependencies()
    
    model_dir = Path(model_path)
    if not model_dir.exists():
        raise FileNotFoundError(f"Model directory not found: {model_dir}")
    
    # Load metadata
    with open(model_dir / "metadata.json", 'r') as f:
        metadata = json.load(f)
    
    # Load label encoder
    label_encoder = joblib.load(model_dir / "label_encoder.pkl")
    
    # Try to load the PyTorch model
    AutoTokenizer, AutoModel = _lazy_load_transformers()
    if AutoTokenizer is not None and AutoModel is not None:
        try:
            # Load tokenizer and model
            tokenizer = AutoTokenizer.from_pretrained(model_dir / "tokenizer")
            model = torch.load(model_dir / "model.pt", map_location='cpu')
            model.eval()
            
            return {
                'model': model,
                'tokenizer': tokenizer,
                'label_encoder': label_encoder,
                'metadata': metadata,
                'has_model': True
            }
        except Exception as e:
            print(f"Failed to load PyTorch model: {e}")
    
    # Fallback to just label encoder
    return {
        'model': None,
        'tokenizer': None,
        'label_encoder': label_encoder,
        'metadata': metadata,
        'has_model': False
    }

def _simple_tokenize(text: str) -> List[Tuple[str, int, int]]:
    """Simple whitespace tokenization with positions"""
    tokens = []
    start = 0
    
    for match in re.finditer(r'\S+', text):
        token = match.group()
        start_pos = match.start()
        end_pos = match.end()
        tokens.append((token, start_pos, end_pos))
    
    return tokens

def tag_testrow(text: str, model_path: str = "/models/testrow") -> List[TokenTag]:
    """
    Tag tokens in a test row with semantic labels
    
    Args:
        text: Test row text to tag
        model_path: Path to the trained model directory
        
    Returns:
        List of TokenTag objects with predictions
    """
    if not text or not text.strip():
        return []
    
    try:
        # Load model (with caching)
        cache_key = f"testrow_model_{model_path}"
        if cache_key not in _model_cache:
            _model_cache[cache_key] = _load_testrow_model(model_path)
        
        model_data = _model_cache[cache_key]
        
        if model_data['has_model']:
            return _predict_with_model(text, model_data)
        else:
            return _predict_with_fallback(text)
            
    except Exception as e:
        print(f"Model loading failed: {e}")
        return _predict_with_fallback(text)

def _predict_with_model(text: str, model_data: Dict[str, Any]) -> List[TokenTag]:
    """Predict using the loaded PyTorch model"""
    torch, joblib, np = _lazy_load_dependencies()
    
    model = model_data['model']
    tokenizer = model_data['tokenizer']
    label_encoder = model_data['label_encoder']
    
    # Tokenize text
    words = text.split()
    tokenized = tokenizer(
        words,
        is_split_into_words=True,
        return_tensors='pt',
        padding=True,
        truncation=True,
        max_length=512
    )
    
    # Get word ids for alignment
    word_ids = tokenized.word_ids()
    
    # Predict
    with torch.no_grad():
        outputs = model(**tokenized)
        logits = outputs['logits'] if hasattr(outputs, 'logits') else outputs[0]
        predictions = torch.argmax(logits, dim=2)[0].cpu().numpy()
    
    # Align predictions back to words
    word_predictions = []
    previous_word_idx = None
    
    for i, word_idx in enumerate(word_ids):
        if word_idx is not None and word_idx != previous_word_idx:
            pred_label = label_encoder.inverse_transform([predictions[i]])[0]
            confidence = torch.softmax(logits[0][i], dim=0).max().item()
            word_predictions.append((pred_label, confidence))
            previous_word_idx = word_idx
    
    # Convert to TokenTag objects with positions
    tokens_with_pos = _simple_tokenize(text)
    results = []
    
    for i, (token, start_pos, end_pos) in enumerate(tokens_with_pos):
        if i < len(word_predictions):
            tag, confidence = word_predictions[i]
        else:
            tag, confidence = 'O', 0.5
        
        results.append(TokenTag(
            token=token,
            tag=tag,
            confidence=confidence,
            start_pos=start_pos,
            end_pos=end_pos
        ))
    
    return results

def _predict_with_fallback(text: str) -> List[TokenTag]:
    """Rule-based fallback when model is not available"""
    tokens_with_pos = _simple_tokenize(text)
    results = []
    
    for i, (token, start_pos, end_pos) in enumerate(tokens_with_pos):
        # Simple heuristic tagging
        token_lower = token.lower()
        
        if i == 0:
            # First token likely test name
            tag = 'B-TEST_NAME'
        elif re.match(r'^\d+\.?\d*$', token):
            # Numbers likely values
            tag = 'B-VALUE' if i == 0 or results[i-1].tag not in ['B-VALUE', 'I-VALUE'] else 'I-VALUE'
        elif token_lower in ['mg/dl', 'mmol/l', 'u/l', 'g/l', '%', 'mm', 'cm']:
            # Units
            tag = 'B-UNIT'
        elif re.match(r'^\d+\.?\d*\s*-\s*\d+\.?\d*$', token):
            # Reference ranges
            tag = 'B-REF_RANGE'
        elif token_lower in ['high', 'low', 'normal', 'abnormal', 'h', 'l', 'n', '*']:
            # Flags
            tag = 'B-FLAG'
        else:
            # Continue previous tag or default to outside
            prev_tag = results[i-1].tag if i > 0 else 'O'
            if prev_tag.startswith('B-'):
                tag = 'I-' + prev_tag[2:]
            elif prev_tag.startswith('I-'):
                tag = prev_tag
            else:
                tag = 'O'
        
        results.append(TokenTag(
            token=token,
            tag=tag,
            confidence=0.7,  # Default confidence for rule-based
            start_pos=start_pos,
            end_pos=end_pos
        ))
    
    return results