"""
Main entry point for BashCraft Website Sitemap & Link Analyzer.
Provides subcommands:
  - crawl : Explores target URL, generates sitemap, and exports reports.
  - serve : Launches the interactive Web visualizer dashboard.
  - audit : Quick broken-link diagnostics.
  - demo  : Runs crawl on the target BashCraft site and saves submission artifacts.
"""

import argparse
import sys
import threading
import time
import webbrowser
from cli import run_crawl_cli, print_banner


DEFAULT_TARGET = "https://bashcraftclub.vercel.app/"


def launch_web_dashboard(host: str = "127.0.0.1", port: int = 8000, reload: bool = False):
    """Starts the FastAPI Web Dashboard and opens the browser automatically."""
    try:
        import uvicorn
    except ImportError:
        print("[x] Error: 'uvicorn' is required to launch the interactive web dashboard.")
        print("💡 Install it using: pip install uvicorn")
        sys.exit(1)

    url = f"http://{host}:{port}"

    def auto_open_browser():
        time.sleep(1.2)
        print(f"🌐 Opening interactive visual dashboard in your browser: {url}")
        webbrowser.open(url)

    threading.Thread(target=auto_open_browser, daemon=True).start()
    print_banner()
    print(f"🚀 Starting BashCraft Sitemap Dashboard at {url}")
    print("💡 The web browser will open automatically. Press Ctrl+C in this window to stop.")
    uvicorn.run("web.app:app", host=host, port=port, reload=reload)


def main():
    parser = argparse.ArgumentParser(
        description="BashCraft Website Sitemap & Link Issue Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Command: crawl
    crawl_parser = subparsers.add_parser("crawl", help="Crawl a website and generate sitemap")
    crawl_parser.add_argument("url", nargs="?", default=DEFAULT_TARGET, help="Target website URL (default: BashCraft)")
    crawl_parser.add_argument("--depth", "-d", type=int, default=3, help="Max crawl depth (default: 3)")
    crawl_parser.add_argument("--max-pages", "-p", type=int, default=50, help="Max internal pages (default: 50)")
    crawl_parser.add_argument("--export", "-e", type=str, default="json,xml,csv,md", help="Comma-separated export formats (json,xml,csv,md)")
    crawl_parser.add_argument("--out", "-o", type=str, default="output", help="Directory to save export files")
    crawl_parser.add_argument("--no-spa", action="store_true", help="Disable JavaScript SPA route analysis")
    crawl_parser.add_argument("--no-broken-check", action="store_true", help="Skip checking discovered links status")

    # Command: serve
    serve_parser = subparsers.add_parser("serve", help="Launch interactive Web Dashboard (default)")
    serve_parser.add_argument("--host", type=str, default="127.0.0.1", help="Host address (default: 127.0.0.1)")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    serve_parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")

    # Command: audit
    audit_parser = subparsers.add_parser("audit", help="Run rapid broken-link health audit in terminal")
    audit_parser.add_argument("url", nargs="?", default=DEFAULT_TARGET, help="Website URL to audit")

    # Command: demo
    demo_parser = subparsers.add_parser("demo", help="Demonstrate crawl on official BashCraft website")

    args = parser.parse_args()

    # Default action when clicking 'Run' or typing 'python main.py' with no arguments:
    # Launches the beautiful interactive Web Dashboard and opens browser!
    if not args.command or args.command == "serve":
        host = getattr(args, "host", "127.0.0.1")
        port = getattr(args, "port", 8000)
        reload = getattr(args, "reload", False)
        launch_web_dashboard(host=host, port=port, reload=reload)

    elif args.command == "crawl":
        url = getattr(args, "url", DEFAULT_TARGET) or DEFAULT_TARGET
        depth = getattr(args, "depth", 3)
        max_pages = getattr(args, "max_pages", 50)
        export = getattr(args, "export", "json,xml,csv,md").split(",")
        output_dir = getattr(args, "out", "output")
        spa_scan = not getattr(args, "no_spa", False)
        check_broken = not getattr(args, "no_broken_check", False)

        run_crawl_cli(
            target_url=url,
            max_depth=depth,
            max_pages=max_pages,
            export_formats=export,
            output_dir=output_dir,
            spa_scan=spa_scan,
            check_broken=check_broken
        )

    elif args.command == "audit":
        run_crawl_cli(
            target_url=args.url or DEFAULT_TARGET,
            max_depth=2,
            max_pages=30,
            export_formats=["md"],
            output_dir="output",
            spa_scan=True,
            check_broken=True
        )

    elif args.command == "demo":
        print_banner()
        print("🎯 Executing Official BashCraft Demonstration Crawl...")
        run_crawl_cli(
            target_url=DEFAULT_TARGET,
            max_depth=3,
            max_pages=50,
            export_formats=["json", "xml", "csv", "md"],
            output_dir="demonstration",
            spa_scan=True,
            check_broken=True
        )


if __name__ == "__main__":
    main()

