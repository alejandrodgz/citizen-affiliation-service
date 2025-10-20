#!/usr/bin/env python
"""
Quick test script to verify RabbitMQ integration.
Run this after starting RabbitMQ and Django server.
"""
import os
import sys
import django

# Setup Django environment
sys.path.insert(0, '/home/alejo/citizen-affiliation-service')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from affiliation.rabbitmq.publisher import publish_user_transferred

def test_rabbitmq_connection():
    """Test RabbitMQ connection and event publishing."""
    print("🧪 Testing RabbitMQ Integration\n")
    print("=" * 50)
    
    # Test publishing an event
    test_id = 999999999
    print(f"\n1️⃣  Publishing test event for citizen ID: {test_id}")
    
    result = publish_user_transferred(test_id)
    
    if result:
        print("✅ Event published successfully!")
        print(f"\n📬 Event sent to queue: user.transferred")
        print(f"📦 Message: {{\"idCitizen\": {test_id}}}")
        print("\n✨ Check RabbitMQ Management UI:")
        print("   URL: http://localhost:15672")
        print("   Username: admin")
        print("   Password: admin")
        print("   Go to Queues → user.transferred → Get Messages")
    else:
        print("❌ Failed to publish event")
        print("\n⚠️  Possible issues:")
        print("   1. RabbitMQ is not running")
        print("   2. Connection settings are incorrect")
        print("   3. Check Django logs for errors")
        print("\n🔧 Try:")
        print("   docker-compose up -d rabbitmq")
    
    print("\n" + "=" * 50)

if __name__ == '__main__':
    test_rabbitmq_connection()
