// Site with no security headers, an unflagged cookie, mixed content,
// SRI-less third-party assets, a verbose Server header, and no https redirect.
export default {
  "GET /": {
    status: 200,
    headers: {
      "content-type": "text/html",
      "server": "Apache/2.4.41 (Ubuntu)",
      "set-cookie": "session=abc123; Path=/",
    },
    body: [
      "<html><head>",
      '<script src="http://cdn.example.net/analytics.js"></script>',
      '<script src="https://cdn.example.net/widget.js"></script>',
      '<link rel="stylesheet" href="https://fonts.example.net/f.css">',
      "</head><body></body></html>",
    ].join("\n"),
  },
  "GET http /": { status: 200, headers: { "content-type": "text/html" }, body: "<html></html>" },
};
