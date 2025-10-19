"""
Runtime inference module for line role classification

Loads the pre-trained model and provides inference without importing training dependencies.
"""

import os
import json
import pickle
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)

# Lightweight data structures
@dataclass
class Line:
    """Simplified line data for inference"""
    text: str
    y_tertile: int = 0  # 0=bottom, 1=middle, 2=top
    is_bold: bool = False
    is_header_hint: bool = False
    font_size: float = 12.0
    x_left: float = 0.0
    width: float = 100.0
    page: int = 1

@dataclass
class RoleProb:
    """Role prediction with probability"""
    line_text: str
    predicted_role: str
    probabilities: Dict[str, float]
    confidence: float

# Global model cache
_model_cache = {}

def _lazy_load_dependencies():
    """Lazy import heavy dependencies"""
    try:
        import joblib
        import numpy as np
        from sklearn.preprocessing import StandardScaler, LabelEncoder
        return joblib, np, StandardScaler, LabelEncoder
    except ImportError as e:
        raise ImportError(f"Required dependencies not available for role inference: {e}")

def _lazy_load_sentence_transformer():
    """Lazy import sentence transformer"""
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer
    except ImportError:
        return None

def _extract_features(lines: List[Line]) -> Any:
    """Extract features from lines without importing training modules"""
    joblib, np, StandardScaler, LabelEncoder = _lazy_load_dependencies()
    
    # Basic structural features
    structural_features = []
    texts = []
    
    for line in lines:
        # Structural features
        features = [
            line.y_tertile,
            int(line.is_bold),
            int(line.is_header_hint),
            line.font_size,
            line.x_left,
            line.width
        ]
        structural_features.append(features)
        texts.append(line.text)
    
    structural_features = np.array(structural_features)
    
    # Try to get embeddings if sentence_transformers is available
    SentenceTransformer = _lazy_load_sentence_transformer()
    if SentenceTransformer is not None:
        try:
            # Use cached model or load default
            if 'sentence_transformer' not in _model_cache:
                _model_cache['sentence_transformer'] = SentenceTransformer('all-MiniLM-L6-v2')
            
            embeddings = _model_cache['sentence_transformer'].encode(texts)
            features = np.hstack([embeddings, structural_features])
        except Exception:
            # Fallback to just structural features with padding
            embedding_dim = 384  # Default for all-MiniLM-L6-v2
            zero_embeddings = np.zeros((len(lines), embedding_dim))
            features = np.hstack([zero_embeddings, structural_features])
    else:
        # No sentence transformers available, use zero embeddings
        embedding_dim = 384  # Default for all-MiniLM-L6-v2
        zero_embeddings = np.zeros((len(lines), embedding_dim))
        features = np.hstack([zero_embeddings, structural_features])
    
    return features

def _load_role_model(model_path: str) -> Dict[str, Any]:
    """Load the role classification model from disk"""
    joblib, np, StandardScaler, LabelEncoder = _lazy_load_dependencies()
    
    model_dir = Path(model_path)
    if not model_dir.exists():
        raise FileNotFoundError(f"Model directory not found: {model_dir}")
    
    # Load metadata
    metadata_path = model_dir / "metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"Metadata file not found: {metadata_path}")
    
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)
    
    embedding_model = metadata.get('embedding_model', 'sbert')
    
    if embedding_model == "tfidf":
        # Load the complete model from joblib (contains classifier + vectorizer)
        model_path_file = model_dir / "model.joblib"
        if not model_path_file.exists():
            raise FileNotFoundError(f"Model file not found: {model_path_file}")
        
        model = joblib.load(model_path_file)
        logger.info(f"roles: loaded tfidf model from {model_dir}")
        
        return {
            'complete_model': model,
            'metadata': metadata,
            'is_tfidf': True
        }
    else:
        # Legacy SBERT model format - load separate components
        classifier = joblib.load(model_dir / "classifier.pkl")
        scaler = joblib.load(model_dir / "scaler.pkl") 
        label_encoder = joblib.load(model_dir / "label_encoder.pkl")
        logger.info(f"roles: loaded {embedding_model} model from {model_dir}")
        
        return {
            'classifier': classifier,
            'scaler': scaler,
            'label_encoder': label_encoder,
            'metadata': metadata,
            'is_tfidf': False
        }

