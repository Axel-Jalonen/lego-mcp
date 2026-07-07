"""Point a small model at the lego MCP server and let it build.

The model is sandboxed by construction: its ONLY tools are the lego MCP
server's (place_brick, remove_brick, view_layers, ...). No filesystem, no
bash, no network — it cannot touch the repo. Every placement it attempts is
validated by the constraint engine, and rejections come back as tool results
explaining the violated rule, so even a small model converges on physically
valid structures instead of hallucinating.

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    .venv/bin/python agent/build_agent.py "build a small watchtower"
    .venv/bin/python agent/build_agent.py --model claude-sonnet-5 "build a bridge"
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from anthropic import AsyncAnthropic
from anthropic.lib.tools.mcp import async_mcp_tool
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent.parent

SYSTEM = """\
You are a Lego master builder. You build ONLY through the provided tools —
every placement is physics-checked and invalid ones are rejected.

Rules of the world:
- Coordinates: x,y in studs; z in PLATES. A brick is 3 plates tall, a
  plate/tile is 1. z=0 is the baseplate. A brick placed at z=0 has its top
  at z=3, so the next brick on top of it goes at z=3.
- Pieces must connect stud-to-tube. Floating, colliding, or out-of-bounds
  placements are REJECTED — read the error message, it tells you the valid z.
- Tiles are smooth: nothing can ever be stacked on a tile. Use them as
  finishing caps only.
- Slopes have studs only on their non-sloped back rows; nothing attaches to
  the sloped face. At rotation 0 a slope descends toward +y; rotate 90/180/270
  to aim it. Inverted slopes grip below only on their back rows.
- Baseplates (baseplate_16x16 etc.) have studs on top and nothing underneath:
  z=0 only. Great as a floor to build on.
- Only parts from list_parts exist. Rotation is 0, 90, 180 or 270.

Method:
1. Start with new_build (pick a sensible baseplate size), then list_parts.
2. Plan briefly, then build BOTTOM-UP, layer by layer.
3. If a placement is rejected, fix it using the hint in the error — do not
   repeat the same call.
4. Check your work with view_layers occasionally.
5. When finished, call export_build with fmt="blender", then summarize what
   you built in 2-3 sentences.
"""


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("prompt", help="what to build, e.g. 'a small watchtower'")
    ap.add_argument("--model", default="claude-haiku-4-5",
                    help="model id (default: claude-haiku-4-5)")
    ap.add_argument("--max-turns", type=int, default=60,
                    help="safety cap on assistant turns (default 60)")
    args = ap.parse_args()

    server = StdioServerParameters(
        command=str(ROOT / ".venv" / "bin" / "python"),
        args=["-m", "lego_mcp.server"],
        cwd=str(ROOT),
    )

    client = AsyncAnthropic()
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as mcp_client:
            await mcp_client.initialize()
            tools_result = await mcp_client.list_tools()
            tools = [async_mcp_tool(t, mcp_client) for t in tools_result.tools]
            print(f"lego tools: {[t.name for t in tools_result.tools]}")
            print(f"builder model: {args.model}\n")

            runner = client.beta.messages.tool_runner(
                model=args.model,
                max_tokens=4096,
                system=SYSTEM,
                tools=tools,
                messages=[{"role": "user", "content": args.prompt}],
            )

            turns = 0
            async for message in runner:
                turns += 1
                for block in message.content:
                    if block.type == "text" and block.text.strip():
                        print(f"[builder] {block.text.strip()}")
                    elif block.type == "tool_use":
                        brief = json.dumps(block.input, separators=(",", ":"))
                        print(f"  -> {block.name}({brief[:120]})")
                if turns >= args.max_turns:
                    print(f"\n(stopping: hit --max-turns {args.max_turns})")
                    break

            # Final ground truth from the engine, not the model's claims.
            state = await mcp_client.call_tool("get_build", {})
            summary = json.loads(state.content[0].text)
            print(f"\nengine says: {summary['piece_count']} pieces, "
                  f"{summary['height_plates']} plates tall, "
                  f"build '{summary['name']}' saved in builds/.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
