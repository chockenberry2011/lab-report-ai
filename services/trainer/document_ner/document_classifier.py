"""
Document-level NER classifier using CRF for comprehensive field extraction.

This classifier handles all entity types across the entire document,
learning patterns to handle layout variations across different vendors.
"""

import joblib
import sklearn_crfsuite
from sklearn_crfsuite import metrics
from typing import List, Dict, Tuple, Any, Optional
import re
from .entity_labels import DOCUMENT_ENTITY_LABELS, get_entity_type, is_begin_label


class DocumentNERClassifier:
    """CRF-based classifier for extracting all document fields"""

    def __init__(self):
        self.model = None
        self.labels = DOCUMENT_ENTITY_LABELS

    def token_to_features(self, tokens: List[str], i: int) -> Dict[str, Any]:
        """
        Generate features for a token at position i.

        Features designed to capture layout patterns and context
        that help identify different entity types regardless of format.
        """
        token = tokens[i]

        features = {
            'bias': 1.0,
            'token.lower': token.lower(),
            'token.isupper': token.isupper(),
            'token.istitle': token.istitle(),
            'token.isdigit': token.isdigit(),
            'token.isalpha': token.isalpha(),
            'token.isalnum': token.isalnum(),
            'token.ispunct': not token.isalnum(),
            'token.length': len(token),

            # Prefixes and suffixes
            'token.prefix1': token[:1].lower(),
            'token.prefix2': token[:2].lower(),
            'token.prefix3': token[:3].lower(),
            'token.suffix1': token[-1:].lower(),
            'token.suffix2': token[-2:].lower(),
            'token.suffix3': token[-3:].lower(),

            # Shape patterns (A=upper, a=lower, 9=digit, X=other)
            'token.shape': self._get_token_shape(token),
            'token.short_shape': self._get_short_shape(token),

            # Date patterns
            'token.is_date_like': self._is_date_like(token),
            'token.is_time_like': self._is_time_like(token),

            # ID patterns
            'token.is_id_like': self._is_id_like(token),
            'token.is_phone_like': self._is_phone_like(token),

            # Medical patterns
            'token.is_medical_term': self._is_medical_term(token),

            # Position indicators
            'token.has_colon': ':' in token,
            'token.has_comma': ',' in token,
            'token.has_parentheses': '(' in token or ')' in token,
            'token.has_slash': '/' in token,
            'token.has_dash': '-' in token,
        }

        # Previous token features
        if i > 0:
            prev_token = tokens[i-1]
            features.update({
                'prev_token.lower': prev_token.lower(),
                'prev_token.shape': self._get_token_shape(prev_token),
                'prev_token.is_colon': prev_token == ':',
                'prev_token.is_label_word': self._is_label_word(prev_token),
            })
        else:
            features['BOS'] = True  # Beginning of sequence

        # Next token features
        if i < len(tokens) - 1:
            next_token = tokens[i+1]
            features.update({
                'next_token.lower': next_token.lower(),
                'next_token.shape': self._get_token_shape(next_token),
                'next_token.is_colon': next_token == ':',
            })
        else:
            features['EOS'] = True  # End of sequence

        # Two-token context
        if i > 1:
            features['prev2_token.lower'] = tokens[i-2].lower()
        if i < len(tokens) - 2:
            features['next2_token.lower'] = tokens[i+2].lower()

        # Multi-token patterns
        features.update(self._get_context_features(tokens, i))

        return features

    def _get_token_shape(self, token: str) -> str:
        """Convert token to shape pattern, max length 8"""
        shape = ""
        for char in token:
            if char.isupper():
                shape += "A"
            elif char.islower():
                shape += "a"
            elif char.isdigit():
                shape += "9"
            else:
                shape += "X"
        return shape[:8]  # Limit length

    def _get_short_shape(self, token: str) -> str:
        """Get condensed shape pattern"""
        shape = self._get_token_shape(token)
        # Collapse consecutive identical characters
        if not shape:
            return ""

        short = shape[0]
        for char in shape[1:]:
            if char != short[-1]:
                short += char
        return short

    def _is_date_like(self, token: str) -> bool:
        """Check if token looks like a date"""
        # MM/DD/YYYY, MM-DD-YYYY, etc.
        date_patterns = [
            r'^\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}$',
            r'^\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2}$',
            r'^\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2}$',
            r'^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)',
        ]
        return any(re.match(pattern, token, re.IGNORECASE) for pattern in date_patterns)

    def _is_time_like(self, token: str) -> bool:
        """Check if token looks like a time"""
        return bool(re.match(r'^\d{1,2}:\d{2}(:\d{2})?(\s*(AM|PM))?$', token, re.IGNORECASE))

    def _is_id_like(self, token: str) -> bool:
        """Check if token looks like an ID (alphanumeric with consistent pattern)"""
        # Common ID patterns: A123456, 12D3456789, etc.
        return bool(re.match(r'^[A-Z]?\d{6,}[A-Z]?$', token) or
                   re.match(r'^\d{2}[A-Z]\d{7}$', token))

    def _is_phone_like(self, token: str) -> bool:
        """Check if token looks like phone number"""
        phone_patterns = [
            r'^\(\d{3}\)\s*\d{3}-\d{4}$',
            r'^\d{3}-\d{3}-\d{4}$',
            r'^\d{3}\.\d{3}\.\d{4}$',
            r'^\d{10}$',
        ]
        return any(re.match(pattern, token) for pattern in phone_patterns)

    def _is_medical_term(self, token: str) -> bool:
        """Check if token is likely a medical/lab term"""
        medical_indicators = [
            'lab', 'laboratory', 'pathology', 'clinical', 'medical', 'health',
            'test', 'specimen', 'patient', 'doctor', 'physician', 'md', 'clia'
        ]
        return token.lower() in medical_indicators

    def _is_label_word(self, token: str) -> bool:
        """Check if token is commonly used as a field label"""
        label_words = [
            'patient', 'name', 'dob', 'birth', 'sex', 'gender', 'male', 'female',
            'mrn', 'id', 'number', 'account', 'accession', 'specimen', 'sample',
            'collected', 'received', 'reported', 'date', 'time', 'doctor', 'physician',
            'provider', 'ordering', 'clinic', 'lab', 'laboratory', 'clia', 'address',
            'phone', 'fax', 'director', 'report'
        ]
        return token.lower().rstrip(':').rstrip(',') in label_words

    def _get_context_features(self, tokens: List[str], i: int) -> Dict[str, Any]:
        """Extract context-based features"""
        features = {}

        # Look for nearby label words
        window = 3
        for j in range(max(0, i-window), min(len(tokens), i+window+1)):
            if j != i and self._is_label_word(tokens[j]):
                relative_pos = j - i
                features[f'nearby_label_at_{relative_pos}'] = tokens[j].lower()

        # Check if we're in a header-like region (first few tokens of a line)
        # This is approximate since we don't have line boundaries in this context
        features['is_likely_header_region'] = i < 5

        return features

    def sentences_to_features(self, sentences: List[List[str]]) -> List[List[Dict[str, Any]]]:
        """Convert list of token sentences to feature sentences"""
        return [
            [self.token_to_features(tokens, i) for i in range(len(tokens))]
            for tokens in sentences
        ]

    def train(self, X_train: List[List[str]], y_train: List[List[str]],
              X_dev: Optional[List[List[str]]] = None, y_dev: Optional[List[List[str]]] = None) -> Dict[str, Any]:
        """
        Train the CRF model.

        Args:
            X_train: List of token sequences
            y_train: List of label sequences
            X_dev: Optional validation data
            y_dev: Optional validation labels

        Returns:
            Training statistics
        """
        # Convert to features
        X_train_features = self.sentences_to_features(X_train)

        # Initialize CRF model
        self.model = sklearn_crfsuite.CRF(
            algorithm='lbfgs',
            c1=0.1,           # L1 regularization
            c2=0.1,           # L2 regularization
            max_iterations=100,
            all_possible_transitions=True
        )

        # Train
        self.model.fit(X_train_features, y_train)

        # Evaluation
        y_pred_train = self.model.predict(X_train_features)
        train_score = metrics.flat_f1_score(y_train, y_pred_train, average='weighted', labels=self.labels)

        stats = {
            'train_f1': train_score,
            'train_examples': len(X_train),
            'labels': self.labels
        }

        if X_dev and y_dev:
            X_dev_features = self.sentences_to_features(X_dev)
            y_pred_dev = self.model.predict(X_dev_features)
            dev_score = metrics.flat_f1_score(y_dev, y_pred_dev, average='weighted', labels=self.labels)
            stats['dev_f1'] = dev_score
            stats['dev_examples'] = len(X_dev)

        return stats

    def predict(self, X: List[List[str]]) -> List[List[str]]:
        """Predict labels for token sequences"""
        if not self.model:
            raise ValueError("Model not trained. Call train() first.")

        X_features = self.sentences_to_features(X)
        return self.model.predict(X_features)

    def predict_single(self, tokens: List[str]) -> List[str]:
        """Predict labels for a single token sequence"""
        predictions = self.predict([tokens])
        return predictions[0] if predictions else []

    def extract_entities(self, tokens: List[str], labels: List[str]) -> List[Dict[str, Any]]:
        """
        Extract entities from tokens and labels.

        Returns list of entities with their text, type, and position.
        """
        entities = []
        current_entity = None

        for i, (token, label) in enumerate(zip(tokens, labels)):
            if label == 'O':
                # End current entity if exists
                if current_entity:
                    entities.append(current_entity)
                    current_entity = None
            elif is_begin_label(label):
                # End previous entity and start new one
                if current_entity:
                    entities.append(current_entity)

                current_entity = {
                    'type': get_entity_type(label),
                    'text': token,
                    'start_token': i,
                    'end_token': i,
                    'confidence': 1.0  # TODO: Add confidence scoring
                }
            elif current_entity and label == f"I-{current_entity['type']}":
                # Continue current entity
                current_entity['text'] += f" {token}"
                current_entity['end_token'] = i
            else:
                # Invalid label sequence - treat as O
                if current_entity:
                    entities.append(current_entity)
                    current_entity = None

        # Don't forget last entity
        if current_entity:
            entities.append(current_entity)

        return entities

    def save(self, model_path: str, metadata: Optional[Dict[str, Any]] = None):
        """Save the trained model"""
        if not self.model:
            raise ValueError("No model to save. Train the model first.")

        # Save CRF model
        joblib.dump(self.model, model_path)

        # Save metadata if provided
        if metadata:
            import json
            from pathlib import Path
            metadata_path = Path(model_path).parent / "metadata.json"
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)

    def load(self, model_path: str):
        """Load a trained model"""
        self.model = joblib.load(model_path)

    def get_feature_importance(self, top_n: int = 20) -> List[Tuple[str, float]]:
        """Get most important features for debugging"""
        if not self.model:
            raise ValueError("Model not trained.")

        # Get transition and state features
        trans_features = self.model.transition_features_
        state_features = self.model.state_features_

        # Combine and sort by absolute weight
        all_features = []

        for (from_state, to_state), weight in trans_features.items():
            all_features.append((f"transition:{from_state}->{to_state}", abs(weight)))

        for (state, feature), weight in state_features.items():
            all_features.append((f"state:{state}:{feature}", abs(weight)))

        # Sort by absolute weight and return top features
        all_features.sort(key=lambda x: x[1], reverse=True)
        return all_features[:top_n]