"""启动客户端可视化控制台。

用法：python -m mcp_client.run_webapp [--port 8500] [--host 127.0.0.1]
"""

import argparse

import uvicorn

from .webapp import app


def main() -> None:
    parser = argparse.ArgumentParser(description="ESPMCP 客户端控制台")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8500)
    args = parser.parse_args()
    print(f"[ESPMCP] 客户端控制台: http://{args.host}:{args.port}/")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
