from dataclasses import dataclass
from datetime import datetime
import os
import httpx

import markdown

from src.utils.server_config import mcp, RECRUITEE_COMPANY_ID, RECRUITEE_API_TOKEN, BASE_DEPLOY_URL



_API = f"https://api.recruitee.com/c/{RECRUITEE_COMPANY_ID}"
_HEADERS = {"Authorization": f"Bearer {RECRUITEE_API_TOKEN}"}
_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


async def _get(path: str, params: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            resp = await client.get(f"{_API}{path}", headers=_HEADERS, params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            raise ValueError(f"Recruitee API failed: {e.response.status_code}, {e.response.text}")


def iso_to_unix(iso_string: str) -> int:
    """
    Converts an ISO 8601 formatted date string to a Unix timestamp (seconds since epoch).
    Args:
        iso_string (str): ISO date string like '2025-05-20T12:30:00Z' or '2025-05-20T12:30:00+00:00'
    Returns:
        int: Unix timestamp (seconds since 1970-01-01T00:00:00Z)
    """
    try:
        dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        return int(dt.timestamp())
    except Exception as e:
        raise ValueError(f"Invalid ISO date string: {iso_string}") from e


@mcp.tool()
async def markdown_to_url(markdown_str: str) -> str:
    """Convert Markdown text to HTML, save it to the documents directory, and return URL to access it."""
    if not markdown_str:
        return ""
    if not BASE_DEPLOY_URL:
        raise ValueError("BASE_URL environment variable must be set to generate document URLs")
    
    try:
        html = markdown.markdown(
            markdown_str,
            extensions=["extra", "codehilite"]
        )
        
        full_html = f"""<!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Generated Report</title>
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 40px 20px;
                    line-height: 1.6;
                    background-color: #f5f5f5;
                }}
                .container {{
                    background: white;
                    padding: 60px 80px;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    margin: 0 auto;
                }}
                h1, h2, h3, h4, h5, h6 {{
                    color: #333;
                }}
                img {{
                    max-width: 100%;
                    height: auto;
                    border-radius: 4px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                    margin: 10px 0;
                }}
                code {{
                    background-color: #f8f9fa;
                    padding: 2px 4px;
                    border-radius: 3px;
                    font-family: 'Courier New', monospace;
                }}
                pre {{
                    background-color: #f8f9fa;
                    padding: 15px;
                    border-radius: 5px;
                    overflow-x: auto;
                }}
                table {{
                    border-collapse: collapse;
                    width: 100%;
                    margin: 20px 0;
                }}
                th, td {{
                    border: 1px solid #ddd;
                    padding: 12px;
                    text-align: left;
                }}
                th {{
                    background-color: #f8f9fa;
                }}
                blockquote {{
                    border-left: 4px solid #007bff;
                    margin: 0;
                    padding-left: 20px;
                    color: #666;
                }}
                
                /* Responsive adjustments */
                @media (max-width: 768px) {{
                    body {{
                        padding: 20px 10px;
                    }}
                    .container {{
                        padding: 30px 20px;
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="container">
                {html}
            </div>
        </body>
        </html>"""

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"report_{timestamp}.html"
        documents_dir = "/data"
        os.makedirs(documents_dir, exist_ok=True)
        file_path = os.path.join(documents_dir, filename)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(full_html)
        return f"{BASE_DEPLOY_URL}/documents/{filename}"
        
    except Exception as e:
        raise ValueError(f"Error converting Markdown to HTML file: {e}") from e


@dataclass
class Record:
    id: str
    title: str
    text: str
    metadata: dict


RECORDS = [
    Record(id="123", title="John Doe", text="Software Engineer", metadata={"company": "AppUnite"}),
    Record(id="456", title="Jane Smith", text="Product Manager", metadata={"company": "AppUnite"}),
]
LOOKUP = {r.id: r for r in RECORDS}

@mcp.tool()
async def search(query: str):
    """
    Simple unranked keyword search across title, text, and metadata.
    Searches for any of the query terms in the record content.
    Returns a list of matching record IDs for ChatGPT to fetch.
    """
    toks = query.lower().split()
    ids = []
    for r in RECORDS:
        record_txt = " ".join(
            [r.title, r.text, " ".join(r.metadata.values())]
        ).lower()
        if any(t in record_txt for t in toks):
            ids.append(r.id)

    return {"ids": ids }

@mcp.tool()
async def fetch(id: str):
    """
    Fetch a record by ID.
    Returns the complete record data for ChatGPT to analyze and cite.
    """
    if id not in LOOKUP:
        raise ValueError(f"Unknown record ID: {id}")
    return LOOKUP[id]