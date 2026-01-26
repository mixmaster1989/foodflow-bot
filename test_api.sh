#!/bin/bash
# API Endpoint Test Script v2
# Tests all FoodFlow API endpoints with real auth

BASE_URL="http://localhost:8001"
RESULTS_FILE="/home/user1/foodflow-bot/api_test_results.log"
TEST_USER_ID=432823154

echo "=== API ENDPOINT TESTS DATA SYNC ===" > $RESULTS_FILE
echo "Started: $(date)" >> $RESULTS_FILE
echo "=========================" >> $RESULTS_FILE

# 1. GET TOKEN
echo "🔑 Getting token for user $TEST_USER_ID..."
LOGIN_RESP=$(curl -s -X POST "$BASE_URL/api/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"telegram_id\": $TEST_USER_ID}")

TOKEN=$(echo "$LOGIN_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))")

if [ -z "$TOKEN" ]; then
    echo "❌ Failed to get token!"
    echo "Response: $LOGIN_RESP"
    exit 1
fi
echo "✅ Token received."

test_endpoint() {
    local method=$1
    local endpoint=$2
    local data=$3
    local auth=${4:-"true"}
    
    local curl_cmd="curl -s -w '\n%{http_code}' -X $method '$BASE_URL$endpoint'"
    
    if [ "$auth" == "true" ]; then
        curl_cmd="$curl_cmd -H 'Authorization: Bearer $TOKEN'"
    fi
    
    if [ -n "$data" ]; then
        curl_cmd="$curl_cmd -H 'Content-Type: application/json' -d '$data'"
    fi
    
    response=$(eval "$curl_cmd" 2>/dev/null)
    status_code=$(echo "$response" | tail -1)
    body=$(echo "$response" | sed '$d')
    
    if [[ "$status_code" =~ ^[0-9]+$ ]]; then
        if [ "$status_code" -ge 200 ] && [ "$status_code" -lt 300 ]; then
            echo "✅ $method $endpoint → $status_code"
            echo "✅ $method $endpoint → $status_code" >> $RESULTS_FILE
        else
            echo "❌ $method $endpoint → $status_code"
            echo "❌ $method $endpoint → $status_code" >> $RESULTS_FILE
            echo "   Body: ${body:0:100}..." >> $RESULTS_FILE
        fi
    else
        echo "💥 $method $endpoint → FAILED (no response)"
    fi
}

echo ""
echo "🧪 Testing API Endpoints..."
echo ""

# Root & Basic
test_endpoint GET "/" "" "false"
test_endpoint GET "/health" "" "false"
test_endpoint GET "/api/auth/me"

# Products
test_endpoint GET "/api/products"
test_endpoint GET "/api/products/53" # Existing ID from earlier check

# Consumption
test_endpoint GET "/api/consumption"

# Reports
test_endpoint GET "/api/reports/daily?date=2026-01-24"

# Shopping List (Fixed PUT)
test_endpoint GET "/api/shopping-list"
test_endpoint PUT "/api/shopping-list/1/buy"
test_endpoint PUT "/api/shopping-list/1/unbuy"

# Recipes
test_endpoint GET "/api/recipes/categories"

echo ""
echo "=== TEST COMPLETE ===" >> $RESULTS_FILE
echo ""
echo "📁 Results saved to: $RESULTS_FILE"

