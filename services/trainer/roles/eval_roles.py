#!/usr/bin/env python3
"""
Evaluate line role classifier

Evaluates trained classifier on test data and provides detailed analysis.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import joblib
from collections import Counter
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import classification_report, confusion_matrix

try:
    from .line_classifier import LineRoleClassifier, LineData, ROLE_LABELS
    from .train_roles import load_and_normalize_data
except ImportError:  # fallback when run as a plain script
    from line_classifier import LineRoleClassifier, LineData, ROLE_LABELS
    from train_roles import load_and_normalize_data


def evaluate_model_on_data(classifier: LineRoleClassifier, test_lines: List[LineData]) -> Dict[str, Any]:
    """Evaluate model and return detailed results"""
    print(f"Evaluating model on {len(test_lines)} test examples...")
    
    # Get predictions and probabilities
    predictions = classifier.predict(test_lines)
    probabilities = classifier.predict_proba(test_lines)
    
    # True labels
    true_labels = [line.role for line in test_lines]
    
    # Calculate metrics
    report = classification_report(true_labels, predictions, output_dict=True, zero_division=0)
    cm = confusion_matrix(true_labels, predictions, labels=ROLE_LABELS)
    
    # Calculate confidence statistics
    max_probs = np.max(probabilities, axis=1)
    mean_confidence = np.mean(max_probs)
    
    # Find low confidence predictions
    low_confidence_threshold = 0.5
    low_confidence_indices = np.where(max_probs < low_confidence_threshold)[0]
    
    results = {
        'predictions': predictions,
        'true_labels': true_labels,
        'probabilities': probabilities,
        'classification_report': report,
        'confusion_matrix': cm,
        'accuracy': report['accuracy'],
        'mean_confidence': mean_confidence,
        'low_confidence_count': len(low_confidence_indices),
        'low_confidence_indices': low_confidence_indices.tolist()
    }
    
    return results


def analyze_prediction_confidence(results: Dict[str, Any], test_lines: List[LineData]):
    """Analyze prediction confidence patterns"""
    probabilities = results['probabilities']
    predictions = results['predictions']
    true_labels = results['true_labels']
    
    max_probs = np.max(probabilities, axis=1)
    
    print(f"\n=== Confidence Analysis ===")
    print(f"Mean prediction confidence: {results['mean_confidence']:.3f}")
    print(f"Confidence distribution:")
    print(f"  Very high (>0.9): {np.sum(max_probs > 0.9)} ({np.mean(max_probs > 0.9)*100:.1f}%)")
    print(f"  High (0.7-0.9): {np.sum((max_probs > 0.7) & (max_probs <= 0.9))} ({np.mean((max_probs > 0.7) & (max_probs <= 0.9))*100:.1f}%)")
    print(f"  Medium (0.5-0.7): {np.sum((max_probs > 0.5) & (max_probs <= 0.7))} ({np.mean((max_probs > 0.5) & (max_probs <= 0.7))*100:.1f}%)")
    print(f"  Low (<0.5): {np.sum(max_probs <= 0.5)} ({np.mean(max_probs <= 0.5)*100:.1f}%)")
    
    # Analyze confidence by role
    confidence_by_role = {}
    accuracy_by_role = {}
    
    for role in ROLE_LABELS:
        role_indices = [i for i, label in enumerate(true_labels) if label == role]
        if role_indices:
            role_confidences = max_probs[role_indices]
            role_predictions = [predictions[i] for i in role_indices]
            role_true = [true_labels[i] for i in role_indices]
            
            confidence_by_role[role] = np.mean(role_confidences)
            accuracy_by_role[role] = np.mean([p == t for p, t in zip(role_predictions, role_true)])
    
    print(f"\nConfidence and accuracy by role:")
    print(f"{'Role':<20} {'Mean Confidence':<15} {'Accuracy':<10}")
    print("-" * 50)
    for role in ROLE_LABELS:
        if role in confidence_by_role:
            print(f"{role:<20} {confidence_by_role[role]:<15.3f} {accuracy_by_role[role]:<10.3f}")


def show_prediction_examples(results: Dict[str, Any], test_lines: List[LineData], 
                           examples_per_category: int = 3):
    """Show examples of correct and incorrect predictions"""
    predictions = results['predictions']
    true_labels = results['true_labels']
    probabilities = results['probabilities']
    
    max_probs = np.max(probabilities, axis=1)
    
    print(f"\n=== Prediction Examples ===")
    
    # High confidence correct predictions
    correct_mask = np.array(predictions) == np.array(true_labels)
    high_confidence_correct = np.where(correct_mask & (max_probs > 0.9))[0]
    
    if len(high_confidence_correct) > 0:
        print(f"\nHigh confidence correct predictions:")
        for i, idx in enumerate(high_confidence_correct[:examples_per_category]):
            line = test_lines[idx]
            conf = max_probs[idx]
            print(f"  {i+1}. [{predictions[idx]}] (conf: {conf:.3f})")
            print(f"     Text: {line.text[:80]}...")
            print(f"     Features: tertile={line.y_tertile}, bold={line.is_bold}, header_hint={line.is_header_hint}")
    
    # High confidence incorrect predictions
    high_confidence_incorrect = np.where(~correct_mask & (max_probs > 0.7))[0]
    
    if len(high_confidence_incorrect) > 0:
        print(f"\nHigh confidence incorrect predictions:")
        for i, idx in enumerate(high_confidence_incorrect[:examples_per_category]):
            line = test_lines[idx]
            conf = max_probs[idx]
            print(f"  {i+1}. Predicted: [{predictions[idx]}] True: [{true_labels[idx]}] (conf: {conf:.3f})")
            print(f"     Text: {line.text[:80]}...")
            print(f"     Features: tertile={line.y_tertile}, bold={line.is_bold}, header_hint={line.is_header_hint}")
    
    # Low confidence predictions
    low_confidence = np.where(max_probs < 0.5)[0]
    
    if len(low_confidence) > 0:
        print(f"\nLow confidence predictions:")
        for i, idx in enumerate(low_confidence[:examples_per_category]):
            line = test_lines[idx]
            conf = max_probs[idx]
            correct = "✓" if predictions[idx] == true_labels[idx] else "✗"
            print(f"  {i+1}. {correct} [{predictions[idx]}] (conf: {conf:.3f})")
            print(f"     Text: {line.text[:80]}...")
            print(f"     Features: tertile={line.y_tertile}, bold={line.is_bold}, header_hint={line.is_header_hint}")


def interactive_prediction_demo(classifier: LineRoleClassifier):
    """Interactive demo for testing predictions"""
    print(f"\n=== Interactive Prediction Demo ===")
    print("Enter line text to get role predictions (or 'quit' to exit)")
    
    while True:
        try:
            text = input("\nEnter line text: ").strip()
            if text.lower() in ['quit', 'exit', 'q']:
                break
            
            if not text:
                continue
            
            # Get additional features from user
            print("Enter additional features (or press Enter for defaults):")
            
            y_tertile_input = input("Y tertile (0=bottom, 1=middle, 2=top) [1]: ").strip()
            y_tertile = int(y_tertile_input) if y_tertile_input and y_tertile_input.isdigit() else 1
            
            is_bold_input = input("Is bold? (y/n) [n]: ").strip().lower()
            is_bold = is_bold_input == 'y'
            
            is_header_hint_input = input("Has header hints? (y/n) [auto]: ").strip().lower()
            if is_header_hint_input in ['y', 'n']:
                is_header_hint = is_header_hint_input == 'y'
            else:
                # Auto-detect
                from line_classifier import detect_header_hints
                is_header_hint = detect_header_hints(text)
            
            # Create line data
            line = LineData(
                text=text,
                y_tertile=y_tertile,
                is_bold=is_bold,
                is_header_hint=is_header_hint,
                role='UNKNOWN',  # Will be predicted
                page=1,
                y_norm=0.5
            )
            
            # Get prediction
            prediction = classifier.predict([line])[0]
            probabilities = classifier.predict_proba([line])[0]
            
            print(f"\n📊 Prediction: {prediction}")
            print(f"Confidence: {np.max(probabilities):.3f}")
            
            # Show top 3 predictions
            label_names = classifier.label_encoder.classes_
            sorted_indices = np.argsort(probabilities)[::-1]
            
            print(f"\nTop 3 predictions:")
            for i in range(min(3, len(sorted_indices))):
                idx = sorted_indices[i]
                role = label_names[idx]
                prob = probabilities[idx]
                print(f"  {i+1}. {role}: {prob:.3f}")
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")
    
    print("Demo ended.")


def save_evaluation_results(results: Dict[str, Any], classifier, output_dir: str):
    """Save evaluation results to files"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save classification report
    with open(output_dir / 'evaluation_report.json', 'w') as f:
        # Convert numpy arrays to lists for JSON serialization
        serializable_results = {
            'accuracy': float(results['accuracy']),
            'mean_confidence': float(results['mean_confidence']),
            'low_confidence_count': int(results['low_confidence_count']),
            'classification_report': results['classification_report'],
            'confusion_matrix': results['confusion_matrix'].tolist()
        }
        json.dump(serializable_results, f, indent=2)
    
    # Get class order from the classifier and align to that
    y_true = results['true_labels']
    y_pred = results['predictions'] 
    y_proba = results['probabilities']
    
    # Get the actual class order from the classifier
    class_names = list(getattr(classifier, "label_encoder_", None).classes_) \
        if hasattr(classifier, "label_encoder_") else list(getattr(classifier, "classes_", []))
    
    # Build probability rows safely
    prob_rows = []
    for i, prob in enumerate(y_proba):
        row = { "true": y_true[i], "pred": y_pred[i] }
        # zip to avoid index errors if shapes differ
        row["probs"] = { lbl: float(p) for lbl, p in zip(class_names, prob) }
        prob_rows.append(row)
    
    # Save detailed predictions
    predictions_data = []
    for i, prob_row in enumerate(prob_rows):
        predictions_data.append({
            'index': i,
            'predicted': prob_row['pred'],
            'true': prob_row['true'],
            'confidence': float(np.max(y_proba[i])),
            'correct': prob_row['pred'] == prob_row['true'],
            'probabilities': prob_row['probs']
        })
    
    with open(output_dir / 'detailed_predictions.json', 'w') as f:
        json.dump(predictions_data, f, indent=2)
    
    print(f"Evaluation results saved to {output_dir}")


