#!/bin/bash

if [ ! -f .token ]; then
    echo "Error: .token file not found" >&2
    exit 1
fi

ACCESS_TOKEN=$(<.token)

# ips=(
#   '34.193.198.229'
#   '208.194.0.82'
#   '5.15.17.116'
#   '155.190.19.7'
#   '155.190.19.5'
#   '155.190.19.6'
#   '44.223.4.17'
#   '100.26.190.180'
#   '54.80.153.169'
#   '54.159.249.63'
#   '3.85.192.9'
#   '54.80.122.65'
#   '54.242.130.240'
#   '89.206.28.23'
#   '3.80.168.71'
#   '68.89.69.72'
#   '18.209.177.153'
#   '54.198.140.42'
#   '54.209.227.161'
#   '54.81.46.251'
#   '54.162.221.22'
#   '54.237.243.164'
# )

# 98.225.244.16
# 34.193.198.229
# 52.19.194.143
# 73.233.38.184
# 198.13.63.194
# 174.96.78.242
# 64.226.128.35
# 208.194.0.82
# 70.16.129.211
# 64.226.129.162
# 165.76.184.134

ips=(
'34.193.198.229'
'198.13.63.194'
'208.194.0.82'
'125.14.64.218'
'136.47.167.201'
'98.225.244.16'
'52.19.194.143'
'89.206.28.23'
'212.93.150.142'
'172.56.148.186'
'73.233.38.184'
'201.233.198.229'
'70.16.129.211'
'174.96.78.242'
'64.226.128.35'
)

json_array="$(printf '"%s",' "${ips[@]}")"
json_array="[${json_array%,}]"  # Remove trailing comma and wrap in brackets

response=$(curl -s -X POST \
  -H "Content-Type: application/json" \
  --data "$json_array" \
  "https://ipinfo.io/batch?token=$ACCESS_TOKEN")

if [ -n "$response" ]; then
  output_file="ip_info_output_$(date +'%Y-%m-%d').json"
  echo "$response" > "$output_file"
  echo "Data successfully saved to $output_file"
else
  echo "Failed to get a response from the API."
fi
