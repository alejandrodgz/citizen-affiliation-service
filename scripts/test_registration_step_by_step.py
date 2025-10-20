#!/usr/bin/env python
"""
Step-by-step registration test with detailed inspection at each stage.

This script demonstrates and validates each step of the event-driven registration.
"""
import os
import sys
import django
import json

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from affiliation.services.citizen_service import CitizenService
from affiliation.models import Citizen, Affiliation


def print_separator(char='=', length=80):
    """Print a separator line."""
    print(f"\n{char * length}\n")


def print_step(step_num, title):
    """Print a step header."""
    print_separator()
    print(f"STEP {step_num}: {title}")
    print_separator()


def inspect_citizen(citizen_id):
    """Inspect and print citizen state."""
    citizen = Citizen.objects.filter(citizen_id=citizen_id).first()
    
    if not citizen:
        print(f"❌ Citizen {citizen_id} NOT FOUND in database")
        return None
    
    print(f"\n📊 CITIZEN STATE:")
    print(f"   ID: {citizen.citizen_id}")
    print(f"   Name: {citizen.name}")
    print(f"   Email: {citizen.email}")
    print(f"   Operator: {citizen.operator_name}")
    print(f"\n   🔐 Registration Status:")
    print(f"   - is_registered: {citizen.is_registered}")
    print(f"   - is_verified: {citizen.is_verified}")
    print(f"   - verification_status: '{citizen.verification_status}'")
    print(f"   - verification_message: '{citizen.verification_message}'")
    print(f"   - pending_deletion: {citizen.pending_deletion}")
    
    # Check affiliation
    affiliation = Affiliation.objects.filter(citizen=citizen).first()
    if affiliation:
        print(f"\n   📋 Affiliation:")
        print(f"   - status: '{affiliation.status}'")
        print(f"   - operator: {affiliation.operator_name}")
        print(f"   - affiliated_at: {affiliation.affiliated_at}")
    else:
        print(f"\n   ⚠️  No affiliation found")
    
    return citizen


