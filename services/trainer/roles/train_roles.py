#!/usr/bin/env python3
"""
Train line role classifier

Trains a classifier to predict line roles in medical documents.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Any
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import joblib
from collections import Counter
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split
from sklearn.metrics import confusion_matrix

try:
    from .line_classifier import LineRoleClassifier, LineData, ROLE_LABELS
except ImportError:  # fallback when run as a plain script
    from line_classifier import LineRoleClassifier, LineData, ROLE_LABELS


def load_and_normalize_data(file_path: str) -> List[LineData]:
    """Load data from JSON or CSV and normalize to LineData objects"""
    with open(file_path, 'r') as f:
        content = f.read().strip()
    
    # Content-based detection
    if content.startswith('[') or content.startswith('{'):
        # JSON format
        raw_data = json.loads(content)
    else:
        # CSV format
        df = pd.read_csv(file_path)
        raw_data = df.to_dict('records')
    
    # Field name mapping for normalization
    field_mapping = {
        'isBold': 'is_bold',
        'yBucket': 'y_tertile', 
        'isHeaderHint': 'is_header_hint',
        'xLeft': 'x_left',
        'xRight': 'x_right', 
        'yNorm': 'y_norm',
        'fontSize': 'font_size'
    }
    
    lines = []
    for item in raw_data:
        # Normalize field names
        normalized_item = {}
        for key, value in item.items():
            normalized_key = field_mapping.get(key, key)
            normalized_item[normalized_key] = value
        
        # Handle label -> role conversion
        if 'label' in normalized_item and 'role' not in normalized_item:
            normalized_item['role'] = normalized_item['label']
            del normalized_item['label']
        
        # Keep only fields that LineData expects
        valid_fields = {'text', 'role', 'y_tertile', 'is_bold', 'is_header_hint', 
                       'page', 'x_left', 'x_right', 'y_norm', 'font_size'}
        filtered_item = {k: v for k, v in normalized_item.items() if k in valid_fields}
        
        # Set defaults for missing fields
        defaults = {
            'page': 1,
            'x_left': 0.0,
            'x_right': 0.0, 
            'y_norm': 0.0,
            'font_size': 12.0,
            'y_tertile': 0,
            'is_bold': False,
            'is_header_hint': False
        }
        
        for field, default_value in defaults.items():
            if field not in filtered_item:
                filtered_item[field] = default_value
        
        # Create LineData object
        try:
            line_data = LineData(**filtered_item)
            lines.append(line_data)
        except TypeError as e:
            print(f"Warning: Skipping invalid record: {e}")
            continue
    
    return lines


def plot_training_results(results: Dict[str, Any], output_dir: str):
    """Create visualizations of training results"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Confusion matrix
    plt.figure(figsize=(10, 8))
    cm = results['confusion_matrix']
    labels = results['labels']
    
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                xticklabels=labels, yticklabels=labels)
    plt.title('Confusion Matrix')
    plt.xlabel('Predicted')
    plt.ylabel('Actual')
    plt.xticks(rotation=45, ha='right')
    plt.yticks(rotation=0)
    plt.tight_layout()
    plt.savefig(output_dir / 'confusion_matrix.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # Classification report heatmap
    plt.figure(figsize=(12, 8))
    report = results['classification_report']
    
    # Extract metrics for each class
    metrics_data = []
    for label in ROLE_LABELS:
        if label in report:
            metrics_data.append([
                report[label]['precision'],
                report[label]['recall'], 
                report[label]['f1-score'],
                report[label]['support']
            ])
        else:
            metrics_data.append([0, 0, 0, 0])
    
    metrics_df = pd.DataFrame(
        metrics_data,
        index=ROLE_LABELS,
        columns=['Precision', 'Recall', 'F1-Score', 'Support']
    )
    
    # Plot precision, recall, f1-score (exclude support for heatmap)
    metrics_for_plot = metrics_df[['Precision', 'Recall', 'F1-Score']]
    sns.heatmap(metrics_for_plot, annot=True, fmt='.3f', cmap='RdYlBu_r',
                vmin=0, vmax=1, cbar_kws={'label': 'Score'})
    plt.title('Classification Metrics by Role')
    plt.xlabel('Metrics')
    plt.ylabel('Role')
    plt.xticks(rotation=0)
    plt.yticks(rotation=0)
    plt.tight_layout()
    plt.savefig(output_dir / 'classification_metrics.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"Plots saved to {output_dir}")


def analyze_feature_importance(classifier: LineRoleClassifier, output_dir: str):
    """Analyze and plot feature importance"""
    importance = classifier.get_feature_importance()
    if not importance:
        print("Feature importance not available for this model type")
        return
    
    output_dir = Path(output_dir)
    
    # Sort features by importance
    sorted_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)
    
    # Plot top features
    plt.figure(figsize=(12, 8))
    
    # Take top 20 features
    top_features = sorted_features[:20]
    feature_names = [f[0] for f in top_features]
    feature_scores = [f[1] for f in top_features]
    
    plt.barh(range(len(feature_names)), feature_scores)
    plt.yticks(range(len(feature_names)), feature_names)
    plt.xlabel('Feature Importance')
    plt.title('Top 20 Most Important Features')
    plt.gca().invert_yaxis()
    plt.tight_layout()
    plt.savefig(output_dir / 'feature_importance.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # Save feature importance to file
    with open(output_dir / 'feature_importance.json', 'w') as f:
        json.dump(importance, f, indent=2)
    
    print(f"Feature importance analysis saved to {output_dir}")


def print_classification_summary(results: Dict[str, Any]):
    """Print detailed classification results"""
    print("\n=== Classification Results ===")
    print(f"Overall Accuracy: {results['accuracy']:.3f}")
    
    report = results['classification_report']
    
    print(f"\nPer-class metrics:")
    print(f"{'Role':<20} {'Precision':<10} {'Recall':<10} {'F1-Score':<10} {'Support':<10}")
    print("-" * 70)
    
    for role in ROLE_LABELS:
        if role in report:
            metrics = report[role]
            print(f"{role:<20} {metrics['precision']:<10.3f} {metrics['recall']:<10.3f} "
                  f"{metrics['f1-score']:<10.3f} {int(metrics['support']):<10}")
        else:
            print(f"{role:<20} {'N/A':<10} {'N/A':<10} {'N/A':<10} {'0':<10}")
    
    # Overall metrics
    if 'macro avg' in report:
        macro = report['macro avg']
        print(f"\nMacro average:    {macro['precision']:.3f}     {macro['recall']:.3f}     "
              f"{macro['f1-score']:.3f}")
    
    if 'weighted avg' in report:
        weighted = report['weighted avg']
        print(f"Weighted average: {weighted['precision']:.3f}     {weighted['recall']:.3f}     "
              f"{weighted['f1-score']:.3f}")


def analyze_misclassifications(results: Dict[str, Any], test_lines: List[LineData], 
                              output_dir: str, top_n: int = 20):
    """Analyze and save misclassification examples"""
    predictions = results['predictions']
    true_labels = results['true_labels']
    
    misclassified = []
    for i, (pred, true) in enumerate(zip(predictions, true_labels)):
        if pred != true:
            misclassified.append({
                'index': i,
                'text': test_lines[i].text[:100],  # First 100 chars
                'true_role': true,
                'predicted_role': pred,
                'y_tertile': test_lines[i].y_tertile,
                'is_bold': test_lines[i].is_bold,
                'is_header_hint': test_lines[i].is_header_hint
            })
    
    # Sort by frequency of misclassification patterns
    misclassification_patterns = {}
    for item in misclassified:
        pattern = f"{item['true_role']} -> {item['predicted_role']}"
        if pattern not in misclassification_patterns:
            misclassification_patterns[pattern] = []
        misclassification_patterns[pattern].append(item)
    
    # Sort patterns by frequency
    sorted_patterns = sorted(misclassification_patterns.items(), 
                           key=lambda x: len(x[1]), reverse=True)
    
    # Save misclassification analysis
    output_path = Path(output_dir) / 'misclassifications.json'
    analysis = {
        'total_misclassified': len(misclassified),
        'misclassification_rate': len(misclassified) / len(test_lines),
        'patterns': {}
    }
    
    print(f"\n=== Misclassification Analysis ===")
    print(f"Total misclassified: {len(misclassified)} / {len(test_lines)} "
          f"({len(misclassified)/len(test_lines)*100:.1f}%)")
    
    print(f"\nTop misclassification patterns:")
    for pattern, items in sorted_patterns[:10]:
        count = len(items)
        percentage = (count / len(misclassified)) * 100
        print(f"  {pattern}: {count} ({percentage:.1f}%)")
        
        # Save pattern details
        analysis['patterns'][pattern] = {
            'count': count,
            'percentage': percentage,
            'examples': items[:5]  # Save top 5 examples
        }
    
    with open(output_path, 'w') as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)
    
    print(f"\nDetailed misclassification analysis saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Train line role classifier')
    parser.add_argument('training_data', help='Path to training data JSON file')
    parser.add_argument('--model-type', choices=['logistic', 'random_forest'], 
                       default='logistic', help='Type of model to train')
    parser.add_argument("--embedding-model", choices=["tfidf","sbert","all-minilm-l6-v2"], default="tfidf")
    parser.add_argument('--test-size', type=float, default=0.2,
                       help='Fraction of data to use for testing')
    parser.add_argument('--output-dir', default='/models/roles',
                       help='Directory to save trained model')
    parser.add_argument('--plots-dir', default='/data/training/plots',
                       help='Directory to save plots')
    parser.add_argument('--cross-validate', action='store_true',
                       help='Perform cross-validation')
    parser.add_argument('--random-seed', type=int, default=42,
                       help='Random seed for reproducibility')
    
    args = parser.parse_args()
    
    # Validate inputs
    if not Path(args.training_data).exists():
        print(f"Error: Training data file not found: {args.training_data}")
        sys.exit(1)
    
    print(f"Loading training data from {args.training_data}")
    
    # Load and normalize data
    try:
        lines = load_and_normalize_data(args.training_data)
    except Exception as e:
        print(f"Error loading training data: {e}")
        sys.exit(1)
    
    print(f"Loaded {len(lines)} training examples")
    
    # Analyze data distribution
    role_counts = {}
    for line in lines:
        role_counts[line.role] = role_counts.get(line.role, 0) + 1
    
    print(f"\nTraining data distribution:")
    for role, count in sorted(role_counts.items()):
        percentage = (count / len(lines)) * 100
        print(f"  {role}: {count} ({percentage:.1f}%)")
    
    # Check for minimum data requirements
    min_samples_per_class = 5
    insufficient_classes = [role for role, count in role_counts.items() 
                          if count < min_samples_per_class]
    
    if insufficient_classes:
        print(f"\n⚠️  Warning: Classes with insufficient samples (<{min_samples_per_class}):")
        for role in insufficient_classes:
            print(f"    {role}: {role_counts[role]} samples")
        print("Consider collecting more data for these classes")
    
    # Check class balance and adjust test_size if needed
    role_counts_counter = Counter(line.role for line in lines)
    min_class_count = min(role_counts_counter.values())
    
    test_size = args.test_size
    stratify_labels = [line.role for line in lines]
    
    if min_class_count < 2:
        test_size = 0.5
        stratify_labels = None
        print(f"Warning: Adjusted test_size to 0.5 and disabled stratification due to tiny classes (min_class_count={min_class_count}).")
    
    # Split data
    train_lines, test_lines = train_test_split(
        lines, 
        test_size=test_size, 
        stratify=stratify_labels,
        random_state=args.random_seed
    )
    
    print(f"\nSplit data: {len(train_lines)} train, {len(test_lines)} test")
    
    # Initialize classifier
    print(f"Initializing {args.model_type} classifier with {args.embedding_model} embeddings")
    classifier = LineRoleClassifier(
        model_type=args.model_type,
        embedding_model=args.embedding_model
    )
    
    # Cross-validation if requested
    if args.cross_validate:
        cv_results = classifier.cross_validate(train_lines, cv=5)
        print(f"\nCross-validation results:")
        print(f"  Mean accuracy: {cv_results['mean_accuracy']:.3f} ± {cv_results['std_accuracy']:.3f}")
        print(f"  Individual scores: {cv_results['scores']}")
    
    # Train classifier
    print(f"\nTraining classifier...")
    classifier.fit(train_lines)
    
    # Evaluate on test set
    print(f"\nEvaluating on test set...")
    results = classifier.evaluate(test_lines)
    
    # Print results
    print_classification_summary(results)
    
    # Create output directories
    model_dir = Path(args.output_dir)
    plots_dir = Path(args.plots_dir)
    model_dir.mkdir(parents=True, exist_ok=True)
    plots_dir.mkdir(parents=True, exist_ok=True)
    
    # Save model artifacts
    print(f"\nSaving model to {model_dir}")
    
    # Save the complete model using joblib
    joblib.dump(classifier, model_dir / 'model.joblib')
    
    # Save metadata with required fields
    model_metadata = {
        'embedding_model': args.embedding_model,
        'labels': list(role_counts.keys()),
        'model_type': args.model_type,
        'test_accuracy': results['accuracy']
    }
    
    with open(model_dir / 'metadata.json', 'w') as f:
        json.dump(model_metadata, f, indent=2)
    
    # Save training metadata
    training_metadata = {
        'training_file': args.training_data,
        'model_type': args.model_type,
        'embedding_model': args.embedding_model,
        'test_size': args.test_size,
        'random_seed': args.random_seed,
        'total_samples': len(lines),
        'train_samples': len(train_lines),
        'test_samples': len(test_lines),
        'role_distribution': role_counts,
        'test_accuracy': results['accuracy'],
        'cross_validation': cv_results if args.cross_validate else None
    }
    
    with open(model_dir / 'training_metadata.json', 'w') as f:
        json.dump(training_metadata, f, indent=2, default=str)
    
    # Create visualizations
    print(f"\nCreating visualizations...")
    plot_training_results(results, plots_dir)
    analyze_feature_importance(classifier, plots_dir)
    analyze_misclassifications(results, test_lines, plots_dir)
    
    print(f"\n✅ Training completed successfully!")
    print(f"Model saved to: {model_dir}")
    print(f"Visualizations saved to: {plots_dir}")
    print(f"\nNext steps:")
    print(f"  1. Review the results and visualizations")
    print(f"  2. Test the model: python eval_roles.py --model-dir {model_dir}")
    print(f"  3. Use the model for inference in your application")


if __name__ == '__main__':
    main()