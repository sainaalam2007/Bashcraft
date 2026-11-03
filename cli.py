"""
Command Line Interface (CLI) for BashCraft Website Sitemap & Link Analyzer.
Powered by Rich for colored terminal output, ASCII tables, live spinners,
and structured sitemap hierarchies.
"""

import os
import sys
from typing import List, Optional

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from core.config import CrawlConfig
from core.crawler import WebCrawler
from core.exporter import SitemapExporter
from core.models import CrawlResult
from core.normalizer import URLNormalizer


console = Console(force_terminal=True, highlight=False)

BANNER = r"""[bold green]
 ____            _      ____raft
| __ )  __ _ ___| |__  / ___|_ __ __ _ / _| |_ 
|  _ \ / _` / __| '_ \| |   | '__/ _` | |_| __|
| |_) | (_| \__ \ | | | |___| | | (_| |  _| |_ 
|____/ \__,_|___/_| |_|\____|_|  \__,_|_|  \__|
[/bold green]
[dim cyan]>> High-Impact Website Sitemap & Link Issue Analyzer[/dim cyan]
[dim]   No fluff. Only asli engineering. Built for BashCraft recruitment.[/dim]
"""


def print_banner():
    console.print(BANNER)


def run_crawl_cli(
    target_url: str,
    max_depth: int = 3,
    max_pages: int = 50,
    export_formats: Optional[List[str]] = None,
    output_dir: str = "output",
    spa_scan: bool = True,
    check_broken: bool = True
) -> CrawlResult:
    """Executes crawl from CLI and displays formatted terminal output."""
    print_banner()

    if not URLNormalizer.is_valid_url(target_url):
        console.print(f"[bold red][x] Error:[/bold red] '{target_url}' is not a valid HTTP/HTTPS URL.")
        sys.exit(1)

    config = CrawlConfig(
        start_url=target_url,
        max_depth=max_depth,
        max_pages=max_pages,
        spa_scan=spa_scan,
        check_broken_links=check_broken,
        respect_robots_txt=True
    )

    console.print(Panel(
        f"[bold white]Target URL:[/bold white] [cyan]{target_url}[/cyan]\n"
        f"[bold white]Max Depth:[/bold white] {max_depth} | [bold white]Max Pages:[/bold white] {max_pages} | "
        f"[bold white]SPA Route Scan:[/bold white] {spa_scan} | [bold white]Broken Link Audit:[/bold white] {check_broken}",
        title="[bold green]Crawl Parameters[/bold green]",
        border_style="green"
    ))

    crawler = WebCrawler(config)

    with Progress(
        SpinnerColumn(spinner_name="dots"),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console
    ) as progress:
        task = progress.add_task("[bold cyan]Exploring site architecture and links...", total=None)

        def on_event(event_data):
            if event_data.get("event") == "crawling":
                url = event_data.get("url", "")
                count = event_data.get("crawled_count", 0)
                progress.update(task, description=f"[cyan]Analyzing ({count} pages):[/cyan] [dim]{url[:60]}[/dim]")
            elif event_data.get("event") == "skipped":
                pass

        result = crawler.crawl(progress_callback=on_event)
        progress.update(task, description="[bold green]Crawl complete!")

    # Display Summary Stats Panel
    stats = result.stats
    health_color = "green" if stats.health_score >= 80 else ("yellow" if stats.health_score >= 50 else "red")

    summary_text = (
        f"[bold]Target:[/bold] {result.base_url}\n"
        f"[bold]Duration:[/bold] {stats.duration_seconds}s | [bold]Max Depth Reached:[/bold] {stats.max_depth_reached}\n"
        f"[bold]Pages Crawled:[/bold] [green]{stats.pages_crawled}[/green] / Discovered: {stats.pages_discovered}\n"
        f"[bold]Internal Links:[/bold] [cyan]{stats.total_internal_links}[/cyan] | [bold]External Links:[/bold] [blue]{stats.total_external_links}[/blue]\n"
        f"[bold]Broken Links:[/bold] [{'red' if stats.total_broken_links > 0 else 'green'}]{stats.total_broken_links}[/{'red' if stats.total_broken_links > 0 else 'green'}]\n"
        f"[bold]Avg Latency:[/bold] {stats.average_response_time_ms} ms\n"
        f"[bold]Site Health Score:[/bold] [{health_color}]{stats.health_score}%[/{health_color}]"
    )

    console.print()
    console.print(Panel(summary_text, title="[bold green]Crawl Summary[/bold green]", border_style="cyan"))

    # Display Discovered Pages Table
    pages_table = Table(title="Discovered Web Pages", border_style="dim", header_style="bold cyan")
    pages_table.add_column("Status", justify="center", style="bold")
    pages_table.add_column("Depth", justify="center")
    pages_table.add_column("Page Title & URL", style="white")
    pages_table.add_column("Inbound", justify="center")
    pages_table.add_column("Outbound", justify="center")
    pages_table.add_column("Latency", justify="right")

    for page in sorted(result.pages.values(), key=lambda p: (p.depth, p.url)):
        status_style = "[green]200 OK[/green]" if page.status_code == 200 else f"[red]{page.status_code}[/red]"
        title_url = f"[bold]{page.title[:40]}[/bold]\n[dim]{page.url}[/dim]"
        pages_table.add_row(
            status_style,
            str(page.depth),
            title_url,
            str(page.inbound_links_count),
            f"{page.outbound_internal_count} int / {page.outbound_external_count} ext",
            f"{page.response_time_ms} ms"
        )

    console.print()
    console.print(pages_table)

    # Display Broken Links Table if any
    if result.all_broken_links:
        broken_table = Table(title="Broken Link Diagnostics", border_style="red", header_style="bold red")
        broken_table.add_column("Status", justify="center", style="bold red")
        broken_table.add_column("Target Broken URL", style="yellow")
        broken_table.add_column("Found On (Referrer)", style="dim")
        broken_table.add_column("Failure Reason", style="red")

        for bl in result.all_broken_links:
            broken_table.add_row(
                str(bl.status_code or "FAIL"),
                bl.url,
                bl.source_url,
                bl.error_reason or "Unknown Error"
            )

        console.print()
        console.print(broken_table)
    else:
        console.print("\n[bold green][+] No broken links detected! All routes returned healthy responses.[/bold green]\n")

    # Display Terminal Sitemap Tree
    console.print("[bold cyan]>> Discovered Sitemap Hierarchy Tree:[/bold cyan]")
    root_tree = Tree(f"[bold green]{result.base_url}[/bold green]")

    def build_rich_tree(node_dict, parent_rich_tree):
        for child in node_dict.get("children", []):
            label = f"[white]{child['name']}[/white] [dim]({child.get('title', '')})[/dim]"
            child_branch = parent_rich_tree.add(label)
            build_rich_tree(child, child_branch)

    build_rich_tree(result.sitemap_tree, root_tree)
    console.print(root_tree)

    # Export formats to disk
    if export_formats:
        os.makedirs(output_dir, exist_ok=True)
        domain = URLNormalizer.get_domain(result.base_url).replace(".", "_")

        for fmt in export_formats:
            fmt = fmt.strip().lower()
            if fmt == "json":
                path = os.path.join(output_dir, f"sitemap_{domain}.json")
                with open(path, "w", encoding="utf-8") as f:
                    f.write(SitemapExporter.to_json(result))
                console.print(f"[dim]Saved JSON sitemap to:[/dim] [cyan]{path}[/cyan]")
            elif fmt == "xml":
                path = os.path.join(output_dir, f"sitemap_{domain}.xml")
                with open(path, "w", encoding="utf-8") as f:
                    f.write(SitemapExporter.to_xml(result))
                console.print(f"[dim]Saved XML sitemap to:[/dim] [cyan]{path}[/cyan]")
            elif fmt == "csv":
                path_pages = os.path.join(output_dir, f"pages_{domain}.csv")
                with open(path_pages, "w", encoding="utf-8") as f:
                    f.write(SitemapExporter.to_pages_csv(result))
                path_broken = os.path.join(output_dir, f"broken_links_{domain}.csv")
                with open(path_broken, "w", encoding="utf-8") as f:
                    f.write(SitemapExporter.to_broken_links_csv(result))
                console.print(f"[dim]Saved CSV reports to:[/dim] [cyan]{output_dir}/[/cyan]")
            elif fmt in ("md", "markdown"):
                path_md = os.path.join(output_dir, f"audit_report_{domain}.md")
                with open(path_md, "w", encoding="utf-8") as f:
                    f.write(SitemapExporter.to_markdown_report(result))
                console.print(f"[dim]Saved Markdown report to:[/dim] [cyan]{path_md}[/cyan]")

    return result