def predict_line_roles(lines: List[Line], model_path: str = "/models/roles") -> List[RoleProb]:
    """
    Predict line roles with probabilities
    
    Args:
        lines: List of Line objects to classify
        model_path: Path to the trained model directory
        
    Returns:
        List of RoleProb objects with predictions and probabilities
    """
    if not lines:
        return []
    
    try:
        # Load model (with caching)
        cache_key = f"role_model_{model_path}"
        if cache_key not in _model_cache:
            _model_cache[cache_key] = _load_role_model(model_path)
        
        model_data = _model_cache[cache_key]
        
        if model_data.get('is_tfidf', False):
            # Use the complete TF-IDF model
            complete_model = model_data['complete_model']
            
            # Convert lines to the format expected by the trained model
            from services.trainer.roles.line_classifier import LineData
            line_data_objects = []
            for line in lines:
                line_data_objects.append(LineData(
                    text=line.text,
                    y_tertile=line.y_tertile,
                    is_bold=line.is_bold,
                    is_header_hint=line.is_header_hint,
                    role='UNKNOWN',  # Will be predicted
                    page=line.page,
                    x_left=line.x_left,
                    x_right=line.x_left + line.width,
                    y_norm=0.0,  # Not used in current feature extraction
                    font_size=line.font_size
                ))
            
            # Predict using the complete model
            predictions = complete_model.predict(line_data_objects)
            probabilities = complete_model.predict_proba(line_data_objects)
            
            # Get label encoder from the model
            label_encoder = complete_model.label_encoder
            
        else:
            # Legacy SBERT model format
            classifier = model_data['classifier']
            scaler = model_data['scaler']
            label_encoder = model_data['label_encoder']
            
            # Extract features
            features = _extract_features(lines)
            
            # Scale features
            features_scaled = scaler.transform(features)
            
            # Predict
            predictions = classifier.predict(features_scaled)
            probabilities = classifier.predict_proba(features_scaled)
        
        # Convert to RoleProb objects
        results = []
        for i, line in enumerate(lines):
            if model_data.get('is_tfidf', False):
                pred_role = predictions[i]
            else:
                pred_role = label_encoder.inverse_transform([predictions[i]])[0]
            
            # Create probability dict
            prob_dict = {}
            max_prob = 0.0
            for j, class_name in enumerate(label_encoder.classes_):
                prob = float(probabilities[i][j])
                prob_dict[class_name] = prob
                max_prob = max(max_prob, prob)
            
            results.append(RoleProb(
                line_text=line.text,
                predicted_role=pred_role,
                probabilities=prob_dict,
                confidence=max_prob
            ))
        
        return results
        
    except Exception as e:
        logger.warning(f"Role prediction failed: {e} - using fallback")
        # Fallback to simple heuristic classification
        return _fallback_role_classification(lines)

def _fallback_role_classification(lines: List[Line]) -> List[RoleProb]:
    """Simple rule-based fallback when model loading fails"""
    results = []
    
    for line in lines:
        text = line.text.strip().lower()
        
        # Simple heuristics
        if line.is_header_hint or line.y_tertile == 2:
            role = 'HEADER_PATIENT' if any(word in text for word in ['patient', 'name', 'dob', 'id']) else 'SECTION_PANEL'
        elif line.y_tertile == 0:
            role = 'PAGE_FOOTER'
        elif any(word in text for word in ['test', 'result', 'value']):
            role = 'TEST_ROW'
        elif text.startswith('#') or 'comment' in text:
            role = 'COMMENT'
        else:
            role = 'SECTION_MISC'
        
        results.append(RoleProb(
            line_text=line.text,
            predicted_role=role,
            probabilities={role: 0.8, 'OTHER': 0.2},
            confidence=0.8
        ))
    
    return results