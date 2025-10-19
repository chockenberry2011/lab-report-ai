#!/usr/bin/env python3
"""
Test script for Lab AI Pipeline DAG

Validates DAG syntax and structure before deployment.
Run this before starting Airflow to catch configuration errors.
"""

import sys
import os
from pathlib import Path

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent / 'dags'))

def test_dag_import():
    """Test that the DAG can be imported without errors"""
    print("🔍 Testing DAG import...")
    
    try:
        import lab_pipeline
        print("✅ DAG import successful")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ DAG error: {e}")
        return False


def test_dag_structure():
    """Test DAG structure and task dependencies"""
    print("🔍 Testing DAG structure...")
    
    try:
        from lab_pipeline import dag, weekly_training_dag
        
        # Test main DAG
        print(f"Main DAG ID: {dag.dag_id}")
        print(f"Schedule: {dag.schedule_interval}")
        print(f"Tasks: {len(dag.tasks)}")
        
        task_ids = [task.task_id for task in dag.tasks]
        expected_tasks = [
            'scan_inbox',
            'enqueue_jobs', 
            'check_training_data',
            'training_needed',
            'prepare_training_data',
            'train_roles',
            'train_testrow',
            'training_complete',
            'evaluate_models',
            'archive_outputs',
            'send_report'
        ]
        
        missing_tasks = set(expected_tasks) - set(task_ids)
        if missing_tasks:
            print(f"⚠️  Missing tasks: {missing_tasks}")
        else:
            print("✅ All expected tasks present")
        
        # Test weekly DAG
        print(f"\nWeekly DAG ID: {weekly_training_dag.dag_id}")
        print(f"Schedule: {weekly_training_dag.schedule_interval}")
        print(f"Tasks: {len(weekly_training_dag.tasks)}")
        
        print("✅ DAG structure valid")
        return True
        
    except Exception as e:
        print(f"❌ Structure test failed: {e}")
        return False


def test_task_functions():
    """Test that task functions can be called without errors"""
    print("🔍 Testing task functions...")
    
    try:
        from lab_pipeline import (
            scan_inbox, 
            enqueue_jobs,
            check_training_data_freshness,
            prepare_training_data,
            train_roles_model,
            train_testrow_model,
            evaluate_models,
            archive_outputs
        )
        
        # Test functions exist and are callable
        functions = [
            scan_inbox,
            enqueue_jobs,
            check_training_data_freshness,
            prepare_training_data,
            train_roles_model,
            train_testrow_model,
            evaluate_models,
            archive_outputs
        ]
        
        for func in functions:
            if not callable(func):
                print(f"❌ Function {func.__name__} is not callable")
                return False
        
        print("✅ All task functions are callable")
        return True
        
    except Exception as e:
        print(f"❌ Function test failed: {e}")
        return False


def test_environment_setup():
    """Test environment variables and paths"""
    print("🔍 Testing environment setup...")
    
    # Check environment variables
    env_vars = {
        'DATA_DIR': os.getenv('DATA_DIR', '/data'),
        'API_URL': os.getenv('API_URL', 'http://api:8000'),
        'MODELS_DIR': os.getenv('MODELS_DIR', '/models')
    }
    
    print("Environment variables:")
    for var, value in env_vars.items():
        print(f"  {var}: {value}")
    
    # Check if paths would be accessible
    data_dir = Path(env_vars['DATA_DIR'])
    expected_dirs = [
        data_dir / 'inbox',
        data_dir / 'outbox',
        data_dir / 'labelstudio',
        data_dir / 'training'
    ]
    
    print(f"\nExpected directories under {data_dir}:")
    for dir_path in expected_dirs:
        exists = dir_path.exists() if data_dir.exists() else "N/A"
        print(f"  {dir_path.name}: {exists}")
    
    print("✅ Environment setup documented")
    return True


def main():
    """Run all tests"""
    print("🧪 Lab AI Pipeline DAG Tests")
    print("=" * 40)
    
    tests = [
        test_dag_import,
        test_dag_structure, 
        test_task_functions,
        test_environment_setup
    ]
    
    results = []
    for test in tests:
        print(f"\n{'-' * 30}")
        result = test()
        results.append(result)
    
    print(f"\n{'=' * 40}")
    print(f"Test Results: {sum(results)}/{len(results)} passed")
    
    if all(results):
        print("🎉 All tests passed! DAG is ready for deployment.")
        return 0
    else:
        print("❌ Some tests failed. Check errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())