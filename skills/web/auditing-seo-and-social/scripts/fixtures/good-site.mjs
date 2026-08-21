// SEO-complete two-page site with a pt locale. Keys: "METHOD /path".
const html = { "content-type": "text/html; charset=utf-8" };
const page = ({ title, path, ptPath, jsonld = '{"@context":"https://schema.org","@type":"WebPage"}', links = [] }) => [
  "<html><head>",
  `<title>${title}</title>`,
  `<meta name="description" content="About ${title}.">`,
  `<link rel="canonical" href="https://example.com${path}">`,
  `<meta property="og:title" content="${title}">`,
  `<meta property="og:description" content="About ${title}.">`,
  '<meta property="og:image" content="https://example.com/og.png">',
  `<meta property="og:url" content="https://example.com${path}">`,
  '<meta name="twitter:card" content="summary_large_image">',
  `<script type="application/ld+json">${jsonld}</script>`,
  `<link rel="alternate" hreflang="en" href="https://example.com${path}">`,
  `<link rel="alternate" hreflang="pt" href="https://example.com${ptPath}">`,
  `<link rel="alternate" hreflang="x-default" href="https://example.com${path}">`,
  "</head><body>",
  ...links.map((l) => `<a href="${l}">${l}</a>`),
  "</body></html>",
].join("\n");

export default {
  "GET /robots.txt": { status: 200, headers: { "content-type": "text/plain" }, body: "User-agent: *\nAllow: /\nSitemap: https://example.com/sitemap.xml\n" },
  "GET /sitemap.xml": { status: 200, headers: { "content-type": "application/xml" }, body:
    "<urlset><url><loc>https://example.com/</loc></url><url><loc>https://example.com/projects/a</loc></url><url><loc>https://example.com/pt/</loc></url></urlset>" },
  "GET /": { status: 200, headers: html, body: page({ title: "Example — Home", path: "/", ptPath: "/pt/", links: ["/projects/a"] }) },
  "GET /projects/a": { status: 200, headers: html, body: page({ title: "Project A — Example", path: "/projects/a", ptPath: "/pt/projects/a" }) },
  "GET /pt/": { status: 200, headers: html, body: page({ title: "Example — Início", path: "/pt/", ptPath: "/pt/" }) },
  "GET /pt/projects/a": { status: 200, headers: html, body: page({ title: "Projeto A — Example", path: "/pt/projects/a", ptPath: "/pt/projects/a" }) },
  "GET /og.png": { status: 200, headers: { "content-type": "image/png" }, body: "png" },
};