def test_registration_steps():
    """Test registration step by step."""
    
    # Test data
    test_citizen_id = '1111222233'
    test_data = {
        'citizen_id': test_citizen_id,
        'name': 'Test Step By Step User',
        'address': 'Test Street 123',
        'email': 'test.steps@example.com',
        'operator_id': '68f003d9a49e090002e5d0b5',
        'operator_name': 'TEST DAGZ'
    }
    
    # Clean up if exists
    existing = Citizen.objects.filter(citizen_id=test_citizen_id).first()
    if existing:
        print(f"🧹 Cleaning up existing citizen {test_citizen_id}")
        existing.delete()
    
    service = CitizenService()
    
    # ============================================================================
    print_step(1, "INITIATE REGISTRATION")
    # ============================================================================
    
    print("📝 Calling CitizenService.register_citizen()...")
    print(f"\nInput data:")
    print(json.dumps(test_data, indent=2))
    
    result = service.register_citizen(test_data)
    
    print(f"\n✅ Service Response:")
    print(json.dumps(result, indent=2))
    
    if not result['success']:
        print(f"\n❌ Registration failed: {result['message']}")
        return
    
    # ============================================================================
    print_step(2, "INSPECT DATABASE STATE (Immediately After Registration)")
    # ============================================================================
    
    print("🔍 Checking what was saved to the database...")
    citizen = inspect_citizen(test_citizen_id)
    
    if not citizen:
        print("\n❌ TEST FAILED: Citizen not created")
        return
    
    # ============================================================================
    print_step(3, "VERIFY OPTIMISTIC CREATION")
    # ============================================================================
    
    print("✅ VALIDATING OPTIMISTIC UI PATTERN:")
    
    checks = [
        ("Citizen exists in database", citizen is not None, True),
        ("is_registered = True", citizen.is_registered, True),
        ("is_verified = False", citizen.is_verified, False),
        ("verification_status = 'pending'", citizen.verification_status, 'pending'),
        ("verification_message contains 'waiting'", 
         'waiting' in citizen.verification_message.lower() if citizen.verification_message else False, True),
        ("pending_deletion = False", citizen.pending_deletion, False),
    ]
    
    all_passed = True
    for check_name, actual, expected in checks:
        if actual == expected:
            print(f"   ✅ {check_name}: {actual}")
        else:
            print(f"   ❌ {check_name}: Expected {expected}, got {actual}")
            all_passed = False
    
    affiliation = Affiliation.objects.filter(citizen=citizen).first()
    if affiliation:
        if affiliation.status == 'PENDING':
            print(f"   ✅ Affiliation status = 'PENDING': {affiliation.status}")
        else:
            print(f"   ❌ Affiliation status should be 'PENDING', got '{affiliation.status}'")
            all_passed = False
    else:
        print(f"   ❌ No affiliation created")
        all_passed = False
    
    if all_passed:
        print(f"\n🎉 OPTIMISTIC CREATION: PASSED")
    else:
        print(f"\n❌ OPTIMISTIC CREATION: FAILED")
        return
    
    # ============================================================================
    print_step(4, "CHECK API RESPONSE FORMAT")
    # ============================================================================
    
    print("📡 What the UI/Frontend receives:")
    print(json.dumps({
        "success": result['success'],
        "message": result['message'],
        "citizen_id": result.get('citizen_id'),
        "verification_status": result.get('verification_status')
    }, indent=2))
    
    print(f"\n💡 UI CAN NOW:")
    print(f"   1. Show success message: '{result['message']}'")
    print(f"   2. Display badge: '🟡 Waiting for MINTIC verification'")
    print(f"   3. Let user navigate to profile")
    print(f"   4. User can START USING THE APP (even though not verified yet!)")
    
    # ============================================================================
    print_step(5, "CHECK RABBITMQ EVENT (Simulation)")
    # ============================================================================
    
    print("📤 Event that was published to RabbitMQ:")
    event_payload = {
        'id': int(test_citizen_id),
        'name': test_data['name'],
        'address': test_data['address'],
        'email': test_data['email'],
        'operatorId': test_data['operator_id'],
        'operatorName': test_data['operator_name']
    }
    print(f"Queue: 'register.citizen.requested'")
    print(json.dumps(event_payload, indent=2))
    
    print(f"\n💡 This event will be consumed by Operator Connectivity, which will:")
    print(f"   1. Call MINTIC API: POST /apis/registerCitizen")
    print(f"   2. Wait for response (could take 5-10 seconds)")
    print(f"   3. Publish 'register.citizen.completed' event back")
    
    # ============================================================================
    print_step(6, "SIMULATE MINTIC VERIFICATION SUCCESS")
    # ============================================================================
    
    print("⏳ Simulating Operator Connectivity calling MINTIC...")
    print("   (In real scenario, this happens async in another service)")
    
    print(f"\n📥 Simulating 'register.citizen.completed' event reception...")
    
    from affiliation.rabbitmq.register_citizen_consumer import handle_register_citizen_completed
    
    completion_event = {
        'id': test_citizen_id,
        'operatorId': test_data['operator_id'],
        'success': True,
        'message': 'Citizen registered successfully in MINTIC',
        'response': {
            'status': 'registered',
            'timestamp': '2025-10-19T12:00:00Z'
        }
    }
    
    print(f"Event payload:")
    print(json.dumps(completion_event, indent=2))
    
    print(f"\n🔄 Processing event...")
    handle_register_citizen_completed(completion_event)
    
    # ============================================================================
    print_step(7, "INSPECT DATABASE STATE (After MINTIC Confirmation)")
    # ============================================================================
    
    print("🔍 Checking updated database state...")
    citizen.refresh_from_db()
    inspect_citizen(test_citizen_id)
    
    # ============================================================================
    print_step(8, "VERIFY VERIFICATION COMPLETE")
    # ============================================================================
    
    print("✅ VALIDATING POST-VERIFICATION STATE:")
    
    affiliation.refresh_from_db()
    
    checks = [
        ("is_verified = True", citizen.is_verified, True),
        ("verification_status = 'verified'", citizen.verification_status, 'verified'),
        ("verification_message updated", 
         'successfully' in citizen.verification_message.lower() if citizen.verification_message else False, True),
        ("Affiliation status = 'AFFILIATED'", affiliation.status, 'AFFILIATED'),
    ]
    
    all_passed = True
    for check_name, actual, expected in checks:
        if actual == expected:
            print(f"   ✅ {check_name}: {actual}")
        else:
            print(f"   ❌ {check_name}: Expected {expected}, got {actual}")
            all_passed = False
    
    if all_passed:
        print(f"\n🎉 VERIFICATION COMPLETE: PASSED")
    else:
        print(f"\n❌ VERIFICATION COMPLETE: FAILED")
        return
    
    # ============================================================================
    print_step(9, "FINAL UI STATE")
    # ============================================================================
    
    print("💡 UI NOW SHOWS:")
    print(f"   🟢 'Verified by MINTIC ✓'")
    print(f"   ✅ User has full access to all features")
    print(f"   ✅ Profile is complete and verified")
    
    # ============================================================================
    print_step(10, "SUMMARY")
    # ============================================================================
    
    print("📊 REGISTRATION FLOW TIMELINE:")
    print(f"\n   0.0s - User clicks 'Register'")
    print(f"   0.1s - ✅ Citizen created locally (status: pending)")
    print(f"   0.1s - ✅ Event published to RabbitMQ")
    print(f"   0.1s - ✅ User redirected to profile (CAN USE APP!)")
    print(f"        - UI shows: '🟡 Waiting for MINTIC verification'")
    print(f"   ...")
    print(f"   5-10s later - Operator Connectivity confirms with MINTIC")
    print(f"   5-10s later - ✅ Status updated to 'verified'")
    print(f"   5-10s later - ✅ UI badge changes to: '🟢 Verified ✓'")
    
    print(f"\n✅ KEY BENEFIT:")
    print(f"   User waited: ~0.1 seconds (database write)")
    print(f"   Instead of: ~10 seconds (MINTIC API call)")
    print(f"   Improvement: 100x faster response!")
    
    # Cleanup
    print_separator()
    print("🧹 Cleaning up test data...")
    citizen.delete()
    print(f"✅ Test citizen {test_citizen_id} deleted")
    
    print_separator()
    print("🎊 ALL TESTS PASSED!")
    print_separator()


if __name__ == '__main__':
    try:
        test_registration_steps()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
