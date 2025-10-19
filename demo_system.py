#!/usr/bin/env python3
"""
Lab AI System Demo - Demonstrate the complete API + queue + worker system

This script demonstrates:
1. API endpoints (POST /jobs, GET /jobs/{id}, GET /results/{id})
2. Queue system with Redis
3. Worker pipeline with full processing
4. Comprehensive confidence scoring
5. EHR-ready JSON output
"""

import json
import time
import tempfile
from pathlib import Path
from lab_ai_client import LabAIClient

def create_demo_pdf():
    """Create a simple demo PDF for testing"""
    
    # Note: In a real scenario, you'd have actual lab PDFs
    # For demo purposes, we'll simulate with a text file that gets "processed"
    demo_content = """
    LAB RESULTS REPORT
    Patient: John Doe
    DOB: 1980-01-15
    
    CHEMISTRY PANEL
    Glucose         95 mg/dL        70-100
    Sodium          140 mEq/L       136-145
    Potassium       4.2 mEq/L       3.5-5.1
    Chloride        102 mEq/L       98-107
    
    LIPID PANEL
    Total Cholesterol  180 mg/dL    <200
    HDL Cholesterol    55 mg/dL     >40
    LDL Cholesterol    110 mg/dL    <100
    Triglycerides      75 mg/dL     <150
    
    COMPLETE BLOOD COUNT
    WBC             7.2 K/uL        4.5-11.0
    RBC             4.5 M/uL        4.2-5.4
    Hemoglobin      14.2 g/dL       12.0-16.0
    Hematocrit      42.1 %          36.0-46.0
    Platelets       285 K/uL        150-450
    """
    
    # Create a temporary "PDF" file (text file for demo)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.pdf', delete=False) as f:
        f.write(demo_content)
        return Path(f.name)

def demo_api_workflow():
    """Demonstrate the complete API workflow"""
    
    print("🧪 Lab AI System Demo")
    print("=" * 60)
    
    # Initialize client
    client = LabAIClient()
    
    # 1. Check API health
    print("\n1️⃣  Checking API health...")
    try:
        health = client.health_check()
        print(f"   ✅ API Status: {health['status']}")
        print(f"   📊 Redis: {health.get('redis', 'unknown')}")
        print(f"   🔄 Celery: {health.get('celery', 'unknown')}")
    except Exception as e:
        print(f"   ❌ API not available: {e}")
        print("   💡 Make sure to start the system with: docker-compose up")
        return False
    
    # 2. Create demo PDF
    print("\n2️⃣  Creating demo lab report...")
    demo_pdf = create_demo_pdf()
    print(f"   📄 Demo PDF created: {demo_pdf}")
    
    # 3. Submit job
    print("\n3️⃣  Submitting processing job...")
    
    # Use high quality configuration
    config = {
        "extraction": {"dpi": 200, "extract_images": True},
        "composition": {
            "scoring": {
                "value_parse_threshold": 0.8,
                "unit_validity_threshold": 0.8,
                "panel_score_threshold": 0.7,
                "document_score_threshold": 0.75
            }
        }
    }
    
    try:
        job_result = client.submit_file(demo_pdf, config)
        job_id = job_result['job_id']
        print(f"   ✅ Job submitted successfully!")
        print(f"   🆔 Job ID: {job_id}")
        print(f"   📊 Status: {job_result['status']}")
    except Exception as e:
        print(f"   ❌ Job submission failed: {e}")
        return False
    
    # 4. Monitor progress
    print(f"\n4️⃣  Monitoring job progress...")
    
    max_wait = 300  # 5 minutes timeout
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        try:
            status = client.get_status(job_id)
            
            print(f"   ⏱️  Status: {status['status']}")
            
            # Show progress details if available
            if status.get('progress'):
                for stage, details in status['progress'].items():
                    message = details.get('message', '')
                    progress = details.get('progress', '')
                    if progress:
                        print(f"      📈 {stage}: {progress}% - {message}")
                    else:
                        print(f"      📝 {stage}: {message}")
            
            # Check if completed
            if status['status'] in ['completed', 'failed', 'cancelled']:
                break
            
            time.sleep(5)  # Wait 5 seconds before next check
            
        except Exception as e:
            print(f"   ⚠️  Status check failed: {e}")
            time.sleep(5)
    
    # 5. Get final status
    print(f"\n5️⃣  Final job status...")
    try:
        final_status = client.get_status(job_id)
        print(f"   📊 Final Status: {final_status['status']}")
        
        if final_status.get('error'):
            print(f"   ❌ Error: {final_status['error']}")
            return False
        
        if final_status['status'] != 'completed':
            print(f"   ⚠️  Job did not complete successfully")
            return False
        
    except Exception as e:
        print(f"   ❌ Failed to get final status: {e}")
        return False
    
    # 6. Download results
    print(f"\n6️⃣  Downloading results...")
    try:
        result_file = client.download_result(job_id)
        print(f"   ✅ Results downloaded: {result_file}")
        
        # Parse and display key results
        with open(result_file) as f:
            results = json.load(f)
        
        doc_info = results.get('document_info', {})
        panels = results.get('lab_panels', [])
        
        print(f"\n   📋 Processing Summary:")
        print(f"      📄 Document Score: {doc_info.get('document_score', 'N/A'):.3f}")
        print(f"      🔍 Needs Review: {doc_info.get('needs_review', 'N/A')}")
        print(f"      🧪 Total Panels: {len(panels)}")
        print(f"      🔬 Total Tests: {doc_info.get('total_tests', 0)}")
        
        if doc_info.get('confidence_distribution'):
            dist = doc_info['confidence_distribution']
            print(f"      📊 Confidence Range: {dist.get('min', 0):.2f} - {dist.get('max', 1):.2f}")
            print(f"      📈 Confidence Mean: {dist.get('mean', 0):.2f}")
        
        print(f"\n   🧪 Panel Details:")
        for i, panel in enumerate(panels, 1):
            score = panel.get('panel_score', 0)
            needs_review = panel.get('needs_review', False)
            test_count = panel.get('test_count', 0)
            review_icon = "❌" if needs_review else "✅"
            
            print(f"      Panel {i}: {panel.get('name', 'Unknown')} {review_icon}")
            print(f"        Score: {score:.3f} | Tests: {test_count}")
            
            if needs_review and panel.get('review_reasons'):
                reasons = ', '.join(panel['review_reasons'][:2])  # Show first 2 reasons
                print(f"        Issues: {reasons}")
    
    except Exception as e:
        print(f"   ❌ Failed to download results: {e}")
        return False
    
    # 7. Get processing logs
    print(f"\n7️⃣  Getting processing logs...")
    try:
        logs = client.get_logs(job_id)
        print(f"   📋 Processing Log Entries: {len(logs.get('logs', []))}")
        
        # Show last few log entries
        for log_entry in logs.get('logs', [])[-5:]:  # Last 5 entries
            stage = log_entry.get('stage', '')
            message = log_entry.get('message', '')
            print(f"      📝 {stage}: {message}")
    
    except Exception as e:
        print(f"   ⚠️  Failed to get logs: {e}")
    
    # 8. System stats
    print(f"\n8️⃣  System statistics...")
    try:
        stats = client.get_stats()
        print(f"   📊 Total Jobs Processed: {stats.get('total_jobs', 0)}")
        
        status_counts = stats.get('status_counts', {})
        for status, count in status_counts.items():
            if count > 0:
                print(f"      {status}: {count}")
    
    except Exception as e:
        print(f"   ⚠️  Failed to get stats: {e}")
    
    # Cleanup
    try:
        demo_pdf.unlink()  # Remove temp demo PDF
    except:
        pass
    
    print(f"\n🎉 Demo completed successfully!")
    print(f"✅ Full pipeline working: PDF → Extractor → Roles → Headers → TestRows → Composer → Confidence → JSON")
    
    return True

