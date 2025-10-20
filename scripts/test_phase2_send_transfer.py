"""
Test script for Phase 2: Sending Transfers

This script tests the outgoing transfer functionality where we send
a citizen to another operator.

Usage:
    python scripts/test_phase2_send_transfer.py <citizen_id>

Example:
    python scripts/test_phase2_send_transfer.py 999888777
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import requests
from affiliation.models import Citizen, Affiliation


def test_send_transfer(citizen_id):
    """Test sending a transfer to another operator."""
    
    print(f"\n{'='*60}")
    print(f"Testing Phase 2: Send Transfer for Citizen {citizen_id}")
    print(f"{'='*60}\n")
    
    # Check if citizen exists
    try:
        citizen = Citizen.objects.get(citizen_id=citizen_id)
        affiliation = citizen.affiliation
        
        print(f"✅ Citizen found:")
        print(f"   Name: {citizen.name}")
        print(f"   Email: {citizen.email}")
        print(f"   Status: {affiliation.status}")
        print(f"   Registered: {citizen.is_registered}")
        
        if affiliation.status != 'AFFILIATED':
            print(f"\n❌ Cannot transfer: Citizen status is {affiliation.status}")
            print(f"   Expected: AFFILIATED")
            return
            
    except Citizen.DoesNotExist:
        print(f"❌ Citizen {citizen_id} not found")
        print(f"\n💡 To test Phase 2, first create a citizen:")
        print(f"   1. Register a new citizen:")
        print(f'      curl -X POST http://localhost:8000/api/v1/citizens/register/ \\')
        print(f'        -H "Content-Type: application/json" \\')
        print(f"        -d '{{\"id\": \"{citizen_id}\", \"name\": \"Test User\", \"address\": \"123 St\", \"email\": \"test@example.com\"}}'")
        print(f"\n   2. Then run this script again")
        return
    
    print(f"\n{'='*60}")
    print(f"Test Scenario: Send to Mock Operator")
    print(f"{'='*60}\n")
    
    # Prepare test data
    target_operator = {
        "targetOperatorId": "mock-operator-123",
        "targetOperatorName": "Mock Test Operator",
        "targetApiUrl": "http://httpbin.org/post"  # Mock endpoint that accepts POST
    }
    
    print(f"📤 Sending transfer request...")
    print(f"   Target: {target_operator['targetOperatorName']}")
    print(f"   API: {target_operator['targetApiUrl']}")
    
    # Send transfer request
    response = requests.post(
        f"http://localhost:8000/api/v1/citizens/{citizen_id}/transfer/",
        json=target_operator
    )
    
    print(f"\n📊 Response Status: {response.status_code}")
    print(f"📄 Response Body:")
    print(f"   {response.json()}")
    
    if response.status_code == 200:
        print(f"\n✅ Transfer request sent successfully!")
        
        # Check database state
        citizen.refresh_from_db()
        affiliation.refresh_from_db()
        
        print(f"\n📊 Updated Database State:")
        print(f"   Status: {affiliation.status}")
        print(f"   Destination Operator: {affiliation.transfer_destination_operator_name}")
        print(f"   Transfer Started: {affiliation.transfer_started_at}")
        
        print(f"\n{'='*60}")
        print(f"Next Steps: Simulate Confirmation")
        print(f"{'='*60}\n")
        
        print(f"To complete the transfer, simulate the receiving operator")
        print(f"sending a confirmation:")
        print(f"\n1. Success confirmation (deletes citizen locally):")
        print(f'   curl -X POST http://localhost:8000/api/v1/citizens/transfer/confirm/ \\')
        print(f'     -H "Content-Type: application/json" \\')
        print(f'     -d \'{{"id": {citizen_id}, "req_status": 1}}\'')
        
        print(f"\n2. Failure confirmation (rolls back to AFFILIATED):")
        print(f'   curl -X POST http://localhost:8000/api/v1/citizens/transfer/confirm/ \\')
        print(f'     -H "Content-Type: application/json" \\')
        print(f'     -d \'{{"id": {citizen_id}, "req_status": 0}}\'')
        
    else:
        print(f"\n❌ Transfer request failed!")
        print(f"   Error: {response.json().get('message', 'Unknown error')}")
    
    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/test_phase2_send_transfer.py <citizen_id>")
        print("Example: python scripts/test_phase2_send_transfer.py 999888777")
        sys.exit(1)
    
    citizen_id = sys.argv[1]
    test_send_transfer(citizen_id)
