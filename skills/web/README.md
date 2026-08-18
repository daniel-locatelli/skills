# Web skills

Skills for auditing and improving deployed websites: Lighthouse / Core Web
Vitals, agent readiness (`llms.txt`, `.well-known`, MCP), security headers,
SEO & social, content & i18n integrity. Generic core with marked "If Astro" /
"If Cloudflare" notes. Design: `docs/superpowers/specs/2026-08-18-web-quality-audit-skills-design.md`.

Skills: `optimizing-web-performance`, `auditing-website-quality` (hub),
`auditing-agent-readiness`. All check scripts emit the same findings contract
`{ dimension, score, findings[{ id, severity, title, evidence, url|file, fix, effort, autoFixable }] }`;
run tests with `node --test skills/web/*/scripts/*.test.mjs`.
