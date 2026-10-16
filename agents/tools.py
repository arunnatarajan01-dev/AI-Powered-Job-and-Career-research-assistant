"""Tools an agent can call. The handler runs the tool and returns the result."""

from agents.rag import retrieve
from jobs.discovery import discover

TOOL_SCHEMAS = (
    {
        "name": "retrieve_passages",
        "description": "Retrieve the passages in the uploaded document that best match the question.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "search_jobs",
        "description": "Search Naukri, LinkedIn, Indeed, Job Match Pro, and Foundit by location, posting window, and role.",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string"},
                "posted": {"type": "string"},
                "keyword": {"type": "string"},
                "providers": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["location", "posted", "keyword", "providers"],
        },
    },
    {
        "name": "read_repository_request",
        "description": "Read the repository URL, author, and institution for an IEEE draft.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
)


def execute_tool(name, arguments, context):
    """Run one tool call and return a JSON-ready result."""
    arguments = arguments or {}
    context = context or {}
    if name == "retrieve_passages":
        query = arguments.get("query") or context.get("question") or ""
        document = context.get("document") or ""
        passages = retrieve(query, document, k=4)
        return {"query": query, "passages": passages}
    if name == "search_jobs":
        providers = arguments.get("providers") or context.get("providers") or []
        return {
            "results": discover(
                providers,
                arguments.get("location") or "",
                arguments.get("posted") or "week",
                arguments.get("keyword") or "",
                experience=arguments.get("experience"),
                remote_only=bool(arguments.get("remote_only")),
                work_mode=arguments.get("work_mode") or "",
            )
        }
    if name == "read_repository_request":
        return {
            "repo_url": context.get("repo_url") or "",
            "author": context.get("author") or "",
            "institution": context.get("institution") or "",
        }
    return {"error": f"Unknown tool {name}"}
