import os

from dotenv import load_dotenv, find_dotenv
from fastmcp import FastMCP



_INSTRUCTIONS = """A server for Recruitee API"""

if find_dotenv() != "":
    load_dotenv(find_dotenv())

RECRUITEE_COMPANY_ID = os.getenv("RECRUITEE_COMPANY_ID")
RECRUITEE_API_TOKEN = os.getenv("RECRUITEE_API_TOKEN")
BASE_DEPLOY_URL = os.getenv("BASE_DEPLOY_URL")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

# Parse ALLOWED_DOMAINS from comma-separated string to list
_allowed_domains_str = os.getenv("ALLOWED_DOMAINS", "appunite.com,appunite.pl,appunite.net")
ALLOWED_DOMAINS = [domain.strip() for domain in _allowed_domains_str.split(",") if domain.strip()]

# Initialize the MCP server
mcp = FastMCP(
    name="Recruitee Server",
    instructions=_INSTRUCTIONS,
)
