#!/bin/bash

# Complete Transfer Flow Test Script
# Tests the two-condition gate for incoming transfers
# Citizen ID: 6787452390

set -e

CITIZEN_ID="6787452390"
CITIZEN_NAME="Complete Flow Test"
CITIZEN_EMAIL="complete.test@example.com"

echo "======================================================================"
echo "🧪 TESTING COMPLETE TRANSFER FLOW WITH TWO-CONDITION GATE"
echo "======================================================================"
echo "Citizen ID: $CITIZEN_ID"
echo "Name: $CITIZEN_NAME"
echo ""

# Step 1: Initiate Transfer
echo "======================================================================"
echo "STEP 1: Initiate Transfer"
echo "======================================================================"
echo "Sending POST request to /api/v1/citizens/transfer/receive/"

RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/citizens/transfer/receive/ \
  -H "Content-Type: application/json" \
  -d "{
    \"id\": \"$CITIZEN_ID\",
    \"citizenName\": \"$CITIZEN_NAME\",
    \"citizenEmail\": \"$CITIZEN_EMAIL\",
    \"urlDocuments\": {
      \"URL1\": [\"http://example.com/doc1.pdf\"],
      \"URL2\": [\"http://example.com/doc2.pdf\"]
    },
    \"confirmAPI\": \"http://localhost:8000/api/v1/test/confirm\"
  }")

echo "Response: $RESPONSE"
echo ""

# Verify initial state
echo "Checking initial database state..."
docker exec citizen-affiliation-service-web-1 python manage.py shell -c "
from affiliation.models import Citizen, Affiliation
citizen = Citizen.objects.get(citizen_id='$CITIZEN_ID')
affiliation = Affiliation.objects.filter(citizen=citizen).first()
print('✅ Citizen created:')
print(f'   is_verified: {citizen.is_verified} (expected: False)')
print(f'   verification_status: {citizen.verification_status} (expected: pending)')
print(f'   is_registered: {citizen.is_registered} (expected: False)')
print('✅ Affiliation created:')
print(f'   status: {affiliation.status} (expected: TRANSFERRING)')
print(f'   documents_ready: {affiliation.documents_ready} (expected: False)')
"
echo ""
sleep 2

# Step 2: Simulate documents.ready event
echo "======================================================================"
echo "STEP 2: Simulate documents.ready Event"
echo "======================================================================"
echo "Publishing to documents.ready queue..."

docker exec citizen-affiliation-service-web-1 python -c "
import pika, json, os
connection = pika.BlockingConnection(pika.ConnectionParameters(
    host=os.getenv('RABBITMQ_HOST', 'rabbitmq'),
    port=int(os.getenv('RABBITMQ_PORT', 5672)),
    credentials=pika.PlainCredentials(os.getenv('RABBITMQ_USER', 'admin'), os.getenv('RABBITMQ_PASS', 'admin'))
))
channel = connection.channel()
channel.basic_publish(exchange='', routing_key='documents.ready', body=json.dumps({'idCitizen': '$CITIZEN_ID'}))
print('✅ Published documents.ready event')
connection.close()
"
echo ""
sleep 3

# Verify intermediate state
echo "Checking intermediate state (after documents ready)..."
docker exec citizen-affiliation-service-web-1 python manage.py shell -c "
from affiliation.models import Citizen, Affiliation
citizen = Citizen.objects.get(citizen_id='$CITIZEN_ID')
affiliation = Affiliation.objects.filter(citizen=citizen).first()
print('State after documents.ready:')
print(f'   documents_ready: {affiliation.documents_ready} (expected: True)')
print(f'   is_verified: {citizen.is_verified} (expected: False)')
print(f'   status: {affiliation.status} (expected: TRANSFERRING)')
print('')
if affiliation.documents_ready and not citizen.is_verified and affiliation.status == 'TRANSFERRING':
    print('✅ Correct! Still waiting for MINTIC verification')
else:
    print('❌ Unexpected state!')
"
echo ""
sleep 2

# Step 3: Simulate register.citizen.completed event
echo "======================================================================"
echo "STEP 3: Simulate register.citizen.completed Event (MINTIC SUCCESS)"
echo "======================================================================"
echo "Publishing to register.citizen.completed queue with statusCode 201..."

docker exec citizen-affiliation-service-web-1 python -c "
import pika, json, os
connection = pika.BlockingConnection(pika.ConnectionParameters(
    host=os.getenv('RABBITMQ_HOST', 'rabbitmq'),
    port=int(os.getenv('RABBITMQ_PORT', 5672)),
    credentials=pika.PlainCredentials(os.getenv('RABBITMQ_USER', 'admin'), os.getenv('RABBITMQ_PASS', 'admin'))
))
channel = connection.channel()
channel.basic_publish(exchange='', routing_key='register.citizen.completed', body=json.dumps({'id': '$CITIZEN_ID', 'statusCode': 201}))
print('✅ Published register.citizen.completed event (statusCode: 201)')
connection.close()
"
echo ""
sleep 3

# Verify final state
echo "======================================================================"
echo "STEP 4: Verify Final State"
echo "======================================================================"
docker exec citizen-affiliation-service-web-1 python manage.py shell -c "
from affiliation.models import Citizen, Affiliation
citizen = Citizen.objects.get(citizen_id='$CITIZEN_ID')
affiliation = Affiliation.objects.filter(citizen=citizen).first()
print('='*70)
print('FINAL STATE - Transfer Complete')
print('='*70)
print(f'Citizen ID: {citizen.citizen_id}')
print(f'Name: {citizen.name}')
print(f'Email: {citizen.email}')
print('')
print('MINTIC Registration:')
print(f'  is_registered: {citizen.is_registered}')
print(f'  is_verified: {citizen.is_verified}')
print(f'  verification_status: {citizen.verification_status}')
print('')
print('Transfer Status:')
print(f'  status: {affiliation.status}')
print(f'  documents_ready: {affiliation.documents_ready}')
print('')
print('='*70)
if citizen.is_registered and citizen.is_verified and affiliation.status == 'AFFILIATED' and affiliation.documents_ready:
    print('✅ ✅ ✅ SUCCESS! Both conditions met, transfer completed!')
    print('   1. Documents downloaded ✅')
    print('   2. MINTIC verification ✅')
else:
    print('❌ FAILED! Expected all conditions to be met')
    print(f'   is_registered={citizen.is_registered} (expected: True)')
    print(f'   is_verified={citizen.is_verified} (expected: True)')
    print(f'   status={affiliation.status} (expected: AFFILIATED)')
    print(f'   documents_ready={affiliation.documents_ready} (expected: True)')
print('='*70)
"

echo ""
echo "======================================================================"
echo "🎉 TEST COMPLETE"
echo "======================================================================"
