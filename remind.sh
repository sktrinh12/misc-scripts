#!/bin/bash

path_dir="$HOME/Documents/scripts/dot-files/zsh_fx"
message="REMINDER: Time to wrap up your work! Or create a 'norun.lock' file to prevent the VPN from shutting down. There are 15 mins remaining!"

for session in $(tmux list-sessions -F '#{session_name}'); do
  for window in $(tmux list-windows -t $session -F '#{window_index}'); do
    for pane in $(tmux list-panes -t $session:$window -F '#{pane_id}'); do
      # pane_strip=${pane#%}
      tmux send-keys -t "${session}:${window}.${pane}" C-z
      sleep 0.25 
      tmux send-keys -t "${session}:${window}.${pane}" "clear" C-m
      sleep 0.25 
      tmux send-keys -t "${session}:${window}.${pane}" \
        "${path_dir}/cowsay-prompt.sh '$message'" C-m
      # echo "Session: $session, Window: $window, Pane: $pane_strip"
    done
  done
done
