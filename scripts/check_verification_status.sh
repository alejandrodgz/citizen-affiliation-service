#!/bin/bash
# Quick script to check citizen verification status

CITIZEN_ID=$1

if [ -z "$CITIZEN_ID" ]; then
    echo "Usage: ./check_verification_status.sh CITIZEN_ID"
    exit 1
fi

docker exec citizen-affiliation-service-web-1 python manage.py shell -c "
from affiliation.models import Citizen, Affiliation

try:
    citizen = Citizen.objects.get(citizen_id='$CITIZEN_ID')
    affiliation = Affiliation.objects.filter(citizen=citizen).first()
    
    print('='*60)
    print(f'👤 CITIZEN: {citizen.name} ({citizen.citizen_id})')
    print('='*60)
    print(f'✓ is_verified: {citizen.is_verified}')
    print(f'✓ verification_status: {citizen.verification_status}')
    print(f'✓ verification_message: {citizen.verification_message}')
    print(f'✓ pending_deletion: {citizen.pending_deletion}')
    if affiliation:
        print(f'✓ affiliation.status: {affiliation.status}')
    print('='*60)
except Exception as e:
    print(f'❌ Error: {e}')
"
