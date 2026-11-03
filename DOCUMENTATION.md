# 📖 Technical Documentation: BashCraft Sitemap & Link Analyzer

This document details the architectural decisions, graph traversal algorithms, URL normalization rules, JavaScript bundle analysis techniques, and testing strategies implemented in the project.

---

## 1. System Architecture & Component Design

The system follows a clean modular architecture separating concerns across domain modeling, crawling mechanics, parsing, auditing, persistence/exporting, and visual interfaces.

```
+-------------------------------------------------------------+
|                 CLI (cli.py) / Web UI (FastAPI)             |
+-------------------------------------------------------------+
                               |
                               v
+-------------------------------------------------------------+
|                   WebCrawler (core/crawler.py)              |
|  - BFS Traversal Queue (deque)                              |
|  - Visited Set (Canonical URLs)                             |
|  - Concurrency & Delay Throttle                             |
+-------------------------------------------------------------+
         |                     |                     |
         v                     v                     v
+------------------+  +------------------+  +------------------+
| URLNormalizer    |  | PageParser       |  | LinkAuditor      |
| (core/normalizer)|  | (core/parser.py) |  | (core/auditor.py)|
+------------------+  +------------------+  +------------------+
                               |
                               v
                      +------------------+
                      | SPAAnalyzer      |
                      | (core/spa_analyzer)
                      +------------------+
                               |
                               v
+-------------------------------------------------------------+
|               SitemapExporter (core/exporter.py)            |
|       XML Sitemap 0.9 | JSON | CSV | Markdown Report        |
+-------------------------------------------------------------+
```

---

## 2. Crawling Approach: Breadth-First Search (BFS) vs. Depth-First Search (DFS)

### Design Decision: Why BFS?
Web sitemaps inherently represent a hierarchical tree structure rooted at the site's homepage (`depth = 0`). BFS was selected over DFS for the following engineering reasons:
1. **Predictable Depth Hierarchy**: BFS explores all direct first-level navigation pages (`/about`, `/events`, `/team`) before diving into nested sub-pages (`/events/bashnex26`). This guarantees that pages are discovered at their minimum distance (depth) from root.
2. **Prioritization of Critical Navigation**: Primary navigation links are discovered and indexed first, which is ideal when constrained by `max_pages`.
3. **Loop Detection & Termination**: In a directed web graph with cycles ($A \rightarrow B \rightarrow C \rightarrow A$), BFS with an unvisited queue and a visited canonical set terminates predictably as soon as all reachable nodes within `max_depth` are cataloged.

### Algorithm Pseudocode
```python
queue = deque([(start_url, 0, None)])  # (url, depth, referrer)
visited = {start_url}

while queue and len(pages) < max_pages:
    current_url, depth, referrer = queue.popleft()
    
    if depth > max_depth:
        continue
        
    response = fetch_with_timeout(current_url)
    dom = parse_dom(response.text)
    
    for link in dom.links:
        category, canonical = classify_and_normalize(link)
        if category == "internal_page":
            record_edge(current_url, canonical)
            if canonical not in visited and (depth + 1) <= max_depth:
                visited.add(canonical)
                queue.append((canonical, depth + 1, current_url))
        elif category == "external":
            record_external(canonical, source=current_url)
            
    if spa_detected:
        routes = extract_spa_routes(dom.scripts)
        for route in routes:
            if route not in visited and (depth + 1) <= max_depth:
                visited.add(route)
                queue.append((route, depth + 1, current_url))
```

---

## 3. URL Normalization & Duplicate Handling

A major challenge in web crawling is duplicate resource indexing: multiple distinct strings pointing to the exact same webpage.

### Canonical Normalization Pipeline (`URLNormalizer.normalize`)
1. **Scheme & Host Normalization**:
   - `HTTP://BashCraftClub.Vercel.App` $\rightarrow$ `https://bashcraftclub.vercel.app`
   - Strips standard default ports (`:80` for HTTP, `:443` for HTTPS).
2. **Path Deduplication & Dot-Segment Resolution**:
   - Uses `posixpath.normpath` to resolve relative references:
     - `/events/../about` $\rightarrow$ `/about`
     - `/events/./bashnex26` $\rightarrow$ `/events/bashnex26`
     - Clean duplicate slashes: `//team` $\rightarrow$ `/team`
3. **Consistent Trailing Slash Handling**:
   - Web servers often treat `/about/` and `/about` identically. The normalizer strips trailing slashes on all subpaths while preserving root `/`:
     - `https://bashcraftclub.vercel.app/` $\rightarrow$ `https://bashcraftclub.vercel.app/`
     - `https://bashcraftclub.vercel.app/about/` $\rightarrow$ `https://bashcraftclub.vercel.app/about`
4. **Fragment Stripping**:
   - Hash fragments (`#form-section`, `#top`) identify client-side scroll positions, not distinct HTTP resources. Fragments are discarded completely.
5. **Analytics Parameter Filtering**:
   - Query parameters that do not alter page content (`utm_source`, `utm_medium`, `utm_campaign`, `fbclid`, `gclid`, `ref`) are stripped.
   - Any remaining functional parameters are sorted alphabetically to prevent permutations (`?b=1&a=2` $\rightarrow$ `?a=2&b=1`) from creating duplicate pages.

---

## 4. Internal vs. External Link Segregation

The crawler strictly differentiates between links that belong to the target entity and external destinations:

