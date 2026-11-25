"""TraceRAG MCP Server 冒烟测试。

它扮演 MCP 客户端：拉起 mcp_server.py，列出工具、真实发起一次检索并打印结果。
目的不是替代单测，而是确认「协议通了、工具能真跑」。

用法（容器内）：
    docker compose exec backend python mcp_smoke_test.py
    docker compose exec backend python mcp_smoke_test.py 6 1    # kb_id user_id

如果「知识库」那段返回空列表，说明 user_id 不对——去 MySQL 看一下
`SELECT id, username FROM users;`，用真实用户 ID 重跑。
"""

from __future__ import annotations

import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER_PATH = os.environ.get("MCP_SERVER_PATH", "/app/mcp_server.py")
KB_ID = int(sys.argv[1]) if len(sys.argv) > 1 else 6
USER_ID = int(sys.argv[2]) if len(sys.argv) > 2 else 1


def _text(result) -> str:
    """把 call_tool 的返回值压成一段可读文本。"""
    if not result.content:
        return "(空)"
    parts = []
    for item in result.content:
        parts.append(getattr(item, "text", None) or str(item))
    return "\n".join(parts)


async def main() -> None:
    # 注意：MCP SDK 拉起子进程时，默认只给一个「安全」的环境变量子集，
    # 会把 MYSQL_HOST / CHROMA_DB_HOST / REDIS_URL 这类变量过滤掉，
    # 导致 server 端 pydantic-settings 回退到 config.py 的 localhost 默认值。
    # 这里必须显式继承完整环境。
    params = StdioServerParameters(
        command=sys.executable,
        args=[SERVER_PATH],
        env={**os.environ},
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 1) 工具清单
            tools = await session.list_tools()
            print("== 工具列表 ==")
            for tool in tools.tools:
                first_line = (tool.description or "").strip().splitlines()
                print(f"  - {tool.name}: {first_line[0] if first_line else ''}")

            # 2) 资源模板（可读性优先，失败不阻塞）
            try:
                templates = await session.list_resource_templates()
                print("\n== 资源模板 ==")
                for tpl in templates.resourceTemplates:
                    print(f"  - {tpl.uriTemplate}")
            except Exception as exc:  # noqa: BLE001
                print(f"\n(资源模板读取跳过: {exc})")

            # 3) 列知识库
            print(f"\n== list_knowledge_bases(user_id={USER_ID}) ==")
            out = await session.call_tool("list_knowledge_bases", {"user_id": USER_ID})
            print(_text(out)[:600])

            # 4) 真实检索
            print(f"\n== search_knowledge_base(kb_id={KB_ID}) ==")
            out = await session.call_tool(
                "search_knowledge_base",
                {
                    "query": "星尘 X9 Pro 卖多少钱",
                    "kb_id": KB_ID,
                    "top_k": 3,
                    "user_id": USER_ID,
                },
            )
            print(_text(out)[:900])

            print("\n✅ 冒烟测试结束")


if __name__ == "__main__":
    asyncio.run(main())