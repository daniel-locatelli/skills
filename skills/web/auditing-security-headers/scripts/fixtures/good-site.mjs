// Static site with a full, strict header set. Keys: "GET /path"; the
// plaintext-HTTP probe is keyed "GET http /path".
export default {
  "GET /": {
    status: 200,
    headers: {
      "content-type": "text/html; charset=utf-8",
      "content-security-policy": "default-src 'self'; script-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'",
      "strict-transport-security": "max-age=63072000; includeSubDomains; preload",
      "x-content-type-options": "nosniff",
      "referrer-policy": "strict-origin-when-cross-origin",
      "permissions-policy": "camera=(), microphone=(), geolocation=()",
    },
    body: '<html><head><script src="/app.js"></script><link rel="stylesheet" href="/site.css"></head><body><img src="/a.png"></body></html>',
  },
  "GET http /": { status: 301, headers: { location: "https://example.com/" }, body: "" },
};
