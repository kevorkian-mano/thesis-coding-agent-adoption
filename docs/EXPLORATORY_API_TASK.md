# Exploratory GitHub API Task
## Topic 2 — JavaScript / TypeScript / npm
**Student:** Manuel Youssef Haik Kevorkian  
**Date:** September 2026  

---

## 1. Objective

The goal of this exploratory task was to investigate GitHub's API surfaces to determine:

- What data is available for studying repository activity and developer behaviour
- Which API (REST vs GraphQL) is more suitable for large-scale corpus construction
- What the practical limits are (rate limits, result caps, query costs)
- What pitfalls exist that could silently skew results if not addressed

The findings from this exploration directly shaped the design of the data collection pipeline used in this thesis.

---

## 2. GitHub API Surfaces Explored

GitHub exposes three API surfaces relevant to this study:

| API | Base URL | Best used for |
|-----|----------|---------------|
| REST API | `api.github.com` | Single-resource lookups (one repo, one user) |
| GraphQL API | `api.github.com/graphql` | Batch fetching — multiple resources in one request |
| Search API | `api.github.com/search` | Discovery — finding repos or users matching criteria |

### 2.1 REST API

The REST API was explored for the following endpoints:

| Endpoint | What it returns |
|----------|----------------|
| `GET /repos/{owner}/{repo}` | Full repo metadata (stars, forks, language, dates) |
| `GET /repos/{owner}/{repo}/commits` | Commit list with author, date, message |
| `GET /repos/{owner}/{repo}/contributors` | List of contributors with commit counts |
| `GET /repos/{owner}/{repo}/languages` | Byte count per language |
| `GET /repos/{owner}/{repo}/contents/{path}` | File existence check (e.g. `package.json`) |
| `GET /users/{login}` | User profile (location, followers, public repos) |
| `GET /search/repositories` | Repositories matching a query string |
| `GET /search/users` | Users matching a query string (e.g. by location) |

**Key finding:** Every endpoint returns data for exactly one resource. To check 1,000 repos, you need 1,000 separate HTTP requests. At GitHub's authenticated rate limit of 5,000 requests/hour, a corpus of even a few thousand repos would take hours if REST-only calls are made per repo.

### 2.2 GraphQL API

The GraphQL API allows multiple resources to be fetched in a single HTTP request using **aliased queries**. For example, 50 user profiles can be fetched in one request by aliasing each:

```graphql
query {
  user_0: user(login: "alice") { followers { totalCount } }
  user_1: user(login: "bob")   { followers { totalCount } }
  ...
}
```

This was the key discovery that made the pipeline feasible. A single GraphQL request can replace 50 individual REST calls.

**Rate limit:** 5,000 points/hour. Each field in the query costs points — simple scalar fields (counts, strings) cost 1 point; traversals (listing commits, listing files) cost proportionally more.

### 2.3 Search API

The Search API supports free-text queries over repositories and users:

```
GET /search/repositories?q=language:JavaScript+fork:false+pushed:>2023-01-01
GET /search/users?q=location:Egypt
```

**Critical limitation discovered:** GitHub caps Search API results at **1,000 per query**, regardless of how many matching repos exist. A query for all JavaScript repos would silently return only the top 1,000 by star count. Without addressing this, the corpus would only contain high-starred repos and miss the "small" stratum entirely.

---

## 3. Key Findings

### 3.1 The 1,000-result Search Cap

Running a single search query for JavaScript repos sorted by stars returned only large-starred repos. The "small" stratum (0–50 stars) — which represents the majority of real-world repos — was entirely absent.

**Solution:** Run separate queries per **star band**:
- `stars:0..50` → small stratum
- `stars:51..500` → medium stratum  
- `stars:>500` → large stratum

Each band gets its own 1,000-result quota, producing a stratified corpus that covers all sizes.

### 3.2 The `history { totalCount }` Rate Limit Trap

During GraphQL exploration, the following query field was tested to count commits per repo:

```graphql
defaultBranchRef {
  target {
    ... on Commit {
      history { totalCount }
    }
  }
}
```

