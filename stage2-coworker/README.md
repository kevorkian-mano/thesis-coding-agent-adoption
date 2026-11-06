# Stage 2: locating repo owners (profile locations + inference + accuracy check)

## Quick start for teammates (any language: Java, JS/TS, Rust, Python, C#, C++, …)

**No code changes are needed.** The scripts work as they are for every language ecosystem.
**You do not paste repos into the script**: you give it your CSV file in the command.

1. Unzip this folder and put your repo list CSV in it. The CSV needs **one column with the repos**, called any of
   `repo`, `name`, `full_name`, `project_name`, `repo_name`, `github_url` or `url`, with values like
   `owner/repo` or `https://github.com/owner/repo`. A `stars` column is optional.
2. Install and set your GitHub token (classic token, no scopes needed):
   ```powershell
   pip install -r requirements.txt
   $env:GITHUB_TOKEN = "ghp_..."
   ```
3. Run the two passes, in this order (replace `my_repos.csv` with your file name):
   ```powershell
   py owner_locations.py --input my_repos.csv
   py infer_owner_country.py --input my_repos.csv --known owner_locations.csv
   ```
4. Results: `owner_locations.csv` (Pass 1), `owner_country_inferred.csv` + `inference_validation.csv` +
   `owners_by_country_final.csv` (Pass 2). Use only **high + medium** inferences; your accuracy per confidence
   level is in `inference_validation.csv`.

Both scripts save progress; if they stop, run the same command again. Pass 2 takes about 1–2 hours per
~5,000 owners. Owner countries are personal data: share only aggregate counts.

---

Finds the country of the owner of every repo in a corpus, in two passes, and measures how accurate the inferred countries are.

| File | Role |
|---|---|
| `owner_locations.py` | **Pass 1.** Fetches each owner's profile location and maps the free text to a country/continent. |
| `infer_owner_country.py` | **Pass 2.** Infers the country of owners **without** a usable location from other GitHub clues, gives each guess a confidence level, and checks accuracy against the owners whose country **is** known from Pass 1. |
| `classify_egypt_accounts.py` | Shared helpers only (GitHub session, rate-limit handling, cache files, the Egyptian place list). Nothing to run here for this stage. |

## Setup

```powershell
pip install -r requirements.txt
$env:GITHUB_TOKEN = "ghp_..."          # classic token, no scopes needed
```

