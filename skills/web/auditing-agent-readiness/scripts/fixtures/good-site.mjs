// Minimal agent-ready site. Keys: "METHOD /path", "METHOD /path accept=<value>",
// "POST /path <jsonrpc method>", or "DOH <name>".
const md = { "content-type": "text/markdown; charset=utf-8" };
const json = { "content-type": "application/json" };
export default {
  "GET /": { status: 200, headers: { "content-type": "text/html", link: '</sitemap-index.xml>; rel="sitemap"', "x-robots-tag": "all" }, body: "<html></html>" },
  "GET /robots.txt": { status: 200, headers: { "content-type": "text/plain" }, body:
    "User-agent: *\nAllow: /\nUser-agent: GPTBot\nAllow: /\nUser-agent: ClaudeBot\nAllow: /\nUser-agent: PerplexityBot\nAllow: /\nUser-agent: Google-Extended\nAllow: /\nUser-agent: CCBot\nAllow: /\nContent-Signal: search=yes, ai-train=yes, ai-input=yes\nSitemap: https://example.com/sitemap-index.xml\n" },
  "GET /sitemap-index.xml": { status: 200, headers: { "content-type": "application/xml" }, body: "<sitemapindex/>" },
  "GET /llms.txt": { status: 200, headers: md, body: "# Example\n\n## Projects\n- [A](https://example.com/projects/a)\n" },
  "GET /pt/llms.txt": { status: 200, headers: md, body: "# Example\n\n- [A](https://example.com/pt/projects/a)\n" },
  "GET /projects/a.md": { status: 200, headers: md, body: "# A\n" },
  "GET /projects/a accept=text/markdown": { status: 200, headers: md, body: "# A\n" },
  "GET /projects/a": { status: 200, headers: { "content-type": "text/html" }, body: "<html></html>" },
  "GET /.well-known/api-catalog": { status: 200, headers: { "content-type": "application/linkset+json" }, body: JSON.stringify({ linkset: [{ anchor: "https://example.com", "service-desc": [{ href: "https://example.com/.well-known/mcp.json" }, { href: "https://example.com/.well-known/agent-skills/index.json" }] }] }) },
  "GET /.well-known/mcp.json": { status: 200, headers: json, body: JSON.stringify({ name: "example", transport: { type: "streamable-http", url: "https://example.com/api/mcp" }, tools: [{ name: "get_page" }] }) },
  "POST /api/mcp initialize": { status: 200, headers: json, body: JSON.stringify({ jsonrpc: "2.0", id: 0, result: { protocolVersion: "2025-06-18", serverInfo: { name: "example" }, capabilities: { tools: {} } } }) },
  "POST /api/mcp tools/list": { status: 200, headers: json, body: JSON.stringify({ jsonrpc: "2.0", id: 1, result: { tools: [{ name: "get_page", inputSchema: { type: "object" } }] } }) },
  "GET /.well-known/agent-skills/index.json": { status: 200, headers: json, body: JSON.stringify({ skills: [{ name: "example-content", type: "skill-md", url: "https://example.com/.well-known/agent-skills/example-content/SKILL.md", digest: "sha256:" + "a".repeat(64) }] }) },
  "GET /.well-known/agent-skills/example-content/SKILL.md": { status: 200, headers: md, body: "---\nname: example-content\ndescription: x\n---\n# x\n" },
  "DOH _mcp._agents.example.com": { status: 200, headers: json, body: JSON.stringify({ Status: 0, Answer: [{ name: "_mcp._agents.example.com", type: 64, data: "1 example.com. alpn=h2" }] }) },
};
