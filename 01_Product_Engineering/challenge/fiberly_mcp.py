import os

from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware
from fastmcp.server.middleware.response_limiting import ResponseLimitingMiddleware

import systems


class CallLog(Middleware):
    async def on_call_tool(self, context, call_next):
        if os.getenv("FIBERLY_MCP_LOG"):
            with open(os.environ["FIBERLY_MCP_LOG"], "a", encoding="utf-8") as log:
                log.write(context.message.name + "\n")
        return await call_next(context)


server = FastMCP("fiberly", mask_error_details=True,
                 middleware=[CallLog(), ResponseLimitingMiddleware(max_size=int(os.getenv("FIBERLY_MCP_MAX_BYTES", "60000")))])
for lookup in systems.LOOKUPS:
    server.tool(lookup)

if __name__ == "__main__":
    server.run(show_banner=False)
