// Site with a sitemap but bare pages, broken/redirected links, and a soft-404.
const html = { "content-type": "text/html" };
const bare = (links = []) => [
  "<html><head>",
  "<title>Untitled</title>",
  '<script type="application/ld+json">{oops}</script>',
  "</head><body>",
  ...links.map((l) => `<a href="${l}">${l}</a>`),
  "</body></html>",
].join("\n");

export default {
  "GET /robots.txt": { status: 200, headers: { "content-type": "text/plain" }, body: "User-agent: *\nAllow: /\n" },
  "GET /sitemap.xml": { status: 200, headers: { "content-type": "application/xml" }, body:
    "<urlset><url><loc>https://example.com/</loc></url><url><loc>https://example.com/projects/a</loc></url><url><loc>https://example.com/gone</loc></url></urlset>" },
  "GET /": { status: 200, headers: html, body: bare(["/dead", "/moved"]) },
  "GET /projects/a": { status: 200, headers: html, body: bare() },
  "GET /gone": { status: 404, headers: {}, body: "" },
  "GET /dead": { status: 404, headers: {}, body: "" },
  "GET /moved": { status: 301, headers: { location: "https://example.com/projects/a" }, body: "" },
  "GET /this-page-should-not-exist-audit-probe": { status: 200, headers: html, body: "<html><body>Home</body></html>" },
};
