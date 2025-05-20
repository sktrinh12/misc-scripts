#!/bin/bash

input=$(cat)

echo "$input" | awk -F',' '
NR == 1 {
    # Print the header
    printf "| %s |\n", $0;
    # Print the separator
    gsub(/[^,]/, "-", $0);
    gsub(/,/, " | ", $0);
    printf "|%s|\n", $0;
}
NR > 1 {
    # Print the rows
    printf "| %s |\n", $0;
}' | sed 's/,/ | /g'
