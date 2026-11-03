"""
FastAPI Web Application and API Backend for BashCraft Sitemap Analyzer.
Provides interactive REST API, Server-Sent Events (SSE) streaming for real-time progress,
and file download endpoints for sitemaps in XML, JSON, CSV, and Markdown.
"""

import asyncio
import json
import os
from typing import Optional, Dict, Any
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, StreamingResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from core.config import CrawlConfig
from core.crawler import WebCrawler
from core.exporter import SitemapExporter
from core.models import CrawlResult
from core.normalizer import URLNormalizer


app = FastAPI(
    title="BashCraft Sitemap & Link Analyzer",
    description="High-performance website crawler, broken link auditor, and interactive visualizer.",
    version="1.0.0"
)

# Template and static paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

os.makedirs(TEMPLATES_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "css"), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "js"), exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Global in-memory state
current_result: Optional[CrawlResult] = None
is_crawling: bool = False
event_queue: asyncio.Queue = asyncio.Queue()


class CrawlRequest(BaseModel):
    url: str
    max_depth: int = 3
    max_pages: int = 50
    crawl_delay: float = 0.05
    check_broken_links: bool = True
    spa_scan: bool = True
    respect_robots_txt: bool = True


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Renders the main interactive visualizer dashboard."""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "default_url": "https://bashcraftclub.vercel.app/"
    })


@app.post("/api/crawl")
async def start_crawl(crawl_req: CrawlRequest, background_tasks: BackgroundTasks):
    """Initiates a crawl asynchronously and streams progress via SSE."""
    global is_crawling, current_result

    if is_crawling:
        raise HTTPException(status_code=409, detail="A crawl task is already in progress.")

    if not URLNormalizer.is_valid_url(crawl_req.url):
        raise HTTPException(
            status_code=400,
            detail="Invalid URL format. Please enter a valid HTTP or HTTPS URL (e.g. https://bashcraftclub.vercel.app/)."
        )

    config = CrawlConfig(
        start_url=crawl_req.url,
        max_depth=crawl_req.max_depth,
        max_pages=crawl_req.max_pages,
        crawl_delay=crawl_req.crawl_delay,
        check_broken_links=crawl_req.check_broken_links,
        spa_scan=crawl_req.spa_scan,
        respect_robots_txt=crawl_req.respect_robots_txt
    )

    # Empty queue
    while not event_queue.empty():
        try:
            event_queue.get_nowait()
        except Exception:
            break

    def run_crawler_sync():
        global is_crawling, current_result
        is_crawling = True
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            def on_progress(event_dict: Dict[str, Any]):
                try:
                    event_queue.put_nowait(event_dict)
                except Exception:
                    pass

            crawler = WebCrawler(config)
            result = crawler.crawl(progress_callback=on_progress)
            current_result = result
            event_queue.put_nowait({"event": "done", "result": result.model_dump()})
        except Exception as e:
            event_queue.put_nowait({"event": "error", "message": str(e)})
        finally:
            is_crawling = False

    background_tasks.add_task(run_crawler_sync)
    return {"status": "started", "target_url": crawl_req.url}


@app.get("/api/crawl/stream")
async def crawl_stream():
    """Server-Sent Events endpoint streaming live crawl telemetry."""
    async def event_generator():
        while True:
            try:
                # Wait for next event with a timeout
                event_data = await asyncio.wait_for(event_queue.get(), timeout=25.0)
                yield f"data: {json.dumps(event_data)}\n\n"
                if event_data.get("event") in ("done", "error"):
                    break
            except asyncio.TimeoutError:
                # Send keep-alive ping
                yield f": keep-alive\n\n"
            except Exception:
                break

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/crawl/result")
async def get_crawl_result():
    """Retrieves the latest completed crawl result."""
    if not current_result:
        raise HTTPException(status_code=404, detail="No crawl result available. Please run a crawl first.")
    return current_result.model_dump()


@app.get("/api/export/{export_format}")
async def export_sitemap(export_format: str):
    """Downloads sitemap and audit report in XML, JSON, CSV, or Markdown format."""
    if not current_result:
        raise HTTPException(status_code=404, detail="No crawl result available to export.")

    domain = URLNormalizer.get_domain(current_result.base_url).replace(".", "_")

    if export_format == "json":
        content = SitemapExporter.to_json(current_result)
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=sitemap_{domain}.json"}
        )

    elif export_format == "xml":
        content = SitemapExporter.to_xml(current_result)
        return Response(
            content=content,
            media_type="application/xml",
            headers={"Content-Disposition": f"attachment; filename=sitemap_{domain}.xml"}
        )

    elif export_format == "csv-pages":
        content = SitemapExporter.to_pages_csv(current_result)
        return Response(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=pages_{domain}.csv"}
        )

    elif export_format == "csv-broken":
        content = SitemapExporter.to_broken_links_csv(current_result)
        return Response(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=broken_links_{domain}.csv"}
        )

    elif export_format == "markdown":
        content = SitemapExporter.to_markdown_report(current_result)
        return Response(
            content=content,
            media_type="text/markdown",
            headers={"Content-Disposition": f"attachment; filename=audit_report_{domain}.md"}
        )

    else:
        raise HTTPException(
            status_code=400,
            detail="Unsupported export format. Supported formats: json, xml, csv-pages, csv-broken, markdown"
        )

