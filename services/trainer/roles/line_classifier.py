"""
Line role classifier for medical documents

Classifies lines into roles like headers, test rows, comments, etc.
"""

import os
import json
import pickle
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Environment flag to disable sentence embeddings (useful for offline environments)
USE_SBERT = os.getenv("ROLES_USE_SBERT", "1") not in ("0", "false", "False")

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from scipy.sparse import hstack, csr_matrix
import joblib

# Define role labels
ROLE_LABELS = [
    'PAGE_HEADER',
    'PAGE_FOOTER',
    # Enhanced patient header categories
    'HEADER_PATIENT_NAME',      # "Patient: DOE, JOHN", "Name: Smith, Jane"
    'HEADER_PATIENT_DEMO',      # "DOB: 01/01/1960 SEX: M", "MRN: A123456 Age: 45"
    'HEADER_PATIENT_CONTACT',   # "123 Main St, City, ST 12345", "Phone: (555) 123-4567"
    # Provider/ordering information
    'HEADER_ORDERING',          # "Ordering Physician: Dr. Smith", "NPI: 1234567890"
    # Lab/facility information
    'HEADER_LAB',               # "Performing Laboratory: LabCorp", "CLIA: 11D1234567"
    'HEADER_MEDICAL_DIRECTOR',  # "Medical Director: Robert Johnson, MD", "Lab Director: Sarah Wilson, PhD", "Board Certified Clinical Pathology"
    # Specimen (keep existing)
    'HEADER_SPECIMEN',          # "Accession: 123 Collected: 01/01/2024"
    # Clinical requirements
    'TEST_FASTING_REQ',         # "12-hour fast required", "Fasting specimen", "Patient should fast 12 hours before collection"
    # Core content
    'SECTION_PANEL',
    'TEST_ROW',
    # System/layout (keep existing)
    'COMMENT',
    'SECTION_MISC',
    'JUNK'
]


@dataclass
class LineData:
    """Represents a single line with features and label"""
    text: str
    y_tertile: int  # 0=bottom, 1=middle, 2=top
    is_bold: bool
    is_header_hint: bool
    role: str
    page: int = 1
    x_left: float = 0.0
    x_right: float = 0.0
    y_norm: float = 0.0
    font_size: float = 12.0


class FeatureExtractor:
    """
    Two-mode text featurizer:
      - embedding_model == "tfidf": pure local TF-IDF (no huggingface)
      - embedding_model == any other string (e.g. "all-MiniLM-L6-v2"): SBERT via sentence-transformers (optional)
    """
    def __init__(self, embedding_model: str = "tfidf"):
        self.embedding_model = (embedding_model or "tfidf").lower()
        self._use_tfidf = self.embedding_model == "tfidf"
        self.vectorizer: TfidfVectorizer | None = None
        self.sentence_model = None
        self._curr_records = None  # for numeric side-features

    def load_embedding_model(self):
        if self._use_tfidf:
            if self.vectorizer is None:
                self.vectorizer = TfidfVectorizer(
                    ngram_range=(1, 2),
                    max_features=20000,
                    lowercase=True,
                    strip_accents="unicode",
                )
            print("Embedding model: TF-IDF (offline)")
            return
        # SBERT path (import only if needed)
        print(f"Embedding model: SBERT '{self.embedding_model}'")
        from sentence_transformers import SentenceTransformer
        self.sentence_model = SentenceTransformer(self.embedding_model)

    def _numeric_features(self):
        y = np.array([getattr(x, "y_tertile", 0) for x in self._curr_records]).reshape(-1, 1)
        b = np.array([1 if getattr(x, "is_bold", False) else 0 for x in self._curr_records]).reshape(-1, 1)
        h = np.array([1 if getattr(x, "is_header_hint", False) else 0 for x in self._curr_records]).reshape(-1, 1)
        return csr_matrix(np.hstack([y, b, h]))

    def fit_transform(self, lines):
        self._curr_records = lines
        texts = [getattr(x, "text", "") or "" for x in lines]
        self.load_embedding_model()
        if self._use_tfidf:
            text_emb = self.vectorizer.fit_transform(texts)
        else:
            arr = self.sentence_model.encode(texts, normalize_embeddings=True)
            text_emb = csr_matrix(arr)
        return hstack([text_emb, self._numeric_features()])

    def transform(self, lines):
        self._curr_records = lines
        texts = [getattr(x, "text", "") or "" for x in lines]
        if self._use_tfidf:
            text_emb = self.vectorizer.transform(texts)
        else:
            arr = self.sentence_model.encode(texts, normalize_embeddings=True)
            text_emb = csr_matrix(arr)
        return hstack([text_emb, self._numeric_features()])


