# Retrieval Recipe: discourse.mcneel.com Search

## Purpose

Search the McNeel Discourse forum as your **first fallback** when you would otherwise
assert something from training data. The forum has ground-truth from McNeel developers
and plugin authors. Consult it **before** stating "this is how it works" on any surface
that can change between Rhino or template releases. Specifically, search before asserting
on:

- MSBuild post-build copy targets (volatile; varies by Rhino.Templates version)
- `<Nullable>`, `<LangVersion>`, or other `.csproj` defaults from Rhino.Templates
- Threading rules that differ between GH1 and the Rhino 8 parallel solver
- NuGet package version requirements or SDK breaking changes
- Any behaviour reported as changed in a recent Rhino WIP or release

If forum search returns no useful results, escalate to the dev guide — see
`[[dev-guide-index.md]]`.

---

## Base Search URL

```
https://discourse.mcneel.com/search.json?q=<query>
```

URL-encode the query string: spaces become `+`, special characters are percent-encoded.

**Example — bare keyword search:**

```
https://discourse.mcneel.com/search.json?q=SolveInstance+threading
```

The endpoint is publicly accessible — no authentication required. Use the `WebFetch` tool
to call it; do not depend on `curl`, `jq`, or any local CLI tooling.

---

## Category Scoping

Append a category filter to restrict results to developer forums instead of general user
forums. Use `+%23<slug>` (where `%23` is URL-encoded `#`, the Discourse category-filter
sigil, and `+` separates it from the preceding term):

| Category name         | Slug                    | Filter token           |
|-----------------------|-------------------------|------------------------|
| Grasshopper Developer | `grasshopper-developer` | `+%23grasshopper-developer` |
| Rhino Developer       | `rhino-developer`       | `+%23rhino-developer`  |
| Scripting             | `scripting`             | `+%23scripting`        |

**Why developer categories beat general categories for plugin-author questions:**

- The `Grasshopper Developer` category (id 8) is where McNeel developers and experienced
  plugin authors reply. Answers reference the SDK, NuGet packages, and MSBuild targets
  directly.
- General user categories (`Grasshopper`, `Rhino`) discuss workflow, not the C# SDK.
  Hitting those categories for a `GH_Component` question returns noise.

**Category-scoped example:**

```
https://discourse.mcneel.com/search.json?q=SolveInstance+threading+%23grasshopper-developer
```

---

## Topic Fetch

Once you have a `topic_id` from the search results, fetch the full thread:

```
https://discourse.mcneel.com/t/<topic-id>.json
```

You may also use the slug form (both resolve identically):

```
https://discourse.mcneel.com/t/<slug>/<topic-id>.json
```

**Example:**

```
https://discourse.mcneel.com/t/98982.json
https://discourse.mcneel.com/t/c-custom-component-solveinstance-behavior/98982.json
```

---

## Response Shape

### Search response (`search.json`)

Top-level keys: `posts`, `topics`, `users`, `categories`, `tags`, `groups`,
`grouped_search_result`.

The fields an agent should care about are on `topics[]`:

| Field            | Type    | Notes                                              |
|------------------|---------|----------------------------------------------------|
| `id`             | integer | Use to fetch the full thread via `/t/<id>.json`    |
| `title`          | string  | Plain text title                                   |
| `slug`           | string  | URL slug; usable in the `/t/<slug>/<id>.json` form |
| `posts_count`    | integer | Total replies; higher often means more discussion  |
| `category_id`    | integer | 8 = Grasshopper Developer (see table above)        |
| `created_at`     | string  | ISO 8601 timestamp                                 |
| `has_accepted_answer` | boolean | Discourse "Solved" plugin flag               |

Note: the `categories` array in the search response is **empty** — category names are not
resolved inline. Use the `category_id` values in the table above to interpret results.

The `posts[]` array in the search response contains **excerpt objects** (blurbs), not full
post bodies. To read actual content, fetch the topic.

### Topic response (`/t/<id>.json`)

Top-level keys include: `id`, `title`, `slug`, `category_id`, `posts_count`, `post_stream`,
`tags`, `created_at`, `views`, `like_count`.

