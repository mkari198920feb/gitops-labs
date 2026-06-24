import os
import httpx

ARGOCD_BASE_URL = os.environ.get("ARGOCD_BASE_URL", "https://localhost:8080")
ARGOCD_TOKEN = os.environ.get("ARGOCD_TOKEN", "")

def _headers() -> dict:
    if not ARGOCD_TOKEN:
        raise RuntimeError("ARGOCD_TOKEN is not set — generate one with 'argocd account generate-token --account admin' and add it to .env")
    return {"Authorization": f"Bearer {ARGOCD_TOKEN}"}

async def list_applications() -> dict:
    async with httpx.AsyncClient(verify=False, timeout=30) as client:
        response = await client.get(f"{ARGOCD_BASE_URL}/api/v1/applications", headers=_headers())
        response.raise_for_status()
        return response.json()

async def get_application(name: str) -> dict:
    async with httpx.AsyncClient(verify=False, timeout=30) as client:
        response = await client.get(f"{ARGOCD_BASE_URL}/api/v1/applications/{name}", headers=_headers())
        response.raise_for_status()
        return response.json()

async def get_application_resource_tree(name: str) -> dict:
    async with httpx.AsyncClient(verify=False, timeout=30) as client:
        response = await client.get(f"{ARGOCD_BASE_URL}/api/v1/applications/{name}/resource-tree", headers=_headers())
        response.raise_for_status()
        return response.json()


async def get_application_events(name: str) -> dict:
    async with httpx.AsyncClient(verify=False, timeout=30) as client:
        response = await client.get(f"{ARGOCD_BASE_URL}/api/v1/applications/{name}/events", headers=_headers())
        response.raise_for_status()
        return response.json()

async def sync_application(name: str, dry_run: bool = True, prune: bool = False) -> dict:
    payload = {
        "dryRun": dry_run,
        "prune": prune
    }
    async with httpx.AsyncClient(verify=False, timeout=60) as client:
        response = await client.post(
            f"{ARGOCD_BASE_URL}/api/v1/applications/{name}/sync",
            headers=_headers(),
            json=payload 
        )
        response.raise_for_status()
        return response.json()

async def rollback_application(name: str, revision_id: int) -> dict:
    payload = {
        "id": revision_id
    }
    async with httpx.AsyncClient(verify=False, timeout=60) as client:
        response = await client.post(
            f"{ARGOCD_BASE_URL}/api/v1/applications/{name}/rollback",
            headers=_headers(),
            json=payload
        )
        response.raise_for_status()
        return response.json()