def demo_url_processing():
    """Demo processing from URL"""
    
    print("\n" + "=" * 60)
    print("🌐 URL Processing Demo")
    
    # Example URL (replace with actual lab report URL)
    pdf_url = "https://example.com/sample_lab_report.pdf"
    
    client = LabAIClient()
    
    try:
        print(f"📤 Submitting URL: {pdf_url}")
        result = client.submit_url(pdf_url)
        print(f"✅ Job {result['job_id']} submitted for URL processing")
        
    except Exception as e:
        print(f"⚠️  URL demo skipped (no valid URL): {e}")

def demo_concurrent_jobs():
    """Demo multiple concurrent job processing"""
    
    print("\n" + "=" * 60) 
    print("🔄 Concurrent Processing Demo")
    
    client = LabAIClient()
    
    # Submit multiple jobs
    job_ids = []
    for i in range(3):
        try:
            demo_pdf = create_demo_pdf()
            result = client.submit_file(demo_pdf, {"test_job": i+1})
            job_ids.append(result['job_id'])
            print(f"📤 Job {i+1} submitted: {result['job_id']}")
            demo_pdf.unlink()
        except Exception as e:
            print(f"❌ Failed to submit job {i+1}: {e}")
    
    print(f"⚡ {len(job_ids)} concurrent jobs submitted")
    print("💡 Worker concurrency=1, so jobs will be processed sequentially")

if __name__ == '__main__':
    print("🚀 Starting Lab AI System Demo...")
    
    # Run main demo
    success = demo_api_workflow()
    
    if success:
        # Run additional demos
        demo_url_processing()
        demo_concurrent_jobs()
        
        print(f"\n🎯 All demos completed!")
        print(f"💡 Try the CLI tool:")
        print(f"   python lab_ai_client.py submit --file your_lab_report.pdf --monitor")
        print(f"   python lab_ai_client.py stats")
        print(f"   python lab_ai_client.py health")
        
        print(f"\n🔧 System URLs:")
        print(f"   API: http://localhost:8000")
        print(f"   API Docs: http://localhost:8000/docs")
        print(f"   Flower (monitoring): http://localhost:5555")
    
    else:
        print(f"\n❌ Demo failed - check that the system is running")
        print(f"💡 Start with: docker-compose up -d")