import os
import httpx
import json

from starlette.middleware.base import BaseHTTPMiddleware

from fastapi import Request, status
from fastapi.responses import JSONResponse, HTMLResponse
from starlette.responses import RedirectResponse, JSONResponse as StarletteJSONResponse
from starlette.routing import Route

from src.utils.server_config import BASE_DEPLOY_URL, ALLOWED_DOMAINS, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET


class BearerAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, protected_paths=None):
        super().__init__(app)
        self.protected_paths = protected_paths or ["/mcp"]
    
    async def dispatch(self, request: Request, call_next):
        # Only apply Bearer auth to specific paths (like /mcp)
        path_requires_bearer = any(request.url.path.startswith(path) for path in self.protected_paths)
        
        if not path_requires_bearer:
            return await call_next(request)
        
        expected = os.getenv("MCP_BEARER_TOKEN")
        header = request.headers.get("authorization")

        if expected and header != f"Bearer {expected}":
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Unauthorized"},
            )
        return await call_next(request)


class LoginPasswordMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, protected_paths=None):
        super().__init__(app)
        self.protected_paths = protected_paths or ["/documents"]
    
    async def dispatch(self, request: Request, call_next):
        # Only apply login/password auth to documents paths
        path_requires_login = any(request.url.path.startswith(path) for path in self.protected_paths)
        
        if not path_requires_login:
            return await call_next(request)
        
        auth_token = request.cookies.get("auth_token")
        if auth_token and self._verify_token(auth_token):
            return await call_next(request)
        
        if request.method == "POST":
            form = await request.form()
            username = form.get("username")
            password = form.get("password")
            
            expected_username = os.getenv("DOCUMENTS_USERNAME")
            expected_password = os.getenv("DOCUMENTS_PASSWORD")
            
            if username == expected_username and password == expected_password:
                response = RedirectResponse(url=str(request.url), status_code=302)
                response.set_cookie("auth_token", "authenticated", max_age=3600*24*7, httponly=True)
                return response
            else:
                return self._show_login_form(error="Invalid username or password")
        return self._show_login_form()

    @staticmethod
    def _verify_token(token: str) -> bool:
        return token == "authenticated"

    @staticmethod
    def _show_login_form(error: str = None):
        error_html = ""
        if error:
            error_html = f'<div class="error">{error}</div>'
        
        login_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Document Access - Recruitee MCP Server</title>
            <style>
                body {{ 
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                    max-width: 400px; 
                    margin: 100px auto; 
                    padding: 20px;
                    background-color: #f5f5f5;
                }}
                .container {{
                    background: white;
                    padding: 40px;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                h2 {{
                    color: #333;
                    text-align: center;
                    margin-bottom: 30px;
                }}
                .form-group {{ 
                    margin: 20px 0; 
                }}
                label {{
                    display: block;
                    margin-bottom: 5px;
                    color: #555;
                    font-weight: 500;
                }}
                input[type="text"], input[type="password"] {{ 
                    width: 100%; 
                    padding: 12px; 
                    border: 1px solid #ddd; 
                    border-radius: 4px;
                    font-size: 14px;
                    box-sizing: border-box;
                }}
                input[type="text"]:focus, input[type="password"]:focus {{
                    border-color: #007bff;
                    outline: none;
                }}
                button {{ 
                    background: #007bff; 
                    color: white; 
                    padding: 12px 20px; 
                    border: none; 
                    border-radius: 4px; 
                    cursor: pointer;
                    width: 100%;
                    font-size: 16px;
                    margin-top: 10px;
                }}
                button:hover {{ 
                    background: #0056b3; 
                }}
                .error {{
                    background: #f8d7da;
                    color: #721c24;
                    padding: 10px;
                    border-radius: 4px;
                    margin-bottom: 20px;
                    border: 1px solid #f5c6cb;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 30px;
                    color: #666;
                    font-size: 12px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>🔐 Document Access</h2>
                {error_html}
                <form method="post">
                    <div class="form-group">
                        <label for="username">Username:</label>
                        <input type="text" id="username" name="username" required>
                    </div>
                    <div class="form-group">
                        <label for="password">Password:</label>
                        <input type="password" id="password" name="password" required>
                    </div>
                    <button type="submit">Login</button>
                </form>
                <div class="footer">
                    Recruitee MCP Server - Document Access
                </div>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=login_html)


class OAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, protected_paths=None):
        super().__init__(app)
        self.protected_paths = protected_paths or ["/mcp"]
    
    async def dispatch(self, request: Request, call_next):
        # Only apply OAuth auth to specific paths (like /mcp)
        path_requires_oauth = any(request.url.path.startswith(path) for path in self.protected_paths)
        
        if not path_requires_oauth:
            return await call_next(request)
        
        # Extract Authorization header
        auth_header = request.headers.get("authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "invalid_token",
                    "error_description": "Missing or invalid authorization header"
                }
            )
        
        # Extract token
        token = auth_header.split(" ", 1)[1]
        
        # Validate token with Google
        try:
            user_info = await self._validate_google_token(token)
            if not user_info:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "error": "invalid_token", 
                        "error_description": "Invalid or expired OAuth token"
                    }
                )
            
            # Check domain restrictions
            email = user_info.get("email", "")
            if not self._is_allowed_domain(email):
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={
                        "error": "access_denied",
                        "error_description": f"Email domain not allowed. Allowed domains: {', '.join(ALLOWED_DOMAINS)}"
                    }
                )
            
            # Add user info to request for potential use in endpoints
            request.state.user = user_info
            
        except Exception as e:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "invalid_token",
                    "error_description": f"Token validation failed: {str(e)}"
                }
            )
        
        return await call_next(request)
    
    async def _validate_google_token(self, token: str) -> dict:
        """Validate OAuth token with Google's userinfo endpoint."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://www.googleapis.com/oauth2/v2/userinfo",
                    headers={"Authorization": f"Bearer {token}"}
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    return None
        except Exception:
            return None
    
    def _is_allowed_domain(self, email: str) -> bool:
        """Check if email domain is in allowed domains list."""
        if not email or "@" not in email:
            return False
        
        domain = email.split("@")[1].lower()
        return domain in [d.lower() for d in ALLOWED_DOMAINS]


def add_oauth_endpoints(app):
    """Add OAuth 2.0 metadata endpoints required for Claude Desktop MCP integration."""
    
    # OAuth 2.0 Authorization Server Metadata (RFC 8414)
    # Direct Google OAuth - Claude Desktop talks directly to Google
    oauth_metadata = {
        "issuer": BASE_DEPLOY_URL,
        "authorization_endpoint": "https://accounts.google.com/o/oauth2/v2/auth",  # Google's endpoint
        "token_endpoint": "https://oauth2.googleapis.com/token",                   # Google's endpoint
        "userinfo_endpoint": "https://www.googleapis.com/oauth2/v2/userinfo",      # Google's endpoint
        "registration_endpoint": f"{BASE_DEPLOY_URL}/register",
        "grant_types_supported": ["authorization_code"],
        "response_types_supported": ["code"],
        "scopes_supported": ["openid", "email", "profile"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["RS256"],
        # PKCE support (required by Claude Desktop)
        "code_challenge_methods_supported": ["S256"],
        # Additional metadata to help with authorization requests
        "response_modes_supported": ["query", "fragment"],
        "default_scopes": ["openid", "email", "profile"],
        "allowed_domains": ALLOWED_DOMAINS,
    }
    
    # OAuth 2.0 Protected Resource Metadata (RFC 8707) - what Claude looks for first
    protected_resource_metadata = {
        "resource": BASE_DEPLOY_URL,
        "authorization_servers": [BASE_DEPLOY_URL],
        "scopes_supported": ["openid", "email", "profile"],
        "bearer_methods_supported": ["header"],
        "resource_documentation": f"{BASE_DEPLOY_URL}/docs",
    }
    
    async def get_oauth_metadata(request):
        """OAuth 2.0 Authorization Server Metadata endpoint."""
        return StarletteJSONResponse(oauth_metadata)
    
    async def get_protected_resource_metadata(request):
        """OAuth 2.0 Protected Resource Metadata endpoint (RFC 8707)."""
        return StarletteJSONResponse(protected_resource_metadata)
    
    async def register_client(request):
        """Dynamic Client Registration endpoint for MCP clients (Claude Desktop, ChatGPT, etc.)."""
        # Return the real Google OAuth client credentials
        # Claude Desktop will use these to talk directly to Google
        client_id = GOOGLE_CLIENT_ID
        client_secret = GOOGLE_CLIENT_SECRET
        
        # Support common MCP client redirect URIs
        redirect_uris = [
            "http://localhost:3000/callback",    # Claude Desktop
            "http://localhost:8080/callback",    # Other local clients
            "http://127.0.0.1:3000/callback",    # Alternative localhost
            "http://127.0.0.1:8080/callback",    # Alternative localhost
            "https://chatgpt.com/connector_platform_oauth_redirect",  # ChatGPT
            "https://claude.ai/api/mcp/auth_callback",  # Claude.ai web
        ]
        
        client_config = {
            "client_id": client_id,
            "client_secret": client_secret,  # Real Google client secret
            "redirect_uris": redirect_uris,
            "grant_types": ["authorization_code"],
            "response_types": ["code"],
            "application_type": "native",  # For desktop/native applications
            "token_endpoint_auth_method": "none",  # Public clients (native apps) don't use client_secret in token exchange
            "scope": "openid email profile",  # Space-separated string for OAuth spec
            "default_scopes": ["openid", "email", "profile"],  # Array format
            "default_max_age": 3600
        }
        
        return StarletteJSONResponse(client_config)
    
    async def server_info(request):
        """Basic server information endpoint."""
        info = {
            "name": "Recruitee MCP Server",
            "version": "1.0.0",
            "description": "OAuth-protected MCP server for Recruitee API",
            "mcp_version": "2024-11-05",
            "protocol": "mcp",
            "implementation": "fastmcp",
            "endpoints": {
                "mcp": "/mcp",
                "oauth_metadata": "/.well-known/oauth-authorization-server",
                "protected_resource_metadata": "/.well-known/oauth-protected-resource",
                "client_registration": "/register",
                "actions": "/actions",
                "search": "/search"
            },
            "capabilities": {
                "tools": ["search_candidates", "search_candidate_by_query", "get_candidates_details"],
                "resources": ["candidates"],
                "prompts": ["search", "filter"]
            },
            "actions": [
                {
                    "name": "search",
                    "available": True,
                    "description": "Search and filter candidates"
                }
            ],
            "authentication": "OAuth 2.0 (Google)",
            "allowed_domains": ALLOWED_DOMAINS,
            "openai_compatible": True
        }
        return StarletteJSONResponse(info)
    
    async def search_action(request):
        """Search action endpoint that ChatGPT might be expecting."""
        search_info = {
            "action": "search",
            "available": True,
            "description": "Search candidates using various filters",
            "endpoints": [
                {
                    "name": "search_candidates",
                    "description": "Search candidates with advanced filters",
                    "method": "POST",
                    "path": "/mcp"
                },
                {
                    "name": "search_candidate_by_query",
                    "description": "Search candidates by text query",
                    "method": "POST", 
                    "path": "/mcp"
                }
            ],
            "authentication_required": True,
            "oauth_flow": "authorization_code"
        }
        return StarletteJSONResponse(search_info)
    
    async def actions_list(request):
        """List all available actions for ChatGPT."""
        actions = {
            "actions": [
                {
                    "name": "search",
                    "description": "Search and filter candidates",
                    "available": True,
                    "endpoint": "/action/search"
                },
                {
                    "name": "candidate_details",
                    "description": "Get detailed candidate information",
                    "available": True,
                    "endpoint": "/mcp"
                }
            ],
            "authentication": "OAuth 2.0",
            "base_url": BASE_DEPLOY_URL
        }
        return StarletteJSONResponse(actions)
    
    # Add routes to the Starlette app
    oauth_routes = [
        Route("/", server_info, methods=["GET"]),  # Root endpoint for server info
        Route("/.well-known/oauth-authorization-server", get_oauth_metadata, methods=["GET"]),
        Route("/.well-known/oauth-protected-resource", get_protected_resource_metadata, methods=["GET"]),
        Route("/register", register_client, methods=["POST"]),
        # ChatGPT-specific endpoints
        Route("/action/search", search_action, methods=["GET"]),
        Route("/actions", actions_list, methods=["GET"]),
        Route("/search", search_action, methods=["GET"]),  # Alternative search endpoint
    ]
    
    # Add routes to the existing app
    app.routes.extend(oauth_routes)