Input: a CSV with a repo column (see Quick start); a `stars` column is optional (if present, each owner's most-starred repo is used, otherwise the first one listed). Works for any language ecosystem. Put it in this folder (or pass its path).

## Run order

```powershell
py owner_locations.py --input java_repos_final_5290.csv
py infer_owner_country.py --input java_repos_final_5290.csv --known owner_locations.csv
```

Both scripts cache everything they download (`cache_*.jsonl`); rerun the same command to resume. Once all owners are cached, both run without a token. Pass 2 takes about 1–2 hours for ~4,700 owners (≈1,600 + 1,200 GraphQL requests).

## Pass 1: profile location → country (`owner_locations.py`)

Offline matching of the location text, in this order: a part that is a country name/alias ("USA", "Deutschland", "中国") → a state/province ("California", "Karnataka") → a city (34,000 cities from geonamescache; real names beat alternative names; the biggest city of a name wins, unless a US state code follows it, so "Alexandria, VA" → US) → US state code ("Austin, TX") → a country name inside the text → non-Latin place names (北京, 서울) → a large city inside the text. Small Egyptian towns via the Egyptian place list. Jokes and non-places ("Earth", "127.0.0.1", "Antarctica"), and continent-only text, are not placed. Accents are ignored; one/two-letter parts are never matched to cities.

Outputs: `owner_locations.csv` (one row per owner: location, country_code, country, continent, how it matched), `owners_by_country.csv`, `owners_by_continent.csv`.

## Pass 2: inference + confidence (`infer_owner_country.py`)

For every owner, clues are collected from the owner's profile and their most-starred repo in the corpus. **The profile location is never used as a clue**, which is what makes the accuracy check fair. Each clue votes for a country with a weight:

| Clue | Example | Weight |
|---|---|---|
| Java/Kotlin package / build files (pom `groupId`, gradle `group`, `src/main/java` or `src/main/kotlin` top folder) | `br.com.loja` → BR, `com.alibaba` → CN | 3 |
| **Manifests, any language**: author emails and URLs in `package.json`, `Cargo.toml`, `pyproject.toml`, `setup.py/cfg`, `composer.json`, `go.mod`, `Directory.Build.props`, `pubspec.yaml` (emails also from pom `<developers>`) | author `max@firma.de` → DE, homepage `empresa.com.br` → BR, `module gitee.com/…` → CN | 2–3 |
| Package mirrors used only in China (in any manifest or build file) | `maven.aliyun.com`, `npmmirror.com` → CN | 2.5 |
| Emails: profile + the owner's own commit emails (country domain, national provider, company) | `@qq.com` → CN, `@guc.edu.eg` → EG, `@web.de` → DE | 3 |
| Network: followers/following (users) or public members (organizations), located via Pass 1's resolver | ≥ 60% of ≥ 5 located connections in one country | 2–3 |
| Contributors: authors of the latest 100 commits of up to 3 repos (owner and bots excluded) | 3 of 4 located contributors in DE | 1.5–3 |
| Linked websites / national platforms | csdn.net → CN, habr.com → RU, a `.de` site | 2–2.5 |
| Language of README, commit messages, bio (writing system first for Chinese/Japanese/Korean, then langdetect) | Chinese → CN, Vietnamese → VN, Portuguese → BR | 1–2.5 |
| Donation links | Afdian / WeChat / Alipay → CN, Pix → BR | 2 |
| Company or bio naming a country | "Backend dev from Vietnam" | 1.5 |

English, Spanish and Arabic text give no vote (spoken in too many countries). Timezones and names are deliberately not used. A domain votes only once (e.g. the same domain as email and homepage). In Maven/Gradle build files, repository URLs only count if they are China-only mirrors: other hosts there are third-party library repositories and say nothing about the owner.

**Language neutrality:** all clues except the Java/Kotlin package clue work for any ecosystem; the manifest clue replaces it for JS/TS, Rust, Python, PHP, Go, C#/.NET and Dart. C/C++ have no standard manifest and rely on the other clues. Accuracy is always measured on the corpus itself (next section), so other stacks get their own, honest figures.

**Confidence**, from the vote totals:
- **high**: top country total ≥ 4 and at least 2× the runner-up
- **medium**: total ≥ 2 and at least 1.5× the runner-up
- **low**: any other vote; a guess resting **only** on contributors is capped at low (contributors alone were right only ~68% of the time)
- **none**: no clue at all

**Accuracy check:** the same inference is run on owners whose country is known from Pass 1, and the guess is compared with the real country, per confidence level. Result on the 5,290-repo Java corpus (1,849 known owners):

| Confidence | Owners | Correct |
|---|---|---|
| high | 719 | **94.0%** |
| medium | 416 | **81.5%** |
| low | 270 | 67.8% |
| none | 444 | – |

Use only **high + medium** guesses in country tables. Most remaining errors are between Chinese-speaking places (Hong Kong/Taiwan/Singapore/Japan → China) and US → China.

Coverage on that corpus: 1,849 owners from profile location (39%) + 1,698 high/medium inferences = **3,547 of 4,718 owners located (75%)**.

Outputs:
- `owner_country_inferred.csv`: per owner: known country (if any), inferred country, confidence, score, and the evidence behind it
- `inference_validation.csv`: the accuracy table above
- `owners_by_country_final.csv`: per country: known + high + medium inferred owners

## Notes
- Per-owner countries (especially inferred ones) are personal data: report aggregates only, never per-person rows.
- `langdetect` is random unless seeded; the script seeds it, and evidence is written in a fixed order, so reruns give identical files.
- Clue tables (email providers, platforms, companies, languages) are at the top of `infer_owner_country.py` and can be extended.
