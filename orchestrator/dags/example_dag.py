from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator

default_args = {
    'owner': 'lab-ai',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5)
}

dag = DAG(
    'lab_ai_pipeline',
    default_args=default_args,
    description='Lab AI processing pipeline',
    schedule_interval=timedelta(hours=1),
    catchup=False
)

def extract_data():
    print("Extracting data...")
    return "Data extracted"

def train_model():
    print("Training model...")
    return "Model trained"

extract_task = PythonOperator(
    task_id='extract_data',
    python_callable=extract_data,
    dag=dag
)

train_task = PythonOperator(
    task_id='train_model',
    python_callable=train_model,
    dag=dag
)

health_check = BashOperator(
    task_id='health_check',
    bash_command='echo "Pipeline health check completed"',
    dag=dag
)

extract_task >> train_task >> health_check