Although `totalCount` appears to be a simple integer, this field forces GitHub's servers to traverse the **entire commit history** of the repository to produce the count. On a repo with 10,000 commits, this is 10,000 nodes scanned server-side. Including this field in a batch query for 50 repos exhausted the entire hourly GraphQL quota in a single request, producing a **3,602-second rate limit sleep** during testing.

**Solution:** Remove `history { totalCount }` entirely from batch queries. Use `pushedAt >= 2023-01-01` as an activity proxy, and `size_kb > 0` as a proxy for non-empty repos.

### 3.3 Git Tree Lookup Cost (`object(expression:...)`)

To check whether a `package.json` file exists at a repo's root, the following GraphQL field was tested:

```graphql
packageJson: object(expression: "HEAD:package.json") { id }
```

This resolves the git object tree for the repo's HEAD commit to find a specific path. When included in a batch query covering 10 accounts × 100 repos = 1,000 repos, GitHub consistently returned **HTTP 502 (Bad Gateway)** errors, indicating a server-side timeout.

**Solution:** Remove the `packageJson` check from batch queries. For the base corpus (Stage 1), this check is performed via a dedicated REST call per repo. For the Egypt-specific corpus (Stage 2c), this check is skipped and documented as a known limitation.

### 3.4 Location Search: Arabic Terms Required

Initial exploration of the GitHub user search API used only English location terms (`Egypt`, `Cairo`, `Alexandria`, `Giza`). A manual review of Egyptian developer profiles revealed that a significant portion use Arabic location strings: `مصر`, `القاهرة`, `الإسكندرية`, `الجيزة`.

Searching with English terms only would undercount Egyptian developers. Both English and Arabic term sets are used in all user search queries.

### 3.5 REST vs GraphQL Performance Comparison

| Approach | Repos/accounts per request | Time for 1,000 repos |
|----------|---------------------------|----------------------|
| REST (1 call per repo) | 1 | ~12 minutes |
| GraphQL (50 repos per request) | 50 | ~15 seconds |

The performance advantage of GraphQL batch queries is approximately **50× fewer API calls**, making corpus construction feasible within a single session.

---

## 4. Authentication and Rate Limits

| API | Unauthenticated limit | Authenticated limit |
|-----|-----------------------|---------------------|
| REST | 60 requests/hour | 5,000 requests/hour |
| GraphQL | Not available | 5,000 points/hour |
| Search | 10 requests/minute | 30 requests/minute |

All scripts in this pipeline require a GitHub Personal Access Token set as the `GITHUB_TOKEN` environment variable. Without authentication, unauthenticated limits make large-scale data collection impossible.

**Rate limit handling:** All scripts read the `X-RateLimit-Reset` response header and sleep exactly until the reset time, rather than using a fixed sleep value. This avoids both over-sleeping (wasting time) and under-sleeping (immediate re-failure).

---

## 5. How Findings Shaped the Pipeline

| Finding | Design decision |
|---------|----------------|
| 1,000 search cap | Star-band queries (0..50, 51..500, >500) run separately |
| `history { totalCount }` cost | Removed from all batch GraphQL queries |
| `object(expression:...)` cost | Removed from bulk queries; REST-only for base corpus |
| REST cost per entity | GraphQL batching (50 entities per request) used throughout |
| Arabic location terms | Both English and Arabic terms used in all user searches |
| Location substring matching | Egypt-specific corpus includes manual false-positive review step |

---

## 6. Tools Used

| Tool | Purpose |
|------|---------|
| Python `requests` library | All HTTP calls to GitHub API |
| `pandas` | Data loading, filtering, deduplication, CSV output |
| GitHub GraphQL Explorer | Interactive query testing before writing scripts |
| GitHub REST API docs | Endpoint reference and field documentation |

---

## 7. Output of the Exploration

The exploratory phase produced:

- A working understanding of GitHub API capabilities and limits
- Identification of the three critical pitfalls (search cap, history cost, tree lookup cost)
- A set of reusable helper functions (`rate_limited_get`, `graphql_post`) used in all pipeline scripts
- The GraphQL batch query pattern used in Stages 1, 2a, 2b, and 2c
- The star-band search strategy used in Stage 1

These findings are documented in the pipeline scripts and in the Shared Corpus Methodology document.
