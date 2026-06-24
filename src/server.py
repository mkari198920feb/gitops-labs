import asyncio
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from mcp.server import Server, NotificationOptions
from mcp.server.stdio import stdio_server
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent

from . import argocd_client as argocd

server = Server("devops-mcp")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="argocd_list_applications",
            description="List all ArgoCD applications with their sync and health status.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="argocd_get_application",
            description="Get full detail for a single ArgoCD application: sync status, health, source, destination.",
            inputSchema={
                "type": "object",
                "properties": {"name": {"type": "string", "description": "Application name"}},
                "required": ["name"],
            },
        ),
        Tool(
            name="argocd_get_resource_tree",
            description="Get the live Kubernetes resource tree for an application.",
            inputSchema={
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        ),
        Tool(
            name="argocd_get_events",
            description="Get recent Kubernetes events for an application's resources.",
            inputSchema={
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        ),
        Tool(
            name="argocd_sync_application",
            description="DESTRUCTIVE: Sync the application. Defaults to dry_run=True (preview only).",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "dry_run": {"type": "boolean", "default": True},
                    "prune": {"type": "boolean", "default": False},
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="argocd_rollback_application",
            description="DESTRUCTIVE: Roll back the application to a previous revision ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "revision_id": {"type": "integer"},
                },
                "required": ["name", "revision_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    import json
    try:
        if name == "argocd_list_applications":
            result = await argocd.list_applications()
        elif name == "argocd_get_application":
            result = await argocd.get_application(arguments["name"])
        elif name == "argocd_get_resource_tree":
            result = await argocd.get_application_resource_tree(arguments["name"])
        elif name == "argocd_get_events":
            result = await argocd.get_application_events(arguments["name"])
        elif name == "argocd_sync_application":
            result = await argocd.sync_application(
                arguments["name"],
                dry_run=arguments.get("dry_run", True),
                prune=arguments.get("prune", False),
            )
        elif name == "argocd_rollback_application":
            result = await argocd.rollback_application(arguments["name"], arguments["revision_id"])
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
    except Exception as e:
        return [TextContent(type="text", text=f"Error calling {name}: {e}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="devops-mcp",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
