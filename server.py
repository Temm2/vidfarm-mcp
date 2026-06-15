import json, httpx, uvicorn, os
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse

K = os.environ.get("VIDFARM_API_KEY", "vf_key_fbdd8e706a5f49ae8adf2505576e42f2")
B = "https://vidfarm.cc/api/v1"
H = {"vidfarm-api-key": K, "content-type": "application/json", "accept": "application/json"}
PUBLIC_URL = os.environ.get("PUBLIC_URL", "https://your-app.railway.app")

mcp = FastMCP(name="vidfarm-bridge")

async def vfg(u, q=None):
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{B}{u}", headers=H, params=q or {})
        try: b = r.json()
        except: b = r.text[:3000]
        return json.dumps({"status": r.status_code, "body": b})

async def vfp(u, e):
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(f"{B}{u}", headers=H, json=e)
        try: b = r.json()
        except: b = r.text[:3000]
        return json.dumps({"status": r.status_code, "body": b})

@mcp.tool()
async def vidfarm_get_me() -> str:
    """Get authenticated VidFarm user profile."""
    return await vfg("/user/me")

@mcp.tool()
async def vidfarm_list_templates() -> str:
    """List all VidFarm video templates."""
    return await vfg("/templates")

@mcp.tool()
async def vidfarm_get_template_skill(template_slug: str) -> str:
    """Get the skill for a VidFarm template. Always call before submitting a job."""
    return await vfg(f"/templates/{template_slug}/skill")

@mcp.tool()
async def vidfarm_run_operation(template_slug: str, operation_name: str, payload_json: str, tracer: str = "claude-mindnote") -> str:
    """Submit a job to a VidFarm template operation. payload_json must be valid JSON."""
    try: pl = json.loads(payload_json)
    except Exception as e: return json.dumps({"error": str(e)})
    return await vfp(f"/templates/{template_slug}/operations/{operation_name}", {"tracer": tracer, "payload": pl})

@mcp.tool()
async def vidfarm_get_job(template_slug: str, job_id: str) -> str:
    """Poll a VidFarm job status. Call every 60s until succeeded or failed."""
    return await vfg(f"/templates/{template_slug}/jobs/{job_id}")

@mcp.tool()
async def vidfarm_get_job_logs(job_id: str) -> str:
    """Get logs for any VidFarm job."""
    return await vfg(f"/user/me/jobs/{job_id}/logs")

@mcp.tool()
async def vidfarm_approve_post(caption: str, title: str, media_json: str = "[]", tracer: str = "claude-mindnote") -> str:
    """Package a finished post as an approved VidFarm post. media_json: [{url, kind, role}]"""
    try: media = json.loads(media_json)
    except Exception as e: return json.dumps({"error": str(e)})
    return await vfp("/approved/posts", {"tracer": tracer, "caption": caption, "title": title, "media": media})

@mcp.tool()
async def vidfarm_list_approved_posts(tracer: str = "") -> str:
    """List approved VidFarm posts."""
    return await vfg("/approved/posts", {"tracer": tracer} if tracer else {})

@mcp.tool()
async def vidfarm_get_schedules(post_id: str) -> str:
    """Get schedules for an approved post."""
    return await vfg(f"/approved/posts/{post_id}/schedules")

@mcp.tool()
async def vidfarm_schedule_post(post_id: str, destination_id: str, scheduled_at: str, destination_type: str = "flockposter", timezone: str = "America/New_York") -> str:
    """Schedule an approved post. scheduled_at ISO 8601, 10+ min in future."""
    return await vfp(f"/approved/posts/{post_id}/schedules", {
        "destination_type": destination_type,
        "destination_id": destination_id,
        "scheduled_at": scheduled_at,
        "timezone": timezone
    })

# OAuth 2.0 discovery endpoints required by Claude MCP client
async def opr(r): return JSONResponse({"resource": PUBLIC_URL, "authorization_servers": [], "bearer_methods_supported": ["header"]})
async def oas(r): return JSONResponse({"issuer": PUBLIC_URL, "token_endpoint": f"{PUBLIC_URL}/token", "response_types_supported": ["token"]})
async def reg(r): return JSONResponse({"client_id": "claude-mcp-client", "client_secret": "none", "grant_types": [], "token_endpoint_auth_method": "none"}, status_code=201)
async def tok(r): return JSONResponse({"access_token": "no-auth-required", "token_type": "bearer", "expires_in": 86400})
async def health(r): return JSONResponse({"status": "ok", "version": "v5-railway"})

mcp_app = mcp.sse_app()
app = Starlette(routes=[
    Route("/.well-known/oauth-protected-resource", opr),
    Route("/.well-known/oauth-protected-resource/sse", opr),
    Route("/.well-known/oauth-authorization-server", oas),
    Route("/register", reg, methods=["POST"]),
    Route("/token", tok, methods=["POST"]),
    Route("/health", health),
    Mount("/", app=mcp_app),
])

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"VidFarm MCP v5 running on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)