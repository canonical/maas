#!/bin/bash
# Quick test script for the tether-script endpoint

set -e

# Configuration
MAAS_URL="${MAAS_URL:-http://localhost:5240}"
ENDPOINT="$MAAS_URL/MAAS/a/v3/tether-script"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "================================================"
echo "Testing ONIE Tether Script Endpoint"
echo "================================================"
echo "Endpoint: $ENDPOINT"
echo ""

# Test 1: Valid request
echo -e "${YELLOW}Test 1: Valid ONIE headers${NC}"
TEMP_FILE=$(mktemp)
HTTP_CODE=$(curl -s -w "%{http_code}" "$ENDPOINT" \
  -H "onie-serial-number: TEST-SWITCH-001" \
  -H "onie-eth-addr: 00:11:22:33:44:55" \
  -H "onie-vendor-id: dell_s5248f" \
  -H "onie-machine: dell_s5248f" \
  -H "onie-machine-rev: 1.0" \
  -H "onie-arch: x86_64" \
  -H "onie-security-key: test-key" \
  -H "onie-operation: install" \
  -H "onie-version: 2023.05" \
  -o "$TEMP_FILE")

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ Status Code: 200 OK${NC}"
    
    # Check shebang
    if head -n1 "$TEMP_FILE" | grep -q "#!/bin/sh"; then
        echo -e "${GREEN}✓ Script has valid shebang${NC}"
    else
        echo -e "${RED}✗ Script missing shebang${NC}"
        cat "$TEMP_FILE"
        rm "$TEMP_FILE"
        exit 1
    fi
    
    # Check MAC address
    if grep -q "MAC_ADDRESS=\"00:11:22:33:44:55\"" "$TEMP_FILE"; then
        echo -e "${GREEN}✓ Script contains correct MAC address${NC}"
    else
        echo -e "${RED}✗ Script has incorrect MAC address${NC}"
        grep "MAC_ADDRESS=" "$TEMP_FILE"
        rm "$TEMP_FILE"
        exit 1
    fi
    
    # Check API URL
    if grep -q "API_URL=\"$MAAS_URL\"" "$TEMP_FILE"; then
        echo -e "${GREEN}✓ Script contains correct API URL${NC}"
    else
        echo -e "${YELLOW}⚠ API URL might be different:${NC}"
        grep "API_URL=" "$TEMP_FILE"
    fi
    
    # Check script syntax
    if bash -n "$TEMP_FILE" 2>/dev/null; then
        echo -e "${GREEN}✓ Script has valid bash syntax${NC}"
    else
        echo -e "${RED}✗ Script has syntax errors${NC}"
        bash -n "$TEMP_FILE"
        rm "$TEMP_FILE"
        exit 1
    fi
    
    # Show script preview
    echo ""
    echo "Script preview (first 15 lines):"
    echo "-----------------------------------"
    head -n 15 "$TEMP_FILE"
    echo "..."
    echo "-----------------------------------"
    
    # Save for inspection
    SAVED_FILE="/tmp/maas-tether-script-test.sh"
    cp "$TEMP_FILE" "$SAVED_FILE"
    echo ""
    echo -e "${GREEN}✓ Full script saved to: $SAVED_FILE${NC}"
    
else
    echo -e "${RED}✗ Status Code: $HTTP_CODE (expected 200)${NC}"
    echo "Response:"
    cat "$TEMP_FILE"
    rm "$TEMP_FILE"
    exit 1
fi

rm "$TEMP_FILE"
echo ""

# Test 2: Missing headers (should fail)
echo -e "${YELLOW}Test 2: Missing ONIE headers (should fail)${NC}"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$ENDPOINT")

if [ "$HTTP_CODE" = "400" ]; then
    echo -e "${GREEN}✓ Status Code: 400 Bad Request (as expected)${NC}"
elif [ "$HTTP_CODE" = "422" ]; then
    echo -e "${GREEN}✓ Status Code: 422 Unprocessable Entity (as expected)${NC}"
else
    echo -e "${RED}✗ Status Code: $HTTP_CODE (expected 400 or 422)${NC}"
fi

echo ""
echo "================================================"
echo -e "${GREEN}All tests completed successfully!${NC}"
echo "================================================"
echo ""
echo "Next steps:"
echo "1. Inspect the full script: cat /tmp/maas-tether-script-test.sh"
echo "2. Check MAAS logs: journalctl -u maas-apiserver -f"
echo "3. Verify switch was registered: maas admin switches read"
