"""
Token-level NER classifier for TEST_ROW lines

Classifies tokens within test result lines into semantic components:
TEST_NAME, VALUE, UNIT, REF_RANGE, FLAG
"""

import os
import json
import re
from typing import List, Dict, Tuple, Optional, Any, Union
from dataclasses import dataclass, asdict
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from transformers import (
    AutoTokenizer, AutoModel, AutoConfig,
    TrainingArguments, Trainer,
    get_linear_schedule_with_warmup
)
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, confusion_matrix
import joblib

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

# Class weights to handle imbalance (penalize O heavily)
CLASS_WEIGHTS = {
    'O': 0.1,
    'B-TEST_NAME': 2.0,
    'I-TEST_NAME': 1.5,
    'B-VALUE': 3.0,
    'I-VALUE': 2.0,
    'B-UNIT': 3.0,
    'I-UNIT': 2.0,
    'B-REF_RANGE': 2.5,
    'I-REF_RANGE': 2.0,
    'B-FLAG': 4.0,
    'I-FLAG': 3.0
}


@dataclass
class TokenizedExample:
    """A tokenized example for training/inference"""
    text: str
    tokens: List[str]
    labels: List[str]
    token_ids: List[int]
    attention_mask: List[int]
    label_ids: List[int]
    word_ids: Optional[List[Optional[int]]] = None


class TestRowDataset(Dataset):
    """PyTorch dataset for TEST_ROW token classification"""
    
    def __init__(self, examples: List[TokenizedExample]):
        self.examples = examples
    
    def __len__(self):
        return len(self.examples)
    
    def __getitem__(self, idx):
        example = self.examples[idx]
        return {
            'input_ids': torch.tensor(example.token_ids, dtype=torch.long),
            'attention_mask': torch.tensor(example.attention_mask, dtype=torch.long),
            'labels': torch.tensor(example.label_ids, dtype=torch.long)
        }


class TestRowTokenClassifier(nn.Module):
    """Token classifier for TEST_ROW lines"""
    
    def __init__(self, model_name: str, num_labels: int, dropout: float = 0.3):
        super().__init__()
        self.model_name = model_name
        self.num_labels = num_labels
        
        # Load base transformer model
        config = AutoConfig.from_pretrained(model_name, num_labels=num_labels)
        self.transformer = AutoModel.from_pretrained(model_name, config=config)
        
        # Classification head
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Linear(self.transformer.config.hidden_size, num_labels)
        
        # Class weights for handling imbalance
        self.class_weights = None
    
    def forward(self, input_ids, attention_mask=None, labels=None):
        # Get transformer outputs
        outputs = self.transformer(input_ids=input_ids, attention_mask=attention_mask)
        sequence_output = outputs.last_hidden_state
        
        # Apply dropout and classification
        sequence_output = self.dropout(sequence_output)
        logits = self.classifier(sequence_output)
        
        loss = None
        if labels is not None:
            # Use weighted cross entropy loss
            loss_fct = nn.CrossEntropyLoss(weight=self.class_weights, ignore_index=-100)
            
            # Only compute loss on non-ignored tokens
            active_loss = attention_mask.view(-1) == 1
            active_logits = logits.view(-1, self.num_labels)
            active_labels = torch.where(
                active_loss, labels.view(-1), torch.tensor(loss_fct.ignore_index).type_as(labels)
            )
            loss = loss_fct(active_logits, active_labels)
        
        return {
            'loss': loss,
            'logits': logits,
            'hidden_states': outputs.hidden_states if hasattr(outputs, 'hidden_states') else None,
            'attentions': outputs.attentions if hasattr(outputs, 'attentions') else None
        }
    
    def set_class_weights(self, weights: torch.Tensor):
        """Set class weights for loss computation"""
        self.class_weights = weights