def main():
    parser = argparse.ArgumentParser(description='Evaluate line role classifier')
    parser.add_argument('data_file', help='Path to evaluation data (JSON or CSV)')
    parser.add_argument('--model-dir', default='/models/roles',
                       help='Directory containing trained model')
    parser.add_argument("--embedding-model", choices=["tfidf","sbert","all-minilm-l6-v2"], default="tfidf")
    parser.add_argument('--output-dir', default='/data/evaluation',
                       help='Directory to save evaluation results')
    parser.add_argument('--interactive', action='store_true',
                       help='Run interactive prediction demo')
    parser.add_argument('--examples', type=int, default=3,
                       help='Number of examples to show per category')
    
    args = parser.parse_args()
    
    # Validate inputs
    if not Path(args.data_file).exists():
        print(f"Error: Data file not found: {args.data_file}")
        sys.exit(1)
    
    model_dir = Path(args.model_dir)
    if not model_dir.exists():
        print(f"Error: Model directory not found: {model_dir}")
        sys.exit(1)
    
    # Load model using LineRoleClassifier.load()
    print(f"Loading model from {model_dir}")
    
    try:
        classifier = LineRoleClassifier.load(str(model_dir))
    except Exception as e:
        print(f"Error loading model: {e}")
        sys.exit(1)
    
    print("Model loaded successfully")
    
    # Display model information
    print(f"\nModel Information:")
    print(f"  Embedding model: {classifier.embedding_model}")
    print(f"  Model type: {classifier.model_type}")
    
    # Load and normalize evaluation data
    print(f"\nLoading evaluation data from {args.data_file}")
    try:
        test_lines = load_and_normalize_data(args.data_file)
    except Exception as e:
        print(f"Error loading evaluation data: {e}")
        sys.exit(1)
    
    print(f"Loaded {len(test_lines)} evaluation examples")
    
    # Evaluate
    results = evaluate_model_on_data(classifier, test_lines)
    
    # Print accuracy and per-class counts
    print(f"\n=== Evaluation Results ===")
    print(f"Test Accuracy: {results['accuracy']:.3f}")
    
    # Count actual vs predicted
    true_labels = results['true_labels']
    predictions = results['predictions']
    
    true_counts = Counter(true_labels)
    pred_counts = Counter(predictions)
    
    print(f"\nPer-class counts:")
    print(f"{'Role':<20} {'True Count':<12} {'Pred Count':<12} {'Precision':<10} {'Recall':<10}")
    print("-" * 75)
    
    report = results['classification_report']
    for role in sorted(set(true_labels + predictions)):
        true_count = true_counts.get(role, 0)
        pred_count = pred_counts.get(role, 0)
        
        if role in report:
            metrics = report[role]
            precision = metrics['precision']
            recall = metrics['recall']
        else:
            precision = 0.0
            recall = 0.0
        
        print(f"{role:<20} {true_count:<12} {pred_count:<12} {precision:<10.3f} {recall:<10.3f}")
    
    # Save results
    save_evaluation_results(results, classifier, args.output_dir)
    
    # Interactive demo
    if args.interactive:
        interactive_prediction_demo(classifier)
    
    print(f"\n✅ Evaluation completed!")


if __name__ == '__main__':
    main()