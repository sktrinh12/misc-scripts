#!/bin/bash

PORT=5317
HTTP_LOG_FILE="/tmp/http_server.log"
TEAMS_LOG_FILE="/tmp/teams_for_linux.log"
TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")

echo "==========================" > $HTTP_LOG_FILE
echo "  HTTP Server Log started at: $TIMESTAMP" >> $HTTP_LOG_FILE
echo "==========================" >> $HTTP_LOG_FILE

echo "==========================" > $TEAMS_LOG_FILE
echo "  Teams for Linux Log started at: $TIMESTAMP" >> $TEAMS_LOG_FILE
echo "==========================" >> $TEAMS_LOG_FILE

cd $HOME/Pictures

if lsof -i :$PORT &> /dev/null; then
  # Port is in use, get the PID of the process and kill it
  PID=$(lsof -t -i :$PORT)
  echo "Port $PORT is already in use by PID $PID, killing it..." >> $HTTP_LOG_FILE
  kill -9 $PID
  echo "Killed process $PID, starting new http-server..." >> $HTTP_LOG_FILE
else
  echo "Port $PORT is available, starting http-server..." >> $HTTP_LOG_FILE
fi

npx http-server -p $PORT --cors "*" -g -c-1 >> $HTTP_LOG_FILE 2>&1 &
sleep 0.5
teams-for-linux --isCustomBackgroundEnabled=true "--customBGServiceBaseUrl=http://localhost:$PORT" >> $TEAMS_LOG_FILE 2>&1 &
