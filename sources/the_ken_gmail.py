"""
Fetches The Ken newsletter content from Gmail when cookie auth isn't available.

Prerequisites:
  - Gmail MCP must be connected in Claude Code settings
  - The Ken subscription email must be delivered to your Gmail inbox

This module is called by the pipeline only when THE_KEN_SESSION_COOKIE is not set.
It is designed to be invoked manually or via the Claude Code MCP integration,
not as a standalone async fetcher — Gmail access requires the MCP tool calls
which run in the Claude agent, not directly in Python.

Usage: run `python sources/the_ken_gmail.py` and follow the prompt to paste
the Gmail thread content, or integrate with the Gmail MCP in the dashboard's
/run-now route.
"""

# Placeholder — actual Gmail MCP calls happen at the Claude agent layer.
# When THE_KEN_SESSION_COOKIE is set in .env, this module is not needed.
# To use Gmail instead:
#   1. Reconnect Gmail in Claude Code → Settings → Integrations
#   2. Ask Claude: "Fetch today's Ken newsletter from my Gmail and add it to the digest"

print("The Ken Gmail integration: use Claude Code with Gmail MCP connected.")
print("Alternatively, set THE_KEN_SESSION_COOKIE in your .env file.")
