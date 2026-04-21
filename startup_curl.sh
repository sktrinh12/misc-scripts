#!/bin/bash

PROFILE=${1:-default}

# colors
BOLD='\033[1m'
CYAN='\033[0;36m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
RESET='\033[0m'

divider() {
  echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
}

row() {
  printf "  ${BOLD}%-15s${RESET} %s\n" "$1" "$2"
}

divider
echo -e "  ${BOLD}🔒 VPN STATUS CHECK${RESET}   profile: ${YELLOW}${PROFILE}${RESET}"
divider

IP_ADDR=$(curl -s icanhazip.com)
DATA=$(curl -s "http://ip-api.com/json/${IP_ADDR}")
STATUS=$(echo "$DATA" | jq -r '.status')

if [[ "$STATUS" != "success" ]]; then
  echo -e "  ${RED}Failed to resolve IP info${RESET}"
  exit 1
fi

row "Status"      "$(echo "$DATA" | jq -r '.status')"
row "IP"          "$(echo "$DATA" | jq -r '.query')"
row "Country"     "$(echo "$DATA" | jq -r '.country') ($(echo "$DATA" | jq -r '.countryCode'))"
row "Region"      "$(echo "$DATA" | jq -r '.regionName') ($(echo "$DATA" | jq -r '.region'))"
row "City"        "$(echo "$DATA" | jq -r '.city')"
row "Zip"         "$(echo "$DATA" | jq -r '.zip')"
row "Coordinates" "$(echo "$DATA" | jq -r '.lat'), $(echo "$DATA" | jq -r '.lon')"
row "Timezone"    "$(echo "$DATA" | jq -r '.timezone')"
row "ISP"         "$(echo "$DATA" | jq -r '.isp')"
row "Org"         "$(echo "$DATA" | jq -r '.org')"
row "AS"          "$(echo "$DATA" | jq -r '.as')"

divider
echo -e "  ${BOLD}🖥  EC2 Instance${RESET}"
divider

"$HOME/Documents/scripts/terraform/wireguard-ec2/config/device_scripts/ec2_describe.sh" "us-east-1" "$PROFILE"

divider
