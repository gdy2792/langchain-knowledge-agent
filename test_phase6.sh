#!/bin/bash
# Phase 6 success check: two accounts, isolated data.
# Run this while `uv run uvicorn server.main:app` is running in another terminal.
#
# Paced with sleeps between /chat calls — each one costs up to 2 Voyage
# embedding calls (1 recall + 1 batched save of both turns), and Voyage's
# free tier caps at 3 requests/minute, so even 2 calls per turn needs
# real spacing to stay under that.
set -e

BASE_URL="http://127.0.0.1:8000"

echo "=== Signing up two test accounts (ok if they already exist) ==="
curl -s -X POST "$BASE_URL/auth/signup" -H "Content-Type: application/json" \
  -d '{"email":"alice@example.com","password":"testpass123"}' > /dev/null
curl -s -X POST "$BASE_URL/auth/signup" -H "Content-Type: application/json" \
  -d '{"email":"bob@example.com","password":"testpass123"}' > /dev/null

echo "=== Logging in as each ==="
ALICE_TOKEN=$(curl -s -X POST "$BASE_URL/auth/login" -H "Content-Type: application/json" \
  -d '{"email":"alice@example.com","password":"testpass123"}' | jq -r .access_token)
BOB_TOKEN=$(curl -s -X POST http://127.0.0.1:8000/auth/login -H "Content-Type: application/json" -d '{"email":"bob@example.com","password":"testpass123"}' | jq -r .access_token)
echo "Alice token: ${ALICE_TOKEN:0:20}..."
echo "Bob token:   ${BOB_TOKEN:0:20}..."

echo ""
echo "=== Alice tells the agent a fact about herself ==="
curl -s -N -X POST "$BASE_URL/chat" -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ALICE_TOKEN" \
  -d '{"message":"My favorite color is green."}' | grep final_answer

echo "(waiting 45s to stay under Voyage's free-tier rate limit...)"
sleep 45

echo ""
echo "=== Bob tells the agent a DIFFERENT fact about himself ==="
curl -s -N -X POST "$BASE_URL/chat" -H "Content-Type: application/json" \
  -H "Authorization: Bearer $BOB_TOKEN" \
  -d '{"message":"My favorite color is orange."}' | grep final_answer

echo "(waiting 45s...)"
sleep 45

echo ""
echo "=== Alice asks what her favorite color was (should say green) ==="
curl -s -N -X POST "$BASE_URL/chat" -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ALICE_TOKEN" \
  -d '{"message":"What did I say my favorite color was?"}' | grep final_answer

echo "(waiting 45s...)"
sleep 45

echo ""
echo "=== Bob asks the same question (should say orange, NOT green) ==="
curl -s -N -X POST "$BASE_URL/chat" -H "Content-Type: application/json" \
  -H "Authorization: Bearer $BOB_TOKEN" \
  -d '{"message":"What did I say my favorite color was?"}' | grep final_answer

echo ""
echo "=== Success check ==="
echo "PASS if: Alice's answer says green, Bob's answer says orange,"
echo "and neither answer mentions the other person's color."
