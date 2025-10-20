#!/usr/bin/env python
"""
Test script for event-driven citizen registration/unregistration.

This script demonstrates the new optimistic UI pattern:
1. Register citizen → creates locally with pending verification
2. Simulate Operator Connectivity confirming registration
3. Delete citizen → marks as pending deletion
4. Simulate Operator Connectivity confirming unregistration

Usage:
    python scripts/test_event_driven_registration.py
"""
import os
import sys
import django
import time
import json

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from affiliation.services.citizen_service import CitizenService
from affiliation.models import Citizen, Affiliation


def print_section(title):
    """Print a formatted section header."""
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}\n")


def test_event_driven_registration():
    """Test the full event-driven registration flow."""
    
    print_section("EVENT-DRIVEN REGISTRATION TEST")
    
    # Test citizen data
    test_citizen = {
        'citizen_id': '9999888877',
        'name': 'Test Event Driven User',
        'address': 'Calle 123 #45-67',
        'email': 'test.events@example.com',
        'operator_id': '68f003d9a49e090002e5d0b5',
        'operator_name': 'TEST DAGZ'
    }
    
    service = CitizenService()
    
    # Step 1: Register citizen (creates locally with pending verification)
    print("📝 Step 1: Registering citizen (optimistic creation)...")
    result = service.register_citizen(test_citizen)
    print(f"Result: {json.dumps(result, indent=2)}")
    
    if not result['success']:
        print("❌ Registration failed, stopping test")
        return
    
    # Check citizen state
    citizen = Citizen.objects.filter(citizen_id=test_citizen['citizen_id']).first()
    if citizen:
        print(f"\n✅ Citizen created locally:")
        print(f"   - ID: {citizen.citizen_id}")
        print(f"   - Name: {citizen.name}")
        print(f"   - Registered: {citizen.is_registered}")
        print(f"   - Verified: {citizen.is_verified}")
        print(f"   - Status: {citizen.verification_status}")
        print(f"   - Message: {citizen.verification_message}")
        
        affiliation = Affiliation.objects.filter(citizen=citizen).first()
        if affiliation:
            print(f"   - Affiliation Status: {affiliation.status}")
    
    # Step 2: Simulate Operator Connectivity confirming registration
    print("\n⏳ Step 2: Simulating MINTIC verification (waiting 2 seconds)...")
    time.sleep(2)
    
    print("📥 Simulating register.citizen.completed event...")
    # This would normally come from Operator Connectivity via RabbitMQ
    from affiliation.rabbitmq.register_citizen_consumer import handle_register_citizen_completed
    
    completion_event = {
        'id': test_citizen['citizen_id'],
        'operatorId': test_citizen['operator_id'],
        'success': True,
        'message': 'Citizen registered successfully in MINTIC',
        'response': {}
    }
    
    handle_register_citizen_completed(completion_event)
    
    # Check updated citizen state
    citizen.refresh_from_db()
    print(f"\n✅ Citizen after MINTIC verification:")
    print(f"   - Verified: {citizen.is_verified}")
    print(f"   - Status: {citizen.verification_status}")
    print(f"   - Message: {citizen.verification_message}")
    
    affiliation.refresh_from_db()
    print(f"   - Affiliation Status: {affiliation.status}")
    
    # Step 3: Delete citizen (marks as pending deletion)
    print_section("EVENT-DRIVEN UNREGISTRATION TEST")
    
    print("🗑️  Step 3: Deleting citizen (marking for deletion)...")
    delete_result = service.delete_affiliation(test_citizen['citizen_id'])
    print(f"Result: {json.dumps(delete_result, indent=2)}")
    
    # Check citizen state
    citizen.refresh_from_db()
    print(f"\n✅ Citizen marked for deletion:")
    print(f"   - Pending Deletion: {citizen.pending_deletion}")
    print(f"   - Message: {citizen.verification_message}")
    
    affiliation.refresh_from_db()
    print(f"   - Affiliation Status: {affiliation.status}")
    
    # Step 4: Simulate Operator Connectivity confirming unregistration
    print("\n⏳ Step 4: Simulating MINTIC unregister confirmation (waiting 2 seconds)...")
    time.sleep(2)
    
    print("📥 Simulating unregister.citizen.completed event...")
    from affiliation.rabbitmq.unregister_citizen_consumer import handle_unregister_citizen_completed
    
    unregister_event = {
        'id': test_citizen['citizen_id'],
        'operatorId': test_citizen['operator_id'],
        'success': True,
        'message': 'Citizen unregistered successfully from MINTIC',
        'response': {}
    }
    
    handle_unregister_citizen_completed(unregister_event)
    
    # Check if citizen was deleted
    citizen_exists = Citizen.objects.filter(citizen_id=test_citizen['citizen_id']).exists()
    if not citizen_exists:
        print(f"\n✅ Citizen successfully deleted after MINTIC confirmation")
    else:
        print(f"\n❌ Citizen still exists (unexpected)")
    
    print_section("TEST COMPLETED")


def test_failed_verification():
    """Test registration with failed MINTIC verification."""
    
    print_section("FAILED VERIFICATION TEST")
    
    test_citizen = {
        'citizen_id': '8888777766',
        'name': 'Test Failed Verification',
        'address': 'Calle 456 #78-90',
        'email': 'test.failed@example.com',
        'operator_id': '68f003d9a49e090002e5d0b5',
        'operator_name': 'TEST DAGZ'
    }
    
    service = CitizenService()
    
    # Register citizen
    print("📝 Registering citizen...")
    result = service.register_citizen(test_citizen)
    print(f"Result: {json.dumps(result, indent=2)}")
    
    if not result['success']:
        print("❌ Registration failed, stopping test")
        return
    
    # Simulate failed verification
    print("\n⏳ Simulating MINTIC verification failure...")
    time.sleep(1)
    
    from affiliation.rabbitmq.register_citizen_consumer import handle_register_citizen_completed
    
    failed_event = {
        'id': test_citizen['citizen_id'],
        'operatorId': test_citizen['operator_id'],
        'success': False,
        'message': 'Citizen already registered in another operator',
        'error': {
            'message': 'El ciudadano ya se encuentra registrado en el operador: OtherOperator'
        }
    }
    
    handle_register_citizen_completed(failed_event)
    
    # Check citizen state
    citizen = Citizen.objects.filter(citizen_id=test_citizen['citizen_id']).first()
    if citizen:
        print(f"\n⚠️  Citizen after failed verification:")
        print(f"   - Verified: {citizen.is_verified}")
        print(f"   - Status: {citizen.verification_status}")
        print(f"   - Message: {citizen.verification_message}")
        
        affiliation = Affiliation.objects.filter(citizen=citizen).first()
        if affiliation:
            print(f"   - Affiliation Status: {affiliation.status}")
    
    # Cleanup
    print("\n🧹 Cleaning up failed citizen...")
    citizen.delete()
    
    print_section("FAILED VERIFICATION TEST COMPLETED")


if __name__ == '__main__':
    try:
        test_event_driven_registration()
        print("\n" + "="*80 + "\n")
        test_failed_verification()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
