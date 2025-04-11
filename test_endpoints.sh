#!/bin/bash

# Basic test script for simple-telegram-mcp endpoints

# --- Configuration ---
# Use your own User ID (Saved Messages) for chat-specific tests
TARGET_USER_ID="976142936"
# Command to run the MCP server
SERVER_CMD="uv run simple-telegram-mcp"
# Unique text for test messages to avoid conflicts
TEST_MSG_BASE="MCP Auto Test $(date +%s)"
# Emoji for reaction test
TEST_REACTION="👍" # Unicode: \ud83d\udc4d

# --- Variables ---
PASSED_COUNT=0
FAILED_COUNT=0
TEST_RESULTS=() # Array to store full status lines like "test_name ... ok/FAILED"
FAILED_TESTS=()

# --- Helper Function ---
run_test() {
  TEST_NAME="$1"
  CMD="$2"
  # Print test name without newline
  echo -n "$TEST_NAME ... " >&2
  # Execute command and capture only its stdout
  CMD_OUTPUT=$(eval "$CMD" 2>&1) # Still capture stderr in case mcpt prints errors there
  EXIT_CODE=$?
  # Check exit code and update counters/arrays
  if [ $EXIT_CODE -ne 0 ]; then
    echo "FAILED" >&2 # Print status on same line
    FAILED_COUNT=$((FAILED_COUNT + 1))
    # Store detailed failure info if needed later, or just the status line
    TEST_RESULTS+=("$TEST_NAME ... FAILED (Exit Code: $EXIT_CODE)")
    # Optionally print failure details immediately to stderr
    echo "Captured Output on Failure:" >&2
    echo "$CMD_OUTPUT" >&2
    echo "---------------------------------" >&2
  else
    echo "ok" >&2 # Print status on same line
    PASSED_COUNT=$((PASSED_COUNT + 1))
    TEST_RESULTS+=("$TEST_NAME ... ok")
  fi
  # Echo the *actual command output* to stdout for command substitution capture
  echo "$CMD_OUTPUT"
}

# --- Tests ---

echo "Starting MCP Endpoint Tests..."
echo "Target User ID (Saved Messages): $TARGET_USER_ID"
echo "Server Command: $SERVER_CMD"
echo

# 1. Login Status
run_test "telegram_login_status" "mcpt call telegram_login_status $SERVER_CMD"

# 2. List Chats
run_test "telegram_list_chats" "mcpt call telegram_list_chats --params '{\"limit\": 5}' $SERVER_CMD"

# 3. Search Chats
run_test "telegram_search_chats" "mcpt call telegram_search_chats --params '{\"query\": \"Telegram\"}' $SERVER_CMD" # Search for a common term

# 4. Get User Profile (Self)
run_test "telegram_get_user_profile (self)" "mcpt call telegram_get_user_profile --params '{\"user_id\": $TARGET_USER_ID}' $SERVER_CMD"

# 5. Post Message (to Saved Messages)
POST_MSG_TEXT="$TEST_MSG_BASE - Post"
# Capture the clean stdout from run_test (which is the command's output)
POST_OUTPUT=$(run_test "telegram_post_message" "mcpt call telegram_post_message --params '{\"chat_id\": $TARGET_USER_ID, \"text\": \"$POST_MSG_TEXT\"}' $SERVER_CMD")
# Display the captured output (optional, could be removed if too verbose)
echo "Captured Post Message Output:" >&2
echo "$POST_OUTPUT"
# Attempt to parse the (now cleaner) output using jq
# Use grep with potential leading space allowance
POST_MSG_ID=$(echo "$POST_OUTPUT" | jq -r '.message_id // empty') # Use jq, default to empty if null/missing

if [[ -z "$POST_MSG_ID" || ! "$POST_MSG_ID" =~ ^[0-9]+$ ]]; then
  echo "!!! WARNING: Could not extract valid message_id from post_message output. Skipping dependent tests. !!!"
  POST_MSG_ID="" # Ensure it's empty if invalid
else
  echo "Extracted Post Message ID: $POST_MSG_ID"
  echo

  # 6. Reply To Message (Requires Post Message ID)
  REPLY_MSG_TEXT="$TEST_MSG_BASE - Reply"
  # Capture the clean stdout from run_test
  REPLY_OUTPUT=$(run_test "telegram_reply_to_message" "mcpt call telegram_reply_to_message --params '{\"chat_id\": $TARGET_USER_ID, \"message_id\": $POST_MSG_ID, \"text\": \"$REPLY_MSG_TEXT\"}' $SERVER_CMD")
  # Display the captured output (optional)
  echo "Captured Reply Message Output:" >&2
  echo "$REPLY_OUTPUT"
  # Attempt to parse the (now cleaner) output using jq
  # Use grep with potential leading space allowance
  REPLY_MSG_ID=$(echo "$REPLY_OUTPUT" | jq -r '.message_id // empty') # Use jq, default to empty if null/missing

  if [[ -z "$REPLY_MSG_ID" || ! "$REPLY_MSG_ID" =~ ^[0-9]+$ ]]; then
    echo "!!! WARNING: Could not extract valid message_id from reply_to_message output. Skipping reaction test. !!!"
    REPLY_MSG_ID="" # Ensure it's empty if invalid
  else
    echo "Extracted Reply Message ID: $REPLY_MSG_ID"
    echo

    # 7. Add Reaction (Requires Reply Message ID)
    run_test "telegram_add_reaction" "mcpt call telegram_add_reaction --params '{\"chat_id\": $TARGET_USER_ID, \"message_id\": $REPLY_MSG_ID, \"reaction\": \"$TEST_REACTION\"}' $SERVER_CMD"
  fi

  # 8. Get Chat History (Saved Messages)
  run_test "telegram_get_chat_history" "mcpt call telegram_get_chat_history --params '{\"chat_id\": $TARGET_USER_ID, \"limit\": 5}' $SERVER_CMD"

  # 9. Search Messages (Saved Messages)
  run_test "search_telegram_messages" "mcpt call search_telegram_messages --params '{\"chat_id\": $TARGET_USER_ID, \"query\": \"$TEST_MSG_BASE\", \"limit\": 5}' $SERVER_CMD"

fi

echo # Newline after tests >&2
echo "--- Test Execution Finished ---" >&2
echo # Newline >&2

# --- Summary ---
TOTAL_TESTS=$((PASSED_COUNT + FAILED_COUNT))
echo "================== TEST SUMMARY ==================" >&2
# Print individual results collected
for result_line in "${TEST_RESULTS[@]}"; do
  echo "$result_line" >&2
done
echo "--------------------------------------------------" >&2
echo " Total Tests Run: $TOTAL_TESTS" >&2
echo " Passed: $PASSED_COUNT" >&2
echo " Failed: $FAILED_COUNT" >&2
echo "================================================" >&2

# Exit with failure code if any test failed
if [ $FAILED_COUNT -ne 0 ]; then
  exit 1
fi

# Note: This script uses 'jq' for JSON parsing. Ensure it is installed.
# Error handling is basic; it checks exit codes but doesn't validate output content deeply.