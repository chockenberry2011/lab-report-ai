#!/usr/bin/env python3
"""
Lab AI Client - Command line tool for testing the API + queue + worker system

Usage:
    python lab_ai_client.py --help
    python lab_ai_client.py submit --file sample.pdf
    python lab_ai_client.py submit --url https://example.com/report.pdf
    python lab_ai_client.py status JOB_ID
    python lab_ai_client.py download JOB_ID
    python lab_ai_client.py monitor JOB_ID
"""

import argparse
import json
import time
import sys
import requests
from pathlib import Path
from typing import Optional, Dict, Any

class LabAIClient:
    def __init__(self, api_url: str = "http://localhost:8000"):
        self.api_url = api_url.rstrip('/')
        self.session = requests.Session()
    
    def submit_file(self, file_path: Path, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Submit a PDF file for processing"""
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        url = f"{self.api_url}/jobs"
        
        with open(file_path, 'rb') as f:
            files = {'file': (file_path.name, f, 'application/pdf')}
            data = {'config': json.dumps(config or {})}
            
            response = self.session.post(url, files=files, data=data)
            response.raise_for_status()
            
            return response.json()
    
    def submit_url(self, pdf_url: str, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Submit a PDF URL for processing"""
        
        url = f"{self.api_url}/jobs"
        data = {
            'pdf_url': pdf_url,
            'config': json.dumps(config or {})
        }
        
        response = self.session.post(url, data=data)
        response.raise_for_status()
        
        return response.json()
    
    def get_status(self, job_id: str) -> Dict[str, Any]:
        """Get job status"""
        
        url = f"{self.api_url}/jobs/{job_id}"
        response = self.session.get(url)
        response.raise_for_status()
        
        return response.json()
    
    def download_result(self, job_id: str, output_path: Optional[Path] = None) -> Path:
        """Download job result"""
        
        url = f"{self.api_url}/results/{job_id}"
        response = self.session.get(url)
        response.raise_for_status()
        
        if not output_path:
            output_path = Path(f"lab_results_{job_id}.json")
        
        with open(output_path, 'wb') as f:
            f.write(response.content)
        
        return output_path
    
    def get_logs(self, job_id: str) -> Dict[str, Any]:
        """Get job logs"""
        
        url = f"{self.api_url}/jobs/{job_id}/logs"
        response = self.session.get(url)
        response.raise_for_status()
        
        return response.json()
    
    def cancel_job(self, job_id: str) -> Dict[str, Any]:
        """Cancel a job"""
        
        url = f"{self.api_url}/jobs/{job_id}"
        response = self.session.delete(url)
        response.raise_for_status()
        
        return response.json()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get system statistics"""
        
        url = f"{self.api_url}/stats"
        response = self.session.get(url)
        response.raise_for_status()
        
        return response.json()
    
    def health_check(self) -> Dict[str, Any]:
        """Check API health"""
        
        url = f"{self.api_url}/health"
        response = self.session.get(url)
        response.raise_for_status()
        
        return response.json()

def print_status(status_data: Dict[str, Any], verbose: bool = False):
    """Pretty print job status"""
    
    print(f"Job ID: {status_data['job_id']}")
    print(f"Status: {status_data['status']}")
    print(f"Created: {status_data['created_at']}")
    
    if status_data.get('started_at'):
        print(f"Started: {status_data['started_at']}")
    
    if status_data.get('completed_at'):
        print(f"Completed: {status_data['completed_at']}")
    
    if status_data.get('error'):
        print(f"❌ Error: {status_data['error']}")
    
    if status_data.get('result_url'):
        print(f"✅ Result available: {status_data['result_url']}")
    
    if verbose and status_data.get('progress'):
        print("\nProgress Details:")
        for stage, details in status_data['progress'].items():
            progress = details.get('progress', 'N/A')
            message = details.get('message', '')
            timestamp = details.get('timestamp', '')
            print(f"  {stage}: {progress}% - {message} ({timestamp})")

def monitor_job(client: LabAIClient, job_id: str, interval: int = 5):
    """Monitor job progress until completion"""
    
    print(f"Monitoring job {job_id}...")
    print("Press Ctrl+C to stop monitoring\n")
    
    try:
        while True:
            status = client.get_status(job_id)
            
            print(f"\r⏱️  Status: {status['status']}", end='', flush=True)
            
            if status['status'] in ['completed', 'failed', 'cancelled']:
                print(f"\n\n🎯 Final Status:")
                print_status(status, verbose=True)
                
                if status['status'] == 'completed' and status.get('result_url'):
                    print(f"\n📥 Downloading results...")
                    result_file = client.download_result(job_id)
                    print(f"✅ Results saved to: {result_file}")
                
                break
            
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print(f"\n\n⏹️  Monitoring stopped. Job {job_id} is still running.")
        print("Check status with: python lab_ai_client.py status " + job_id)

def main():
    parser = argparse.ArgumentParser(description="Lab AI Processing Client")
    parser.add_argument("--api-url", default="http://localhost:8000", help="API URL")
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Submit command
    submit_parser = subparsers.add_parser('submit', help='Submit a job')
    submit_group = submit_parser.add_mutually_exclusive_group(required=True)
    submit_group.add_argument('--file', type=Path, help='PDF file to process')
    submit_group.add_argument('--url', help='PDF URL to process')
    submit_parser.add_argument('--config', help='JSON config string')
    submit_parser.add_argument('--config-file', type=Path, help='JSON config file')
    submit_parser.add_argument('--monitor', action='store_true', help='Monitor job until completion')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Get job status')
    status_parser.add_argument('job_id', help='Job ID')
    status_parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed progress')
    
    # Download command
    download_parser = subparsers.add_parser('download', help='Download job result')
    download_parser.add_argument('job_id', help='Job ID')
    download_parser.add_argument('--output', '-o', type=Path, help='Output file path')
    
    # Monitor command
    monitor_parser = subparsers.add_parser('monitor', help='Monitor job progress')
    monitor_parser.add_argument('job_id', help='Job ID')
    monitor_parser.add_argument('--interval', type=int, default=5, help='Check interval in seconds')
    
    # Logs command
    logs_parser = subparsers.add_parser('logs', help='Get job logs')
    logs_parser.add_argument('job_id', help='Job ID')
    
    # Cancel command
    cancel_parser = subparsers.add_parser('cancel', help='Cancel a job')
    cancel_parser.add_argument('job_id', help='Job ID')
    
    # Stats command
    subparsers.add_parser('stats', help='Get system statistics')
    
    # Health command
    subparsers.add_parser('health', help='Check API health')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    client = LabAIClient(args.api_url)
    
    try:
        if args.command == 'submit':
            # Parse config
            config = {}
            if args.config:
                config = json.loads(args.config)
            elif args.config_file:
                with open(args.config_file) as f:
                    config = json.load(f)
            
            # Submit job
            if args.file:
                print(f"📤 Submitting file: {args.file}")
                result = client.submit_file(args.file, config)
            else:
                print(f"📤 Submitting URL: {args.url}")
                result = client.submit_url(args.url, config)
            
            print(f"✅ Job submitted successfully!")
            print(f"Job ID: {result['job_id']}")
            print(f"Status: {result['status']}")
            
            if args.monitor:
                print()
                monitor_job(client, result['job_id'])
        
        elif args.command == 'status':
            status = client.get_status(args.job_id)
            print_status(status, args.verbose)
        
        elif args.command == 'download':
            print(f"📥 Downloading results for job {args.job_id}...")
            result_file = client.download_result(args.job_id, args.output)
            print(f"✅ Results saved to: {result_file}")
        
        elif args.command == 'monitor':
            monitor_job(client, args.job_id, args.interval)
        
        elif args.command == 'logs':
            logs = client.get_logs(args.job_id)
            print(f"📋 Logs for job {args.job_id}:")
            for log_entry in logs['logs']:
                timestamp = log_entry.get('timestamp', '')
                stage = log_entry.get('stage', '')
                message = log_entry.get('message', '')
                print(f"  [{timestamp}] {stage}: {message}")
        
        elif args.command == 'cancel':
            result = client.cancel_job(args.job_id)
            print(f"🛑 {result['message']}")
        
        elif args.command == 'stats':
            stats = client.get_stats()
            print("📊 System Statistics:")
            print(f"  Total Jobs: {stats['total_jobs']}")
            print("  Status Distribution:")
            for status, count in stats['status_counts'].items():
                print(f"    {status}: {count}")
        
        elif args.command == 'health':
            health = client.health_check()
            print(f"🏥 API Health: {health['status']}")
            print(f"  Redis: {health.get('redis', 'unknown')}")
            print(f"  Celery: {health.get('celery', 'unknown')}")
            
    except requests.RequestException as e:
        print(f"❌ API Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()