class LineRoleClassifier:
    """Main classifier for line roles"""
    
    def __init__(self, model_type: str = "logistic", embedding_model: str = "tfidf"):
        self.model_type = model_type
        self.embedding_model = (embedding_model or "tfidf").lower()
        self.feature_extractor = FeatureExtractor(embedding_model=self.embedding_model)
        self.label_encoder = LabelEncoder()
        self.model = None
        self.is_fitted = False
        
        # Initialize model
        if model_type == "logistic":
            self.model = LogisticRegression(
                random_state=42,
                max_iter=1000,
                class_weight='balanced'
            )
        elif model_type == "random_forest":
            self.model = RandomForestClassifier(
                n_estimators=100,
                random_state=42,
                class_weight='balanced'
            )
        else:
            raise ValueError(f"Unsupported model type: {model_type}")
    
    def fit(self, lines: List[LineData]) -> 'LineRoleClassifier':
        """Train the classifier"""
        print(f"Training {self.model_type} classifier on {len(lines)} lines...")
        
        # Extract features
        X = self.feature_extractor.fit_transform(lines)
        
        # Encode labels
        y_labels = [line.role for line in lines]
        y = self.label_encoder.fit_transform(y_labels)
        
        # Train model
        self.model.fit(X, y)
        self.is_fitted = True
        
        print("Training completed")
        return self
    
    def predict(self, lines: List[LineData]) -> List[str]:
        """Predict roles for lines"""
        if not self.is_fitted:
            raise ValueError("Classifier must be fitted first")
        
        X = self.feature_extractor.transform(lines)
        y_pred = self.model.predict(X)
        
        # Decode labels
        roles = self.label_encoder.inverse_transform(y_pred)
        return list(roles)
    
    def predict_proba(self, lines: List[LineData]) -> np.ndarray:
        """Predict role probabilities for lines"""
        if not self.is_fitted:
            raise ValueError("Classifier must be fitted first")
        
        X = self.feature_extractor.transform(lines)
        return self.model.predict_proba(X)
    
    def evaluate(self, lines: List[LineData]) -> Dict[str, Any]:
        """Evaluate classifier on test data"""
        if not self.is_fitted:
            raise ValueError("Classifier must be fitted first")
        
        X = self.feature_extractor.transform(lines)
        y_true_labels = [line.role for line in lines]
        y_true = self.label_encoder.transform(y_true_labels)
        
        y_pred = self.model.predict(X)
        y_pred_labels = self.label_encoder.inverse_transform(y_pred)
        
        # Calculate metrics
        report = classification_report(
            y_true_labels, y_pred_labels, 
            output_dict=True, 
            zero_division=0
        )
        
        confusion = confusion_matrix(y_true, y_pred)
        
        # Calculate accuracy
        accuracy = np.mean(y_true == y_pred)
        
        return {
            'accuracy': accuracy,
            'classification_report': report,
            'confusion_matrix': confusion,
            'labels': self.label_encoder.classes_,
            'predictions': y_pred_labels,
            'true_labels': y_true_labels
        }
    
    def cross_validate(self, lines: List[LineData], cv: int = 5) -> Dict[str, Any]:
        """Perform cross-validation"""
        print(f"Performing {cv}-fold cross-validation...")
        
        X = self.feature_extractor.fit_transform(lines)
        y_labels = [line.role for line in lines]
        y = self.label_encoder.fit_transform(y_labels)
        
        scores = cross_val_score(self.model, X, y, cv=cv, scoring='accuracy')
        
        return {
            'mean_accuracy': scores.mean(),
            'std_accuracy': scores.std(),
            'scores': scores
        }
    
    # In save() / load() add embedding_model to metadata so worker can load without SBERT:
    def save(self, out_dir: str):
        import json, os, joblib
        os.makedirs(out_dir, exist_ok=True)
        joblib.dump(self, os.path.join(out_dir, "model.joblib"))
        with open(os.path.join(out_dir, "metadata.json"), "w") as f:
            json.dump({"model_type": self.model_type, "embedding_model": self.embedding_model}, f)

    @classmethod
    def load(cls, model_dir: str):
        import json, os, joblib
        with open(os.path.join(model_dir, "metadata.json")) as f:
            meta = json.load(f)
        obj = joblib.load(os.path.join(model_dir, "model.joblib"))
        return obj
    
    def get_feature_importance(self) -> Optional[Dict[str, float]]:
        """Get feature importance (if available for model type)"""
        if not self.is_fitted:
            return None
        
        if hasattr(self.model, 'feature_importances_'):
            # Random Forest
            importance_scores = self.model.feature_importances_
        elif hasattr(self.model, 'coef_'):
            # Logistic Regression - use absolute coefficients
            importance_scores = np.abs(self.model.coef_).mean(axis=0)
        else:
            return None
        
        # Create feature names
        embedding_dim = len(importance_scores) - 3  # 3 numeric features
        feature_names = []
        feature_names.extend([f'embed_{i}' for i in range(embedding_dim)])
        feature_names.extend(['y_tertile', 'is_bold', 'is_header_hint'])
        
        return dict(zip(feature_names, importance_scores))


def calculate_y_tertile(y_norm: float) -> int:
    """Calculate y tertile from normalized y coordinate (0=bottom, 1=top)"""
    if y_norm <= 0.33:
        return 0  # bottom tertile
    elif y_norm <= 0.67:
        return 1  # middle tertile
    else:
        return 2  # top tertile


def detect_header_hints(text: str) -> bool:
    """Detect if line contains header hints"""
    text_lower = text.lower()
    
    header_keywords = [
        'patient', 'specimen', 'lab', 'report', 'results', 'test',
        'name:', 'dob:', 'mrn:', 'accession:', 'collected:', 'received:',
        'provider:', 'location:', 'status:', 'reference', 'range',
        'panel', 'profile', 'chemistry', 'hematology', 'urinalysis'
    ]
    
    return any(keyword in text_lower for keyword in header_keywords)