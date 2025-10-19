#!/usr/bin/env python3
"""
Lab AI Pipeline DAG

Orchestrates the complete lab report processing pipeline:
- Scan inbox for new PDFs
- Enqueue processing jobs
- Train models weekly
- Evaluate model performance
- Archive completed outputs

This DAG handles both batch processing and model training workflows.
"""

import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.operators.bash_operator import BashOperator
from airflow.operators.dummy_operator import DummyOperator
from airflow.operators.email_operator import EmailOperator
from airflow.sensors.filesystem import FileSensor
from airflow.models import Variable
from airflow.hooks.base_hook import BaseHook
from airflow.utils.dates import days_ago
from airflow.utils.trigger_rule import TriggerRule

import requests
import pandas as pd


# DAG Configuration
DEFAULT_ARGS = {
    'owner': 'lab-ai',
    'depends_on_past': False,
    'start_date': days_ago(1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'max_active_runs': 1,
}

# Environment variables with defaults
DATA_DIR = os.getenv('DATA_DIR', '/data')
API_URL = os.getenv('API_URL', 'http://api:8000')
MODELS_DIR = os.getenv('MODELS_DIR', '/models')
TRAINER_CMD = os.getenv('TRAINER_CMD', 'python')

# File paths
INBOX_DIR = Path(DATA_DIR) / 'inbox'
OUTBOX_DIR = Path(DATA_DIR) / 'outbox'
ARCHIVE_DIR = Path(DATA_DIR) / 'archive'
TRAINING_DIR = Path(DATA_DIR) / 'training'
LABELSTUDIO_DIR = Path(DATA_DIR) / 'labelstudio'

# Create DAG
dag = DAG(
    'lab_pipeline',
    default_args=DEFAULT_ARGS,
    description='Lab AI processing and training pipeline',
    schedule_interval='@hourly',  # Run every hour for batch processing
    catchup=False,
    max_active_runs=1,
    tags=['lab-ai', 'processing', 'ml']
)


def scan_inbox(**context) -> List[str]:
    """
    Scan inbox directory for new PDF files
    
    Returns:
        List of PDF file paths found in inbox
    """
    print(f"📥 Scanning inbox directory: {INBOX_DIR}")
    
    if not INBOX_DIR.exists():
        print(f"⚠️  Inbox directory does not exist: {INBOX_DIR}")
        return []
    
    # Find PDF files
    pdf_files = list(INBOX_DIR.glob('*.pdf'))
    pdf_paths = [str(f) for f in pdf_files]
    
    print(f"📄 Found {len(pdf_paths)} PDF files:")
    for path in pdf_paths:
        print(f"  - {Path(path).name}")
    
    # Store in XCom for next task
    context['task_instance'].xcom_push(key='pdf_files', value=pdf_paths)
    
    return pdf_paths


def enqueue_jobs(**context) -> Dict[str, Any]:
    """
    Submit PDF files to processing API
    
    Returns:
        Dictionary with job submission results
    """
    # Get PDF files from previous task
    pdf_files = context['task_instance'].xcom_pull(key='pdf_files', task_ids='scan_inbox')
    
    if not pdf_files:
        print("📭 No PDF files to process")
        return {'submitted_jobs': [], 'errors': [], 'total': 0}
    
    print(f"🚀 Submitting {len(pdf_files)} jobs to API: {API_URL}")
    
    submitted_jobs = []
    errors = []
    
    for pdf_path in pdf_files:
        try:
            # Submit job to API
            with open(pdf_path, 'rb') as f:
                files = {'file': f}
                data = {'config': json.dumps({'source': 'airflow_batch'})}
                
                response = requests.post(
                    f"{API_URL}/jobs",
                    files=files,
                    data=data,
                    timeout=30
                )
            
            if response.status_code == 200:
                job_data = response.json()
                submitted_jobs.append({
                    'job_id': job_data.get('job_id'),
                    'file_path': pdf_path,
                    'status': 'submitted'
                })
                print(f"✅ Submitted: {Path(pdf_path).name} -> {job_data.get('job_id')}")
                
                # Move file to processing folder
                processing_dir = INBOX_DIR / 'processing'
                processing_dir.mkdir(exist_ok=True)
                new_path = processing_dir / Path(pdf_path).name
                Path(pdf_path).rename(new_path)
                
            else:
                error_msg = f"API error {response.status_code}: {response.text}"
                errors.append({'file': pdf_path, 'error': error_msg})
                print(f"❌ Failed: {Path(pdf_path).name} - {error_msg}")
                
        except Exception as e:
            error_msg = f"Exception: {str(e)}"
            errors.append({'file': pdf_path, 'error': error_msg})
            print(f"❌ Exception for {Path(pdf_path).name}: {error_msg}")
    
    results = {
        'submitted_jobs': submitted_jobs,
        'errors': errors,
        'total': len(pdf_files),
        'success_count': len(submitted_jobs),
        'error_count': len(errors)
    }
    
    print(f"📊 Job submission complete:")
    print(f"  Success: {results['success_count']}")
    print(f"  Errors: {results['error_count']}")
    
    return results


def check_training_data_freshness(**context) -> bool:
    """
    Check if training data has been updated recently and models need retraining
    
    Returns:
        True if models should be retrained
    """
    print("🔍 Checking training data freshness...")
    
    # Check for new labeled data in Label Studio
    ls_files = list(LABELSTUDIO_DIR.glob('*.json'))
    training_files = list(TRAINING_DIR.glob('*.csv')) + list(TRAINING_DIR.glob('*.jsonl'))
    
    # Check modification times
    now = datetime.now()
    week_ago = now - timedelta(days=7)
    
    # Check if any labeled data is newer than a week
    fresh_ls_data = any(
        datetime.fromtimestamp(f.stat().st_mtime) > week_ago 
        for f in ls_files
    )
    
    # Check if training data exists and is recent
    fresh_training_data = any(
        datetime.fromtimestamp(f.stat().st_mtime) > week_ago 
        for f in training_files
    )
    
    should_retrain = fresh_ls_data or fresh_training_data
    
    print(f"  Label Studio files: {len(ls_files)} (fresh: {fresh_ls_data})")
    print(f"  Training files: {len(training_files)} (fresh: {fresh_training_data})")
    print(f"  Should retrain: {should_retrain}")
    
    return should_retrain


def prepare_training_data(**context) -> Dict[str, Any]:
    """
    Convert Label Studio data to training formats
    
    Returns:
        Dictionary with conversion results
    """
    print("🔄 Converting Label Studio data to training format...")
    
    results = {'roles': None, 'testrow': None, 'errors': []}
    
    try:
        # Find Label Studio exports
        roles_exports = list(LABELSTUDIO_DIR.glob('*roles*.json'))
        testrow_exports = list(LABELSTUDIO_DIR.glob('*testrow*.json'))
        
        # Convert roles data
        if roles_exports:
            latest_roles = max(roles_exports, key=lambda f: f.stat().st_mtime)
            roles_output = TRAINING_DIR / 'roles_from_ls.csv'
            
            cmd = f"python /scripts/ls_roles_to_csv.py {latest_roles} -o {roles_output}"
            result = os.system(cmd)
            
            if result == 0:
                results['roles'] = str(roles_output)
                print(f"✅ Roles data converted: {roles_output}")
            else:
                results['errors'].append(f"Roles conversion failed: {cmd}")
        
        # Convert test-row data
        if testrow_exports:
            latest_testrow = max(testrow_exports, key=lambda f: f.stat().st_mtime)
            testrow_output = TRAINING_DIR / 'testrow_from_ls.jsonl'
            
            cmd = f"python /scripts/ls_testrow_to_ner.py {latest_testrow} -o {testrow_output}"
            result = os.system(cmd)
            
            if result == 0:
                results['testrow'] = str(testrow_output)
                print(f"✅ Test-row data converted: {testrow_output}")
            else:
                results['errors'].append(f"Test-row conversion failed: {cmd}")
    
    except Exception as e:
        results['errors'].append(f"Training data preparation failed: {str(e)}")
        print(f"❌ Training data preparation error: {e}")
    
    return results


def train_roles_model(**context) -> Dict[str, Any]:
    """
    Train or retrain the roles classification model
    
    Returns:
        Training results dictionary
    """
    print("🎯 Training roles classification model...")
    
    try:
        # Check for training data
        training_files = list(TRAINING_DIR.glob('*roles*.csv'))
        if not training_files:
            return {'error': 'No roles training data found'}
        
        # Use most recent training file
        latest_training = max(training_files, key=lambda f: f.stat().st_mtime)
        
        # Run training
        cmd = (
            f"cd /services/trainer/roles && "
            f"{TRAINER_CMD} train_roles.py --train-data {latest_training} "
            f"--model-output {MODELS_DIR}/roles_model --eval-split 0.2"
        )
        
        print(f"🔧 Running: {cmd}")
        result = os.system(cmd)
        
        if result == 0:
            print("✅ Roles model training completed successfully")
            return {
                'success': True,
                'model_path': f"{MODELS_DIR}/roles_model",
                'training_data': str(latest_training)
            }
        else:
            return {'error': f'Training failed with exit code {result}'}
            
    except Exception as e:
        print(f"❌ Roles training error: {e}")
        return {'error': str(e)}


def train_testrow_model(**context) -> Dict[str, Any]:
    """
    Train or retrain the test-row NER model
    
    Returns:
        Training results dictionary
    """
    print("🎯 Training test-row NER model...")
    
    try:
        # Check for training data
        training_files = list(TRAINING_DIR.glob('*testrow*.jsonl'))
        if not training_files:
            return {'error': 'No test-row training data found'}
        
        # Use most recent training file
        latest_training = max(training_files, key=lambda f: f.stat().st_mtime)
        
        # Run training
        cmd = (
            f"cd /services/trainer/testrow && "
            f"{TRAINER_CMD} train_testrow.py --train-data {latest_training} "
            f"--model-output {MODELS_DIR}/testrow_model --epochs 10"
        )
        
        print(f"🔧 Running: {cmd}")
        result = os.system(cmd)
        
        if result == 0:
            print("✅ Test-row model training completed successfully")
            return {
                'success': True,
                'model_path': f"{MODELS_DIR}/testrow_model",
                'training_data': str(latest_training)
            }
        else:
            return {'error': f'Training failed with exit code {result}'}
            
    except Exception as e:
        print(f"❌ Test-row training error: {e}")
        return {'error': str(e)}


def evaluate_models(**context) -> Dict[str, Any]:
    """
    Evaluate model performance on held-out test data
    
    Returns:
        Evaluation results dictionary
    """
    print("📊 Evaluating model performance...")
    
    results = {'roles': None, 'testrow': None, 'errors': []}
    
    try:
        # Evaluate roles model
        roles_cmd = (
            f"cd /services/trainer/roles && "
            f"{TRAINER_CMD} eval_roles.py --model {MODELS_DIR}/roles_model "
            f"--test-data {TRAINING_DIR}/*roles*.csv --output {DATA_DIR}/eval_roles.json"
        )
        
        if os.system(roles_cmd) == 0:
            eval_file = Path(DATA_DIR) / 'eval_roles.json'
            if eval_file.exists():
                with open(eval_file) as f:
                    results['roles'] = json.load(f)
                print("✅ Roles model evaluation completed")
        
        # Evaluate test-row model
        testrow_cmd = (
            f"cd /services/trainer/testrow && "
            f"{TRAINER_CMD} eval_testrow.py --model {MODELS_DIR}/testrow_model "
            f"--test-data {TRAINING_DIR}/*testrow*.jsonl --output {DATA_DIR}/eval_testrow.json"
        )
        
        if os.system(testrow_cmd) == 0:
            eval_file = Path(DATA_DIR) / 'eval_testrow.json'
            if eval_file.exists():
                with open(eval_file) as f:
                    results['testrow'] = json.load(f)
                print("✅ Test-row model evaluation completed")
    
    except Exception as e:
        results['errors'].append(f"Model evaluation failed: {str(e)}")
        print(f"❌ Evaluation error: {e}")
    
    return results


def archive_outputs(**context) -> Dict[str, Any]:
    """
    Archive completed outputs and clean up old files
    
    Returns:
        Archive results dictionary
    """
    print("🗄️  Archiving completed outputs...")
    
    try:
        # Create archive directory with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        archive_path = ARCHIVE_DIR / timestamp
        archive_path.mkdir(parents=True, exist_ok=True)
        
        # Archive completed jobs (older than 1 day)
        cutoff_time = datetime.now() - timedelta(days=1)
        
        archived_files = []
        for file_path in OUTBOX_DIR.glob('*.json'):
            file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
            if file_time < cutoff_time:
                # Move to archive
                new_path = archive_path / file_path.name
                file_path.rename(new_path)
                archived_files.append(str(new_path))
        
        # Clean up processing folder
        processing_dir = INBOX_DIR / 'processing'
        if processing_dir.exists():
            for file_path in processing_dir.glob('*'):
                file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                if file_time < cutoff_time:
                    file_path.unlink()  # Delete old processing files
        
        print(f"✅ Archived {len(archived_files)} files to {archive_path}")
        
        return {
            'archive_path': str(archive_path),
            'archived_files': len(archived_files),
            'timestamp': timestamp
        }
        
    except Exception as e:
        print(f"❌ Archive error: {e}")
        return {'error': str(e)}


def send_pipeline_report(**context) -> None:
    """Send pipeline execution report (if email configured)"""
    
    # Get results from previous tasks
    scan_result = context['task_instance'].xcom_pull(task_ids='scan_inbox')
    enqueue_result = context['task_instance'].xcom_pull(task_ids='enqueue_jobs')
    archive_result = context['task_instance'].xcom_pull(task_ids='archive_outputs')
    
    # Build report
    report = f"""
Lab AI Pipeline Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📥 Inbox Scan:
  - Files found: {len(scan_result) if scan_result else 0}

🚀 Job Submission:
  - Jobs submitted: {enqueue_result.get('success_count', 0) if enqueue_result else 0}
  - Errors: {enqueue_result.get('error_count', 0) if enqueue_result else 0}

🗄️  Archive:
  - Files archived: {archive_result.get('archived_files', 0) if archive_result else 0}

Pipeline completed successfully!
"""
    
    print(report)
    
    # Could send email if configured
    # email_config = Variable.get("email_config", deserialize_json=True, default_var={})
    # if email_config.get('enabled'):
    #     send_email(subject="Lab AI Pipeline Report", html_content=report)


# Task definitions
scan_task = PythonOperator(
    task_id='scan_inbox',
    python_callable=scan_inbox,
    dag=dag,
    doc_md="Scan inbox directory for new PDF files to process"
)

enqueue_task = PythonOperator(
    task_id='enqueue_jobs',
    python_callable=enqueue_jobs,
    dag=dag,
    doc_md="Submit found PDF files to the processing API"
)

# Weekly training branch
check_training_data = PythonOperator(
    task_id='check_training_data',
    python_callable=check_training_data_freshness,
    dag=dag,
    doc_md="Check if training data has been updated and models need retraining"
)

prepare_data_task = PythonOperator(
    task_id='prepare_training_data',
    python_callable=prepare_training_data,
    dag=dag,
    doc_md="Convert Label Studio exports to training format"
)

train_roles_task = PythonOperator(
    task_id='train_roles',
    python_callable=train_roles_model,
    dag=dag,
    doc_md="Train the roles classification model"
)

train_testrow_task = PythonOperator(
    task_id='train_testrow',
    python_callable=train_testrow_model,
    dag=dag,
    doc_md="Train the test-row NER model"
)

evaluate_task = PythonOperator(
    task_id='evaluate_models',
    python_callable=evaluate_models,
    dag=dag,
    trigger_rule=TriggerRule.ALL_DONE,  # Run even if training partially fails
    doc_md="Evaluate model performance on test data"
)

archive_task = PythonOperator(
    task_id='archive_outputs',
    python_callable=archive_outputs,
    dag=dag,
    doc_md="Archive old completed outputs and clean up directories"
)

report_task = PythonOperator(
    task_id='send_report',
    python_callable=send_pipeline_report,
    dag=dag,
    trigger_rule=TriggerRule.ALL_DONE,
    doc_md="Send pipeline execution report"
)

# Training barrier - only proceed if we should retrain
training_gateway = DummyOperator(
    task_id='training_needed',
    dag=dag
)

training_complete = DummyOperator(
    task_id='training_complete',
    dag=dag,
    trigger_rule=TriggerRule.ALL_DONE
)

# Define task dependencies
scan_task >> enqueue_task

# Main processing flow
enqueue_task >> archive_task >> report_task

# Training flow (runs on schedule, not every batch)
enqueue_task >> check_training_data
check_training_data >> training_gateway >> prepare_data_task

# Parallel training
prepare_data_task >> [train_roles_task, train_testrow_task]
[train_roles_task, train_testrow_task] >> training_complete

# Evaluation and reporting
training_complete >> evaluate_task >> report_task


# Create separate weekly training DAG
weekly_training_dag = DAG(
    'lab_pipeline_weekly_training',
    default_args=DEFAULT_ARGS,
    description='Weekly model training and evaluation',
    schedule_interval='@weekly',  # Run every Sunday
    catchup=False,
    max_active_runs=1,
    tags=['lab-ai', 'training', 'ml']
)

# Weekly training tasks (reuse functions with new DAG)
weekly_check = PythonOperator(
    task_id='check_training_data',
    python_callable=check_training_data_freshness,
    dag=weekly_training_dag
)

weekly_prepare = PythonOperator(
    task_id='prepare_training_data',
    python_callable=prepare_training_data,
    dag=weekly_training_dag
)

weekly_roles = PythonOperator(
    task_id='train_roles',
    python_callable=train_roles_model,
    dag=weekly_training_dag
)

weekly_testrow = PythonOperator(
    task_id='train_testrow',
    python_callable=train_testrow_model,
    dag=weekly_training_dag
)

weekly_eval = PythonOperator(
    task_id='evaluate_models',
    python_callable=evaluate_models,
    dag=weekly_training_dag,
    trigger_rule=TriggerRule.ALL_DONE
)

weekly_report = PythonOperator(
    task_id='send_training_report',
    python_callable=send_pipeline_report,
    dag=weekly_training_dag,
    trigger_rule=TriggerRule.ALL_DONE
)

# Weekly training dependencies
weekly_check >> weekly_prepare >> [weekly_roles, weekly_testrow] >> weekly_eval >> weekly_report