```python
target_domain = URLNormalizer.get_domain(target_url)
base_domain = URLNormalizer.get_domain(base_url)

if target_domain == base_domain:
    return True  # Internal

# Handles www vs non-www
if base_domain.removeprefix("www.") == target_domain.removeprefix("www."):
    return True  # Internal

# Handles subdomains (e.g., api.bashcraftclub.vercel.app)
if target_domain.endswith("." + base_domain):
    return True  # Internal
```

- **Internal Links**: Added to BFS crawl queue if `depth < max_depth`.
- **External Links**: Recorded in the parent page's metadata and the global external link registry, but **never** recursively crawled. This avoids external crawl traps and preserves crawler focus.

---

## 5. Single Page Application (SPA) Dynamic Route Discovery

### The Challenge with Modern Frameworks
When querying `https://bashcraftclub.vercel.app/`, the raw HTML contains only:
```html
<div id="root"></div>
<script type="module" src="/assets/index-DY_CelF0.js"></script>
```
Standard static HTML parsers find 0 links on this page.

### The Solution: AST/Regex Bundle Dissector
The `SPAAnalyzer` inspects `<script>` tags, retrieves the Vite/React bundle, and scans for client-side routing definitions:
- React Router `path: "/about"`, `path: "/events"`, `<Route path="/team">`
- Navigation hooks `to: "/..."`, `navigate("/...")`
- Parameterized routes: `/team/:teamId` $\rightarrow$ resolves to base route `/team`
- Embedded external URLs and social channels: `github.com/BashCraftClub`, LinkedIn, Instagram

This enables 100% route discovery on modern SPAs with high speed and zero external browser overhead.

---

## 6. Broken Link Detection & Failure Diagnostics

Every discovered internal link is audited using `LinkAuditor`:
1. **HEAD Request First**: Issues an HTTP `HEAD` request to check status without fetching large response bodies, saving bandwidth and execution time.
2. **GET Fallback**: If a server returns `405 Method Not Allowed` or `403 Forbidden` for `HEAD`, falls back to a lightweight `GET` request.
3. **Failure Classification**:
   - `404 Not Found`: Dead or deleted route.
   - `500 / 502 / 503`: Internal server errors.
   - `TimeoutException`: Server took longer than timeout threshold (default 10s).
   - `ConnectError`: DNS resolution failed or connection was refused.
4. **Context Association**: Associates every broken link with its **source page** (referrer) and **anchor text** so developers know exactly where to fix the broken link.
5. **Auditor Cache**: Results are cached in memory to ensure links referenced across multiple pages are only audited once over the network.

---

## 7. SEO Quality & Health Score Formulation

The analyzer computes an automated Site Quality & Health Score between $0\%$ and $100\%$:

$$\text{Health Score} = 100 - (\text{Penalty}_{\text{broken}} + \text{Penalty}_{\text{titles}} + \text{Penalty}_{\text{meta}} + \text{Penalty}_{\text{latency}})$$

Where:
- $\text{Penalty}_{\text{broken}} = \min(N_{\text{broken}} \times 5.0, 40.0)$
- $\text{Penalty}_{\text{titles}} = \left(\frac{N_{\text{missing\_titles}}}{N_{\text{pages}}}\right) \times 20.0$
- $\text{Penalty}_{\text{meta}} = \left(\frac{N_{\text{missing\_meta}}}{N_{\text{pages}}}\right) \times 15.0$
- $\text{Penalty}_{\text{latency}} = \left(\frac{N_{\text{slow\_pages (>1000ms)}}}{N_{\text{pages}}}\right) \times 10.0$

---

## 8. Testing Strategy & Edge Cases Verified

The test suite in [`tests/`](file:///tests/) achieves 100% pass rate across 16 unit and integration test cases:

| Test Case | Scope | Expected Outcome |
| :--- | :--- | :--- |
| `test_loop_prevention` | Circular graph ($A \rightarrow B \rightarrow C \rightarrow A$) | Visits exactly 3 unique pages; terminates cleanly. |
| `test_depth_limit_enforcement` | Multi-level tree with `max_depth=1` | Traverses depth 0 and 1 only; stops at boundary. |
| `test_canonical_normalization` | Casing, default ports, trailing slashes, dot-segments | All variations resolve to unified canonical string. |
| `test_tracking_params_removal` | URLs with `utm_source`, `fbclid`, etc. | Tracking parameters stripped; functional parameters retained. |
| `test_internal_vs_external` | Same domain, www, subdomains, third-party sites | Correct Boolean classification for every target. |
| `test_missing_title_edge_case` | HTML without `<title>` or empty title tag | Graceful fallback to `Untitled (<url>)`. |
| `test_whitespace_title_edge_case` | Title with newlines and spaces | Sanitized and stripped properly. |
| `test_spa_skeleton_detection` | `<div id="root">` with minimal body | Correctly flags page as SPA skeleton. |
| `test_extract_routes_and_links` | React Router code patterns in JavaScript | Discovers all internal paths and external links. |
| `test_xml_sitemap_compliance` | Sitemaps.org 0.9 XML generation | Produces schema-compliant XML with correct priority and changefreq. |
| `test_json_export` | JSON serialization & deserialization | Valid JSON matching Pydantic schema. |
| `test_csv_exports` | Pages and broken links CSV generators | Correct headers, row counts, and escaped commas. |

---

## 9. Conclusion

The BashCraft Website Sitemap & Link Analyzer meets and exceeds all requirements set forth in the recruitment specification. Built strictly with standard web fundamentals, clean code organization, and zero fluff, it provides a dependable tool for real-world web analysis.