Posts live at `post_stream.posts[]`. Fields an agent should care about:

| Field            | Type    | Notes                                                        |
|------------------|---------|--------------------------------------------------------------|
| `id`             | integer | Post id                                                      |
| `post_number`    | integer | 1-based position in thread; post 1 is the opening question  |
| `username`       | string  | Author's forum handle                                        |
| `cooked`         | string  | **HTML body** — the rendered post content                    |
| `created_at`     | string  | ISO 8601 timestamp                                           |
| `like_count`     | integer | Upvote signal; higher = more community-validated             |
| `accepted_answer`| boolean | True on the post marked as the accepted solution             |

**Important:** `cooked` is HTML, not plain text. Strip or ignore tags when reading; the
useful content is inside `<p>`, `<pre>`, `<code>` elements.

There is no `raw` field in public topic responses — `cooked` is the only body field
available without authentication.

---

## Worked Example

**Question:** Does standard Grasshopper run `SolveInstance` calls concurrently between
components, and what changes in the Rhino 8 parallel solver?

### Step 1 — Run the search

```
WebFetch: https://discourse.mcneel.com/search.json?q=GH_Component+SolveInstance+threading+%23grasshopper-developer
```

**Observed result (verified 2026-05-17):** 30 topics returned.

Top 3 topics:

| Rank | id    | title                                                                    | posts_count |
|------|-------|--------------------------------------------------------------------------|-------------|
| 1    | 98982 | C# custom component SolveInstance() behavior                             | 12          |
| 2    | 80496 | Parallelising DA.SetData                                                 | 11          |
| 3    | 55613 | C# Understanding ComputeData() and SolveInstance() -- what happens when? | 3           |

Topic 98982 has 12 posts and directly addresses `SolveInstance` threading behaviour —
fetch it.

### Step 2 — Fetch the thread

```
WebFetch: https://discourse.mcneel.com/t/98982.json
```

**Response shape observed:**

- `title`: "C# custom component SolveInstance() behavior"
- `id`: 98982
- `slug`: "c-custom-component-solveinstance-behavior"
- `category_id`: 8 (Grasshopper Developer)
- `posts_count`: 12
- `post_stream.posts`: array of 12 post objects

### Step 3 — Extract the relevant posts

Read `post_stream.posts` in `post_number` order. For each post:

1. Check `accepted_answer` — if `true`, read this post first.
2. Check `like_count` — higher-liked posts carry stronger community signal.
3. Parse `cooked` — strip HTML tags; focus on `<pre>`/`<code>` blocks for code examples
   and `<p>` text for explanations.

**What an agent extracts from topic 98982:**

- Post 3 (by `Dani_Abalde`, `like_count` high) explains in `cooked`:
  > "Nothing happens at the same time in software, except (virtually) when the process is
  > running in parallel in different threads. But GH doesn't do that, it just does it
  > inside some components, but not between them. Components run one by one, ensuring all
  > expired objects are computed in sequence."

This is primary-source confirmation that standard Grasshopper does **not** run
`SolveInstance` calls concurrently between components — a fact that can change in Rhino 8's
parallel solver and should be verified against the latest forum posts rather than assumed.

### Step 4 — Resolve the parallel-solver half of the question

Topic 98982 settled the standard / GH1 case: components run one by one. The Rhino 8
parallel solver half of the original question is **not** answered by 98982. Topic 80496
("Parallelising DA.SetData") directly addresses thread safety when parallelism is
introduced inside a component, which is the Rhino 8 case. Fetch it the same way:

```
WebFetch: https://discourse.mcneel.com/t/80496.json
```

Apply the same extract pattern: order by `post_number`, check `accepted_answer`, parse
`cooked`. Quote the primary-source conclusion in your answer; do not paraphrase from
training.

---

## See Also

- `[[component-lifecycle.md]]` — `GH_Component` subclass structure and the role of
  `SolveInstance` in the component lifecycle
- `[[threading-and-the-main-thread.md]]` — Rhino 8 parallel solver rules, which
  main-thread APIs are unsafe from `SolveInstance`, and patterns for deferring them
