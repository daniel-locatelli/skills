// Site with nothing agent-facing and a robots.txt that blocks AI crawlers.
export default {
  "GET /": { status: 200, headers: { "content-type": "text/html", "x-robots-tag": "noindex" }, body: "<html></html>" },
  "GET / ua=GPTBot": { status: 403, headers: {}, body: "" },
  "GET / ua=ClaudeBot": { status: 403, headers: {}, body: "" },
  "GET / ua=PerplexityBot": { status: 403, headers: {}, body: "" },
  "GET /robots.txt": { status: 200, headers: { "content-type": "text/plain" }, body: "User-agent: *\nAllow: /\nUser-agent: GPTBot\nDisallow: /\nUser-agent: ClaudeBot\nDisallow: /\n" },
  "GET /sitemap.xml": { status: 404, headers: {}, body: "" },
  "GET /sitemap-index.xml": { status: 404, headers: {}, body: "" },
  "GET /llms.txt": { status: 404, headers: {}, body: "" },
  "GET /.well-known/api-catalog": { status: 404, headers: {}, body: "" },
  "GET /.well-known/mcp.json": { status: 404, headers: {}, body: "" },
  "GET /.well-known/agent-skills/index.json": { status: 404, headers: {}, body: "" },
  "DOH _mcp._agents.example.com": { status: 200, headers: { "content-type": "application/json" }, body: JSON.stringify({ Status: 3, Answer: [] }) },
};
