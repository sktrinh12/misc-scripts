#!/bin/bash

PROFILE=${1:-chom}

echo "PROFILE: $PROFILE"

IP_ADDR=$(curl -s icanhazip.com)
curl -s "http://ip-api.com/json/${IP_ADDR}" | jq '.'

echo -e "\n=====================================\n"

"$HOME/Documents/scripts/terraform/wireguard-ec2/config/device_scripts/ec2_describe.sh" "us-east-1" "$PROFILE"
