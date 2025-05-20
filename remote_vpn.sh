#!/bin/bash

if [ "$#" -lt 2 ] || [ "$#" -gt 4 ]; then
  echo "Usage: ./remote_create.sh <create|destroy> <0|1> [opt - poweroff]"
  exit 1
fi

# 1 is profile=chom, 0 is profile=default

REMOTE_USER="root"
REMOTE_HOST="192.168.1.1"
REMOTE_DIR="/root/wireguard-ec2/config/router_scripts"
REMOTE_SCRIPT=""
ACTION="$1"
PROFILE="$2"
POWEROFF="$3"

if [[ "$PROFILE" != "0" && "$PROFILE" != "1" ]]; then
  echo "Error: The second argument (PROFILE) must be either 0 or 1"
  exit 1
fi

if [ "$ACTION" == "create" ]; then
  REMOTE_SCRIPT="create.sh"
elif [ "$ACTION" == "destroy" ]; then
  REMOTE_SCRIPT="destroy.sh"
else
  echo "Invalid action: choose 'create' or 'destroy'"
  exit 1
fi

ssh "$REMOTE_USER@$REMOTE_HOST" "cd ${REMOTE_DIR} && ./${REMOTE_SCRIPT} ${PROFILE} ${POWEROFF}"
