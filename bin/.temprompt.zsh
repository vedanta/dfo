# Disable theme prompt builders for this session
prompt() {}
build_left_prompt() {}
build_right_prompt() {}
precmd_functions=()

# Our own precmd that sets a 2-line prompt
precmd() {
  PROMPT='%F{blue}%~%f
%F{cyan}⟡ ▶ %f'
}

# Apply immediately once
precmd

echo "Two-line temporary prompt active for this session."