class TestRowNER:
    """Main interface for TEST_ROW token classification"""
    
    def __init__(self, 
                 model_name: str = "distilbert-base-uncased",
                 max_length: int = 256,
                 learning_rate: float = 2e-5,
                 weight_decay: float = 0.01,
                 warmup_ratio: float = 0.1):
        
        self.model_name = model_name
        self.max_length = max_length
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        self.warmup_ratio = warmup_ratio
        
        # Initialize tokenizer and label encoder
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.label_encoder = LabelEncoder()
        self.label_encoder.fit(TOKEN_LABELS)
        
        # Model will be initialized during training or loading
        self.model = None
        self.is_trained = False
        
        # Add special tokens if needed
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
    
    def tokenize_and_align_labels(self, text: str, labels: List[str]) -> TokenizedExample:
        """Tokenize text and align labels with subword tokens"""
        # Split text into words
        words = text.split()
        
        # Ensure labels match words
        if len(labels) != len(words):
            raise ValueError(f"Number of labels ({len(labels)}) doesn't match number of words ({len(words)})")
        
        # Tokenize with word alignment
        tokenized = self.tokenizer(
            words,
            is_split_into_words=True,
            truncation=True,
            max_length=self.max_length,
            padding='max_length',
            return_tensors=None,
            return_offsets_mapping=False
        )
        
        # Align labels with subword tokens
        word_ids = tokenized.word_ids()
        aligned_labels = []
        previous_word_idx = None
        
        for word_idx in word_ids:
            if word_idx is None:
                # Special tokens (CLS, SEP, PAD)
                aligned_labels.append(-100)  # Ignore in loss computation
            elif word_idx != previous_word_idx:
                # First subword token of a word
                aligned_labels.append(self.label_encoder.transform([labels[word_idx]])[0])
            else:
                # Continuation subword token
                label = labels[word_idx]
                if label.startswith('B-'):
                    # Convert B- to I- for continuation tokens
                    continuation_label = 'I-' + label[2:]
                    if continuation_label in TOKEN_LABELS:
                        aligned_labels.append(self.label_encoder.transform([continuation_label])[0])
                    else:
                        aligned_labels.append(self.label_encoder.transform([label])[0])
                else:
                    aligned_labels.append(self.label_encoder.transform([label])[0])
            
            previous_word_idx = word_idx
        
        return TokenizedExample(
            text=text,
            tokens=self.tokenizer.convert_ids_to_tokens(tokenized['input_ids']),
            labels=labels,
            token_ids=tokenized['input_ids'],
            attention_mask=tokenized['attention_mask'],
            label_ids=aligned_labels,
            word_ids=word_ids
        )
    
    def prepare_training_data(self, examples: List[Tuple[str, List[str]]]) -> List[TokenizedExample]:
        """Prepare training data from text-label pairs"""
        tokenized_examples = []
        
        for text, labels in examples:
            try:
                tokenized = self.tokenize_and_align_labels(text, labels)
                tokenized_examples.append(tokenized)
            except ValueError as e:
                print(f"Skipping example due to error: {e}")
                print(f"Text: {text}")
                print(f"Labels: {labels}")
                continue
        
        return tokenized_examples
    
    def train(self, 
              train_examples: List[Tuple[str, List[str]]],
              val_examples: Optional[List[Tuple[str, List[str]]]] = None,
              epochs: int = 3,
              batch_size: int = 16,
              output_dir: str = "/tmp/testrow_training"):
        
        """Train the token classifier"""
        print(f"Preparing training data...")
        
        # Prepare data
        train_data = self.prepare_training_data(train_examples)
        val_data = self.prepare_training_data(val_examples) if val_examples else None
        
        print(f"Training examples: {len(train_data)}")
        if val_data:
            print(f"Validation examples: {len(val_data)}")
        
        # Create datasets
        train_dataset = TestRowDataset(train_data)
        val_dataset = TestRowDataset(val_data) if val_data else None
        
        # Initialize model
        num_labels = len(TOKEN_LABELS)
        self.model = TestRowTokenClassifier(self.model_name, num_labels)
        
        # Set class weights
        weights = torch.tensor([CLASS_WEIGHTS[label] for label in TOKEN_LABELS], dtype=torch.float)
        self.model.set_class_weights(weights)
        
        # Training arguments
        training_args = TrainingArguments(
            output_dir=output_dir,
            num_train_epochs=epochs,
            per_device_train_batch_size=batch_size,
            per_device_eval_batch_size=batch_size,
            warmup_ratio=self.warmup_ratio,
            weight_decay=self.weight_decay,
            logging_dir=f"{output_dir}/logs",
            logging_steps=50,
            evaluation_strategy="epoch" if val_dataset else "no",
            save_strategy="epoch",
            save_total_limit=2,
            load_best_model_at_end=val_dataset is not None,
            metric_for_best_model="eval_loss" if val_dataset else None,
            report_to=None,  # Disable wandb/tensorboard
            remove_unused_columns=False
        )
        
        # Initialize trainer
        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=val_dataset,
            tokenizer=self.tokenizer,
        )
        
        # Train
        print("Starting training...")
        trainer.train()
        
        self.is_trained = True
        print("Training completed")
        
        return trainer
    
    def predict(self, texts: List[str]) -> List[List[str]]:
        """Predict token labels for texts"""
        if not self.is_trained or self.model is None:
            raise ValueError("Model must be trained before prediction")
        
        self.model.eval()
        predictions = []
        
        with torch.no_grad():
            for text in texts:
                # Create dummy labels for tokenization
                words = text.split()
                dummy_labels = ['O'] * len(words)
                
                # Tokenize
                tokenized = self.tokenize_and_align_labels(text, dummy_labels)
                
                # Predict
                inputs = {
                    'input_ids': torch.tensor([tokenized.token_ids]),
                    'attention_mask': torch.tensor([tokenized.attention_mask])
                }
                
                outputs = self.model(**inputs)
                logits = outputs['logits']
                
                # Get predictions
                pred_ids = torch.argmax(logits, dim=2)[0].cpu().numpy()
                
                # Align back to words
                word_predictions = []
                word_ids = tokenized.word_ids
                previous_word_idx = None
                
                for i, word_idx in enumerate(word_ids):
                    if word_idx is not None and word_idx != previous_word_idx:
                        pred_label = self.label_encoder.inverse_transform([pred_ids[i]])[0]
                        word_predictions.append(pred_label)
                        previous_word_idx = word_idx
                
                predictions.append(word_predictions)
        
        return predictions
    
    def evaluate(self, test_examples: List[Tuple[str, List[str]]]) -> Dict[str, Any]:
        """Evaluate model on test data"""
        if not self.is_trained:
            raise ValueError("Model must be trained before evaluation")
        
        # Get predictions
        texts = [example[0] for example in test_examples]
        true_labels_list = [example[1] for example in test_examples]
        pred_labels_list = self.predict(texts)
        
        # Flatten for sklearn metrics
        true_labels_flat = []
        pred_labels_flat = []
        
        for true_labels, pred_labels in zip(true_labels_list, pred_labels_list):
            # Handle length mismatches
            min_len = min(len(true_labels), len(pred_labels))
            true_labels_flat.extend(true_labels[:min_len])
            pred_labels_flat.extend(pred_labels[:min_len])
        
        # Calculate metrics
        report = classification_report(
            true_labels_flat, 
            pred_labels_flat, 
            output_dict=True,
            zero_division=0
        )
        
        cm = confusion_matrix(true_labels_flat, pred_labels_flat, labels=TOKEN_LABELS)
        
        # Token-level accuracy
        accuracy = np.mean([t == p for t, p in zip(true_labels_flat, pred_labels_flat)])
        
        # Entity-level evaluation
        entity_scores = self._calculate_entity_scores(true_labels_list, pred_labels_list)
        
        return {
            'token_accuracy': accuracy,
            'classification_report': report,
            'confusion_matrix': cm,
            'entity_scores': entity_scores,
            'true_labels': true_labels_flat,
            'pred_labels': pred_labels_flat
        }
    
    def _calculate_entity_scores(self, true_labels_list: List[List[str]], 
                               pred_labels_list: List[List[str]]) -> Dict[str, float]:
        """Calculate entity-level precision, recall, F1"""
        entity_types = ['TEST_NAME', 'VALUE', 'UNIT', 'REF_RANGE', 'FLAG']
        scores = {}
        
        for entity_type in entity_types:
            true_entities = set()
            pred_entities = set()
            
            for i, (true_labels, pred_labels) in enumerate(zip(true_labels_list, pred_labels_list)):
                # Extract entities for this type
                true_entities.update(self._extract_entities(true_labels, entity_type, i))
                pred_entities.update(self._extract_entities(pred_labels, entity_type, i))
            
            # Calculate metrics
            if len(pred_entities) == 0:
                precision = 0.0
            else:
                precision = len(true_entities & pred_entities) / len(pred_entities)
            
            if len(true_entities) == 0:
                recall = 0.0
            else:
                recall = len(true_entities & pred_entities) / len(true_entities)
            
            if precision + recall == 0:
                f1 = 0.0
            else:
                f1 = 2 * precision * recall / (precision + recall)
            
            scores[entity_type] = {
                'precision': precision,
                'recall': recall,
                'f1': f1,
                'support': len(true_entities)
            }
        
        return scores
    
    def _extract_entities(self, labels: List[str], entity_type: str, example_idx: int) -> List[Tuple[int, int, int]]:
        """Extract entity spans for a given type"""
        entities = []
        start = None
        
        for i, label in enumerate(labels):
            if label == f'B-{entity_type}':
                if start is not None:
                    # End previous entity
                    entities.append((example_idx, start, i - 1))
                start = i
            elif label == f'I-{entity_type}':
                if start is None:
                    # Invalid I- without B-, treat as B-
                    start = i
            else:
                if start is not None:
                    # End current entity
                    entities.append((example_idx, start, i - 1))
                    start = None
        
        # Handle entity at end of sequence
        if start is not None:
            entities.append((example_idx, start, len(labels) - 1))
        
        return entities
    
    def save_model(self, output_dir: str):
        """Save trained model"""
        if not self.is_trained:
            raise ValueError("Cannot save untrained model")
        
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save model and tokenizer
        self.model.transformer.save_pretrained(output_dir / "transformer")
        self.tokenizer.save_pretrained(output_dir / "tokenizer")
        
        # Save classifier head and other components
        torch.save({
            'classifier_state_dict': self.model.classifier.state_dict(),
            'dropout_state_dict': self.model.dropout.state_dict(),
            'model_config': {
                'model_name': self.model_name,
                'num_labels': len(TOKEN_LABELS),
                'max_length': self.max_length
            }
        }, output_dir / "classifier_head.pt")
        
        # Save label encoder
        joblib.dump(self.label_encoder, output_dir / "label_encoder.pkl")
        
        # Save metadata
        metadata = {
            'model_name': self.model_name,
            'max_length': self.max_length,
            'learning_rate': self.learning_rate,
            'weight_decay': self.weight_decay,
            'warmup_ratio': self.warmup_ratio,
            'token_labels': TOKEN_LABELS,
            'class_weights': CLASS_WEIGHTS,
            'is_trained': self.is_trained
        }
        
        with open(output_dir / "config.json", 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"Model saved to {output_dir}")
    
    def load_model(self, model_dir: str):
        """Load trained model"""
        model_dir = Path(model_dir)
        
        if not model_dir.exists():
            raise FileNotFoundError(f"Model directory not found: {model_dir}")
        
        # Load metadata
        with open(model_dir / "config.json", 'r') as f:
            metadata = json.load(f)
        
        self.model_name = metadata['model_name']
        self.max_length = metadata['max_length']
        self.learning_rate = metadata['learning_rate']
        self.weight_decay = metadata['weight_decay']
        self.warmup_ratio = metadata['warmup_ratio']
        
        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(model_dir / "tokenizer")
        
        # Load label encoder
        self.label_encoder = joblib.load(model_dir / "label_encoder.pkl")
        
        # Initialize and load model
        num_labels = len(TOKEN_LABELS)
        self.model = TestRowTokenClassifier(self.model_name, num_labels)
        
        # Load transformer weights
        self.model.transformer = AutoModel.from_pretrained(model_dir / "transformer")
        
        # Load classifier head
        checkpoint = torch.load(model_dir / "classifier_head.pt", map_location='cpu')
        self.model.classifier.load_state_dict(checkpoint['classifier_state_dict'])
        self.model.dropout.load_state_dict(checkpoint['dropout_state_dict'])
        
        # Set class weights
        weights = torch.tensor([CLASS_WEIGHTS[label] for label in TOKEN_LABELS], dtype=torch.float)
        self.model.set_class_weights(weights)
        
        self.is_trained = True
        print(f"Model loaded from {model_dir}")


def align_labels_with_tokenization(text: str, labels: List[str], tokenizer) -> List[str]:
    """Helper function to align BIO labels with tokenizer output"""
    words = text.split()
    if len(words) != len(labels):
        raise ValueError(f"Words and labels length mismatch: {len(words)} vs {len(labels)}")
    
    # Tokenize each word separately to understand subword splits
    aligned_labels = []
    
    for word, label in zip(words, labels):
        word_tokens = tokenizer.tokenize(word)
        
        if len(word_tokens) == 0:
            continue
        elif len(word_tokens) == 1:
            aligned_labels.append(label)
        else:
            # Multiple subword tokens
            aligned_labels.append(label)  # First token keeps original label
            
            # Subsequent tokens get I- version if original was B-
            if label.startswith('B-'):
                i_label = 'I-' + label[2:]
                aligned_labels.extend([i_label] * (len(word_tokens) - 1))
            else:
                aligned_labels.extend([label] * (len(word_tokens) - 1))
    
    return aligned_labels