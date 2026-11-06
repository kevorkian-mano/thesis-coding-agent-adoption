"""
infer_owner_country.py
======================
Guesses the country of repo owners who have NO location on GitHub, using
other clues from the GitHub API, and measures how accurate the guesses are
on owners whose location we DO know.

Clues (each one is a "vote" for a country, with a weight):
  1. Java/Kotlin package / build  groupId in pom.xml / build.gradle, and the
                                   top folder of src/main/java or src/main/kotlin
                                   (br.com.x -> Brazil, cn.edu.x -> China,
                                   com.alibaba -> China, ...)
  2. Emails                        profile email + the owner's commit emails:
                                   country domain (.de, .com.br, .edu.eg) or
                                   national provider (qq.com, yandex.ru, naver.com)
  3. Language of the text          README, commit messages, bio, description
                                   (Chinese, Korean, Portuguese, ...; English
                                   and Spanish/Arabic say nothing)
  4. Network                       where most followers/following (users) or
                                   public members (organizations) are located
  5. Other repo clues              FUNDING.yml / README payment links
                                   (Afdian, WeChat/Alipay -> China, Pix -> Brazil)
  6b. Manifests (any language)    author emails and URLs in package.json, Cargo.toml,
                                   pyproject.toml, setup.py/cfg, composer.json, go.mod,
                                   Directory.Build.props, pubspec.yaml (and pom/gradle):
                                   judged like emails/websites; also package mirrors
                                   used only in China (maven.aliyun.com, npmmirror.com)
  6. Websites and linked accounts  country domain of the website / blog, or
                                   national platforms (csdn, juejin, qiita,
                                   velog, habr, vk, ...)
  7. Contributors                  where the other people committing to the
                                   owner's repos (latest 100 commits of up to 3
                                   repos; owner and bots left out) are located.
                                   Mainly helps organizations, which have no
                                   followers.
  + company / bio mentioning a country by name

The profile location itself is NEVER used as a clue - only to check accuracy.

Confidence:
  high    total weight >= 4 and the top country has >= 2x the runner-up
  medium  total weight >= 2 and the top country has >= 1.5x the runner-up
  low     anything else with at least one vote
  none    no clues at all

Ethics: this infers where people live although they chose not to say.
Report aggregate numbers (country counts) only, never per-person guesses.

Outputs:
  owner_country_inferred.csv     one row per owner: known country, guess,
                                 confidence, and the evidence behind it
  inference_validation.csv       accuracy per confidence level, measured on
                                 owners whose country is known
  owners_by_country_final.csv    per country: known + inferred (high/medium)

Usage:
  pip install geonamescache langdetect
  $env:GITHUB_TOKEN = "ghp_xxx"
  py infer_owner_country.py           (~1,600 requests, about 1-2 hours)
Progress is cached; rerun the same command to resume. Once everything is
cached it runs without a token.
"""

import os
import re
from collections import Counter, defaultdict

import pandas as pd
from langdetect import DetectorFactory, detect_langs
from langdetect.lang_detect_exception import LangDetectException

from classify_egypt_accounts import (
    make_session, post_graphql, load_cache, append_cache, _safe_login,
)
from owner_locations import Geo, REGION_ALIASES, read_repo_list

DetectorFactory.seed = 0          # langdetect is random otherwise

CACHE_FILE = "cache_owner_signals.jsonl"
BATCH_SIZE = 3                    # owners per request (each pulls a lot)
TEXT_LIMIT = 20_000               # characters kept per text field

CONTRIB_CACHE = "cache_owner_contributors.jsonl"
CONTRIB_REPOS = 3                 # repos per owner (their most-starred ones in the list)
CONTRIB_COMMITS = 100             # latest commits per repo whose authors are read
CONTRIB_BATCH = 4                 # owners per request
BOT_LOGINS = {"dependabot", "renovate", "github-actions", "snyk-bot", "allcontributors",
              "imgbot", "codecov", "sonarcloud", "pre-commit-ci", "mergify", "copilot"}

# ─────────────────────────────────────────────────────────────────────────────
# Clue tables (edit freely)
# ─────────────────────────────────────────────────────────────────────────────

# Country domains that are mostly used for other things -> ignored
GENERIC_CCTLDS = {"io", "co", "me", "tv", "ai", "ly", "fm", "to", "cc", "ws", "la", "sh",
                  "so", "gg", "ac", "im", "sc", "vc", "nu", "tk", "ml", "ga", "cf", "gq",
                  "gl", "ms", "ag", "gd", "st", "am", "pw", "cx", "ps", "dj", "eu", "app",
                  "dev", "xyz", "one", "page", "site", "rs", "re", "mx_"}
TLD_FIX = {"uk": "GB", "su": "RU"}

EMAIL_PROVIDERS = {
    "qq.com": "CN", "163.com": "CN", "126.com": "CN", "foxmail.com": "CN", "sina.com": "CN",
    "sina.cn": "CN", "aliyun.com": "CN", "yeah.net": "CN", "139.com": "CN", "sohu.com": "CN",
    "vip.qq.com": "CN", "vip.163.com": "CN",
    "yandex.ru": "RU", "ya.ru": "RU", "mail.ru": "RU", "rambler.ru": "RU", "bk.ru": "RU",
    "inbox.ru": "RU", "list.ru": "RU", "yandex.com": "RU",
    "naver.com": "KR", "daum.net": "KR", "hanmail.net": "KR", "kakao.com": "KR",
    "web.de": "DE", "gmx.de": "DE", "t-online.de": "DE", "freenet.de": "DE", "posteo.de": "DE",
    "gmx.at": "AT", "gmx.ch": "CH", "bluewin.ch": "CH",
    "uol.com.br": "BR", "bol.com.br": "BR", "terra.com.br": "BR",
    "yahoo.co.jp": "JP", "docomo.ne.jp": "JP", "yahoo.com.br": "BR", "yahoo.fr": "FR",
    "orange.fr": "FR", "free.fr": "FR", "laposte.net": "FR", "sfr.fr": "FR",
    "libero.it": "IT", "virgilio.it": "IT", "alice.it": "IT",
    "wp.pl": "PL", "o2.pl": "PL", "onet.pl": "PL", "interia.pl": "PL",
    "seznam.cz": "CZ", "ukr.net": "UA", "i.ua": "UA", "abv.bg": "BG",
    "rediffmail.com": "IN", "yahoo.co.in": "IN", "naver.co.kr": "KR",
}

# Websites / platforms used almost only in one country
PLATFORMS = {
    "csdn.net": "CN", "juejin.cn": "CN", "juejin.im": "CN", "cnblogs.com": "CN",
    "zhihu.com": "CN", "bilibili.com": "CN", "gitee.com": "CN", "weibo.com": "CN",
    "jianshu.com": "CN", "oschina.net": "CN", "segmentfault.com": "CN", "afdian.net": "CN",
    "afdian.com": "CN", "xiaohongshu.com": "CN", "douyin.com": "CN", "yuque.com": "CN",
    "qiita.com": "JP", "zenn.dev": "JP", "hatenablog.com": "JP", "note.com": "JP",
    "velog.io": "KR", "tistory.com": "KR", "blog.naver.com": "KR", "brunch.co.kr": "KR",
    "habr.com": "RU", "vk.com": "RU", "vc.ru": "RU", "t.me": None,
    "tabnews.com.br": "BR", "viblo.asia": "VN",
    # package mirrors used almost only in China (seen in build files / manifests)
    "maven.aliyun.com": "CN", "mirrors.aliyun.com": "CN", "npmmirror.com": "CN",
    "npm.taobao.org": "CN", "registry.npm.taobao.org": "CN", "mirrors.cloud.tencent.com": "CN",
    "mirrors.huaweicloud.com": "CN", "repo.huaweicloud.com": "CN", "mirrors.163.com": "CN",
}

# Language-neutral clue: the standard manifest file of each ecosystem. Author emails
# and URLs in it are judged like profile emails and websites (country domains,
# national providers, platforms). GraphQL alias -> path in the repo.
MANIFESTS = {
    "m_pkgjson": "package.json",          # JavaScript / TypeScript
    "m_cargo": "Cargo.toml",              # Rust
    "m_pyproject": "pyproject.toml",      # Python
    "m_setuppy": "setup.py",              # Python
    "m_setupcfg": "setup.cfg",            # Python
    "m_composer": "composer.json",        # PHP
    "m_gomod": "go.mod",                  # Go
    "m_buildprops": "Directory.Build.props",  # C# / .NET
    "m_pubspec": "pubspec.yaml",          # Dart / Flutter
}
IGNORED_EMAIL = re.compile(r"noreply|no-reply|example\.(com|org)|localhost|test\.com|domain\.com|email\.com", re.I)

# Companies / orgs in groupIds, emails and company fields
COMPANIES = {
    "alibaba": "CN", "alipay": "CN", "antgroup": "CN", "tencent": "CN", "baidu": "CN",
    "huawei": "CN", "bytedance": "CN", "xiaomi": "CN", "meituan": "CN", "netease": "CN",
    "jd": "CN", "didi": "CN", "kuaishou": "CN", "pinduoduo": "CN", "aliyun": "CN",
    "yandex": "RU", "sberbank": "RU", "kaspersky": "RU", "jetbrains": None,
    "naver": "KR", "kakao": "KR", "samsung": "KR", "linecorp": "JP", "rakuten": "JP",
    "mercadolibre": "AR", "mercadolivre": "BR", "nubank": "BR", "itau": "BR",
    "flipkart": "IN", "infosys": "IN", "tcs": "IN", "wipro": "IN", "zoho": "IN",
}

# langdetect code -> (country, weight). Languages spoken in many countries
# (English, Spanish, Arabic) are left out on purpose.
LANG_COUNTRY = {
    "zh-cn": ("CN", 2.5), "zh-tw": ("TW", 1.5), "ko": ("KR", 2.5), "ja": ("JP", 2.5),
    "vi": ("VN", 2.5), "ru": ("RU", 1.5), "uk": ("UA", 2), "tr": ("TR", 2), "pl": ("PL", 2),
    "th": ("TH", 2), "id": ("ID", 1.5), "fa": ("IR", 2), "pt": ("BR", 1.5), "de": ("DE", 1.5),
    "fr": ("FR", 1), "it": ("IT", 2), "nl": ("NL", 2), "cs": ("CZ", 2), "sk": ("SK", 2),
    "ro": ("RO", 2), "hu": ("HU", 2), "el": ("GR", 2), "he": ("IL", 2), "bg": ("BG", 1.5),
    "sv": ("SE", 2), "da": ("DK", 2), "no": ("NO", 2), "fi": ("FI", 2), "lt": ("LT", 2),
    "lv": ("LV", 2), "et": ("EE", 2), "sl": ("SI", 2), "hr": ("HR", 1.5), "bn": ("BD", 1.5),
    "hi": ("IN", 2), "ta": ("IN", 2), "te": ("IN", 2), "mr": ("IN", 2),
}

# Country names that are also common words / first names -> not used from bios
AMBIGUOUS_NAMES = {"jordan", "chad", "georgia", "turkey", "guinea", "niger", "israel",
                   "jersey", "victoria", "china town"}

WEIGHTS = {"package": 3, "email_domain": 3, "email_provider": 3, "company": 2,
           "platform": 2.5, "website_domain": 2, "funding": 2, "mention": 1.5,
           "manifest_url": 2}


# ─────────────────────────────────────────────────────────────────────────────
# GitHub
# ─────────────────────────────────────────────────────────────────────────────

BLOB = "... on Blob { text }"

def owner_query(items):
    """items: list of (owner, repo_name)."""
    parts = []
    for i, (owner, repo) in enumerate(items):
        o, r = _safe_login(owner), _safe_login(repo)
        parts.append(f"""
        o{i}: repositoryOwner(login: "{o}") {{
          __typename
          ... on User {{
            email websiteUrl company bio twitterUsername
            socialAccounts(first: 10) {{ nodes {{ provider url }} }}
            followers(first: 100) {{ nodes {{ location }} }}
            following(first: 100) {{ nodes {{ location }} }}
          }}
          ... on Organization {{
            email websiteUrl description
            membersWithRole(first: 100) {{ nodes {{ location }} }}
          }}
        }}
        r{i}: repository(owner: "{o}", name: "{r}") {{
          description
          readme: object(expression: "HEAD:README.md") {{ {BLOB} }}
          pom: object(expression: "HEAD:pom.xml") {{ {BLOB} }}
          gradle: object(expression: "HEAD:build.gradle") {{ {BLOB} }}
          gradlekts: object(expression: "HEAD:build.gradle.kts") {{ {BLOB} }}
          funding: object(expression: "HEAD:.github/FUNDING.yml") {{ {BLOB} }}
          srcjava: object(expression: "HEAD:src/main/java") {{ ... on Tree {{ entries {{ name }} }} }}
          srckotlin: object(expression: "HEAD:src/main/kotlin") {{ ... on Tree {{ entries {{ name }} }} }}
          {MANIFEST_FIELDS}
          defaultBranchRef {{ target {{ ... on Commit {{
            history(first: 30) {{ nodes {{ message author {{ email user {{ login }} }} }} }}
          }} }} }}
        }}""")
    return "query { rateLimit { remaining resetAt } " + " ".join(parts) + " }"


MANIFEST_FIELDS = " ".join(f'{a}: object(expression: "HEAD:{f}") {{ {BLOB} }}' for a, f in MANIFESTS.items())


def _text(blob):
    return ((blob or {}).get("text") or "")[:TEXT_LIMIT]


def parse_owner(owner, node, repo):
    rec = {"login": owner, "found": node is not None}
    node = node or {}
    rec["type"] = node.get("__typename")
    rec["email"] = node.get("email")
    rec["website"] = node.get("websiteUrl")
    rec["company"] = node.get("company")
    rec["bio"] = node.get("bio") or node.get("description")
    rec["social"] = [a.get("url") for a in (node.get("socialAccounts") or {}).get("nodes") or []]
    people = []
    for key in ("followers", "following", "membersWithRole"):
        people += [(p or {}).get("location") for p in (node.get(key) or {}).get("nodes") or []]
    rec["network_locations"] = [l for l in people if l]
    repo = repo or {}
    rec["repo_description"] = repo.get("description")
    for key in ("readme", "pom", "gradle", "gradlekts", "funding"):
        rec[key] = _text(repo.get(key))
    rec["srcjava"] = [e["name"] for e in ((repo.get("srcjava") or {}).get("entries") or [])]
    rec["srckotlin"] = [e["name"] for e in ((repo.get("srckotlin") or {}).get("entries") or [])]
    rec["manifests"] = {f: _text(repo.get(a)) for a, f in MANIFESTS.items() if _text(repo.get(a))}
    hist = (((repo.get("defaultBranchRef") or {}).get("target") or {}).get("history") or {})
    commits = []
    for c in hist.get("nodes") or []:
        a = c.get("author") or {}
        commits.append({"message": (c.get("message") or "")[:500], "email": a.get("email"),
                        "login": ((a.get("user") or {}).get("login"))})
    rec["commits"] = commits
    return rec


def fetch_signals(owner_repos):
    """owner_repos: dict owner -> repo name (their most-starred repo in the list)."""
    cache = load_cache(CACHE_FILE)
    todo = [(o, r) for o, r in owner_repos.items() if o.lower() not in cache]
    print(f"Owner clues: {len(owner_repos) - len(todo)} cached, {len(todo)} to fetch")
    if not todo:
        return cache
    if not os.environ.get("GITHUB_TOKEN"):
        print(f"No GITHUB_TOKEN: skipping the {len(todo)} uncached owners, using the cache only.")
        return cache
    session = make_session()
    failed = 0

    def run(items):
        data = post_graphql(session, owner_query(items))
        if data is None:
            return [], list(items)
        payload = data.get("data") or {}
        not_found = {(e.get("path") or [None])[0] for e in data.get("errors") or []
                     if e.get("type") == "NOT_FOUND"}
        good, bad = [], []
        for i, (o, r) in enumerate(items):
            node = payload.get(f"o{i}")
            if node is None and f"o{i}" not in not_found:
                bad.append((o, r))        # timeout etc. -> retry
                continue
            good.append(parse_owner(o, node, payload.get(f"r{i}")))
        return good, bad

    for start in range(0, len(todo), BATCH_SIZE):
        batch = todo[start:start + BATCH_SIZE]
        records, bad = run(batch)
        for item in bad:                  # retry failed owners one at a time
            one, still = run([item])
            records += one
            failed += len(still)
        for rec in records:
            cache[rec["login"].lower()] = rec
        append_cache(CACHE_FILE, records)
        print(f"  {min(start + BATCH_SIZE, len(todo))}/{len(todo)}  (failed: {failed})",
              end="\r", flush=True)
    print()
    if failed:
        print(f"WARNING: {failed} owners failed. Rerun the same command to retry them.")
    return cache


def contributors_query(items):
    """items: list of (alias, owner, repo) - commit authors with their profile location."""
    parts = []
    for alias, owner, repo in items:
        parts.append(f"""
        {alias}: repository(owner: "{_safe_login(owner)}", name: "{_safe_login(repo)}") {{
          defaultBranchRef {{ target {{ ... on Commit {{
            history(first: {CONTRIB_COMMITS}) {{ nodes {{ author {{ user {{ login location }} }} }} }}
          }} }} }}
        }}""")
    return "query { rateLimit { remaining resetAt } " + " ".join(parts) + " }"


def _is_bot(login):
    low = login.lower()
    return low.endswith("[bot]") or low.endswith("-bot") or low in BOT_LOGINS


def fetch_contributors(owner_repo_lists):
    """owner_repo_lists: owner -> up to CONTRIB_REPOS repo names.
    Caches, per owner, the people (other than the owner and bots) who wrote
    the latest commits of those repos, with their profile location."""
    cache = load_cache(CONTRIB_CACHE)
    todo = [(o, rs) for o, rs in owner_repo_lists.items() if o.lower() not in cache]
    print(f"Contributors: {len(owner_repo_lists) - len(todo)} cached, {len(todo)} to fetch")
    if not todo:
        return cache
    if not os.environ.get("GITHUB_TOKEN"):
        print(f"No GITHUB_TOKEN: skipping the {len(todo)} uncached owners, using the cache only.")
        return cache
    session = make_session()
    failed = 0

    def run(owners):
        items = [(f"c{i}_{j}", o, r) for i, (o, rs) in enumerate(owners) for j, r in enumerate(rs)]
        data = post_graphql(session, contributors_query(items))
        if data is None:
            return [], list(owners)
        payload = data.get("data") or {}
        not_found = {(e.get("path") or [None])[0] for e in data.get("errors") or []
                     if e.get("type") == "NOT_FOUND"}
        good, bad = [], []
        for i, (o, rs) in enumerate(owners):
            people, ok = {}, True
            for j in range(len(rs)):
                alias = f"c{i}_{j}"
                node = payload.get(alias)
                if node is None:
                    ok = ok and alias in not_found   # missing repo is fine, a timeout isn't
                    continue
                hist = (((node.get("defaultBranchRef") or {}).get("target") or {})
                        .get("history") or {})
                for c in hist.get("nodes") or []:
                    u = ((c or {}).get("author") or {}).get("user") or {}
                    login = u.get("login")
                    if login and login.lower() != o.lower() and not _is_bot(login):
                        people[login] = u.get("location")
            if ok:
                good.append({"login": o, "contributors": people})
            else:
                bad.append((o, rs))
        return good, bad

    for start in range(0, len(todo), CONTRIB_BATCH):
        batch = todo[start:start + CONTRIB_BATCH]
        records, bad = run(batch)
        for item in bad:                  # retry failed owners one at a time
            one, still = run([item])
            records += one
            failed += len(still)
        for rec in records:
            cache[rec["login"].lower()] = rec
        append_cache(CONTRIB_CACHE, records)
        print(f"  {min(start + CONTRIB_BATCH, len(todo))}/{len(todo)}  (failed: {failed})",
              end="\r", flush=True)
    print()
    if failed:
        print(f"WARNING: {failed} owners failed. Rerun the same command to retry them.")
    return cache


# ─────────────────────────────────────────────────────────────────────────────
# Clues -> votes
# ─────────────────────────────────────────────────────────────────────────────

class Inferer:
    def __init__(self):
        self.geo = Geo()
        self.cctld = {}
        for cc, c in self.geo.countries.items():
            tld = (c.get("tld") or "").lstrip(".").lower()
            if tld and tld not in GENERIC_CCTLDS:
                self.cctld[tld] = cc
        self.cctld.update(TLD_FIX)
        self.country_words = sorted(
            (n for n in self.geo.long_country_names if n not in AMBIGUOUS_NAMES),
            key=len, reverse=True)

    # -- helpers -------------------------------------------------------------
    def domain_country(self, domain):
        """'mail.example.com.br' -> 'BR' (country-code domain), or None."""
        last = domain.lower().rstrip(".").rsplit(".", 1)[-1]
        return self.cctld.get(last)

    @staticmethod
    def host_of(url):
        m = re.search(r"(?:https?://)?(?:www\.)?([a-z0-9.-]+\.[a-z]{2,})", (url or "").lower())
        return m.group(1) if m else None

    def match_platform(self, host):
        for dom, cc in PLATFORMS.items():
            if cc and (host == dom or host.endswith("." + dom)):
                return cc
        return None

    def mentioned_country(self, text):
        low = (text or "").lower()
        for n in self.country_words:
            if re.search(r"(?<![a-z])" + re.escape(n) + r"(?![a-z])", low):
                return self.geo.country_by_name[n]
        for n, cc in REGION_ALIASES.items():
            if " " in n and n in low:     # multi-word regions only ("tamil nadu")
                return cc
        return None

    # -- the clues -----------------------------------------------------------
    def package_votes(self, rec, votes):
        ids = []
        pom = re.sub(r"<parent>.*?</parent>", "", rec.get("pom") or "", flags=re.S)
        ids += re.findall(r"<groupId>\s*([\w.\-]+)\s*</groupId>", pom)[:1]
        for g in ("gradle", "gradlekts"):
            ids += re.findall(r"""\bgroup\s*=?\s*['"]([\w.\-]+)['"]""", rec.get(g) or "")[:1]
        ids += [d for d in (rec.get("srcjava") or []) + (rec.get("srckotlin") or [])
                if re.fullmatch(r"[a-z]{2}", d)]
        for gid in ids:
            seg = gid.lower().split(".")
            if seg[0] in self.cctld:
                votes.append((self.cctld[seg[0]], WEIGHTS["package"], f"package:{gid}"))
            elif len(seg) > 1 and seg[1] in COMPANIES and COMPANIES[seg[1]]:
                votes.append((COMPANIES[seg[1]], WEIGHTS["package"], f"package:{gid}"))

    def email_votes(self, rec, votes):
        emails = set()
        if rec.get("email"):
            emails.add(rec["email"].lower())
        owner = rec["login"].lower()
        for c in rec.get("commits") or []:
            e = (c.get("email") or "").lower()
            # users: only the owner's own commits; organizations: anyone's
            if e and (rec.get("type") == "Organization" or (c.get("login") or "").lower() == owner):
                emails.add(e)
        for text in self.manifest_texts(rec):
            for e in re.findall(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", text):
                if not IGNORED_EMAIL.search(e):
                    emails.add(e.lower().rstrip("."))
        for e in sorted(emails):                 # fixed order -> identical output on every run
            if "@" not in e or e.endswith("users.noreply.github.com"):
                continue
            dom = e.split("@", 1)[1]
            if dom in EMAIL_PROVIDERS:
                votes.append((EMAIL_PROVIDERS[dom], WEIGHTS["email_provider"], f"email:{dom}"))
            elif self.domain_country(dom):
                votes.append((self.domain_country(dom), WEIGHTS["email_domain"], f"email:{dom}"))
            else:
                name = dom.split(".")[0]
                if COMPANIES.get(name):
                    votes.append((COMPANIES[name], WEIGHTS["company"], f"email:{dom}"))

    def language_votes(self, rec, votes):
        parts = [rec.get("readme"), rec.get("bio"), rec.get("repo_description")]
        parts += [c.get("message") for c in rec.get("commits") or []]
        text = "\n".join(p for p in parts if p)
        text = re.sub(r"```.*?```", " ", text, flags=re.S)        # code blocks
        text = re.sub(r"<[^>]+>|https?://\S+|\[[^\]]*\]\([^)]*\)", " ", text)
        text = re.sub(r"[`*#>|_\-=]+", " ", text)
        # Chinese / Japanese / Korean: decided by the writing system. langdetect
        # mislabels Chinese mixed with English/code words (often as Norwegian).
        kana = len(re.findall(r"[぀-ヿ]", text))
        hangul = len(re.findall(r"[가-힯]", text))
        han = len(re.findall(r"[㐀-鿿]", text))
        if kana >= 10:
            lang = "ja"
        elif hangul >= 10:
            lang = "ko"
        elif han >= 15:
            lang = "zh-cn"
        else:
            lang = None
        if lang:
            cc, w = LANG_COUNTRY[lang]
            votes.append((cc, w, f"language:{lang}"))
            return
        text = re.sub(r"[぀-ヿ㐀-鿿가-힯]", " ", text)
        if len(re.findall(r"\w", text)) < 40:
            return
        try:
            langs = detect_langs(text)
        except LangDetectException:
            return
        top = langs[0]
        if top.lang in LANG_COUNTRY and top.prob >= 0.6:
            cc, w = LANG_COUNTRY[top.lang]
            votes.append((cc, w, f"language:{top.lang}"))

    def network_votes(self, rec, votes):
        countries = [self.geo.country_of(l)[0] for l in rec.get("network_locations") or []]
        countries = [c for c in countries if c]
        if len(countries) < 3:
            return
        cc, n = Counter(countries).most_common(1)[0]
        share = n / len(countries)
        if share >= 0.6 and len(countries) >= 5:
            votes.append((cc, 3, f"network:{n}/{len(countries)}"))
        elif share >= 0.5:
            votes.append((cc, 2, f"network:{n}/{len(countries)}"))

    def contributor_votes(self, rec, votes):
        """Where the other people committing to the owner's repos are located."""
        countries = [self.geo.country_of(l)[0] for l in (rec.get("contributors") or {}).values()]
        countries = [c for c in countries if c]
        if not countries:
            return
        cc, n = Counter(countries).most_common(1)[0]
        share = n / len(countries)
        if n >= 3 and share >= 0.6:
            votes.append((cc, 3, f"contributors:{n}/{len(countries)}"))
        elif n >= 2 and share >= 0.5:
            votes.append((cc, 2, f"contributors:{n}/{len(countries)}"))
        elif len(countries) == 1:
            votes.append((cc, 1.5, "contributors:1/1"))

    def web_votes(self, rec, votes):
        urls = [rec.get("website")] + list(rec.get("social") or [])
        urls += re.findall(r"https?://[^\s)\"'>]+", (rec.get("bio") or ""))
        seen = set()
        for u in urls:
            host = self.host_of(u)
            if not host or host in seen or "github" in host:
                continue
            seen.add(host)
            cc = self.match_platform(host)
            if cc:
                votes.append((cc, WEIGHTS["platform"], f"site:{host}"))
            elif self.domain_country(host):
                votes.append((self.domain_country(host), WEIGHTS["website_domain"], f"site:{host}"))

    @staticmethod
    def manifest_texts(rec):
        """Manifest files of any ecosystem, plus Maven/Gradle build files."""
        texts = list((rec.get("manifests") or {}).values())
        texts += [rec.get(k) or "" for k in ("pom", "gradle", "gradlekts")]
        return [t for t in texts if t]

    def manifest_url_votes(self, rec, votes):
        # a domain that already voted (as an email or the profile website) must not vote twice
        voted = {why.split(":", 1)[1] for _, _, why in votes if why.startswith(("email:", "site:"))}
        seen = {h for h in voted}
        manifests = list((rec.get("manifests") or {}).values())
        build_files = [rec.get(k) or "" for k in ("pom", "gradle", "gradlekts")]
        # Maven/Gradle files list other people's library repositories (maven.someone.de), which say
        # nothing about the owner: there, only country-only mirrors (maven.aliyun.com) count.
        for text, mirrors_only in [(t, False) for t in manifests] + [(t, True) for t in build_files]:
            for u in re.findall(r"https?://[^\s\"'<>)\]]+", text):
                host = self.host_of(u)
                if (not host or host in seen or "github" in host
                        or any(host.endswith("." + d) for d in voted)):
                    continue
                seen.add(host)
                cc = self.match_platform(host)
                if cc:
                    votes.append((cc, WEIGHTS["platform"], f"manifest_site:{host}"))
                elif not mirrors_only and self.domain_country(host):
                    votes.append((self.domain_country(host), WEIGHTS["manifest_url"], f"manifest_site:{host}"))
        # go.mod module path is a domain without scheme ("module gitee.com/x/y")
        gomod = (rec.get("manifests") or {}).get("go.mod", "")
        m = re.search(r"^module\s+([\w.-]+\.[a-z]{2,})/", gomod, re.M)
        if m and m.group(1) not in seen and "github" not in m.group(1):
            host = m.group(1).lower()
            cc = self.match_platform(host) or self.domain_country(host)
            if cc:
                votes.append((cc, WEIGHTS["manifest_url"], f"manifest_site:{host}"))

    def funding_votes(self, rec, votes):
        text = ((rec.get("funding") or "") + "\n" + (rec.get("readme") or "")).lower()
        if re.search(r"afdian|alipay|支付宝|微信支付|wechat pay|wechatpay|赞赏码", text):
            votes.append(("CN", WEIGHTS["funding"], "funding:china"))
        if re.search(r"chave pix|\bpix\b.*(chave|doa)", text):
            votes.append(("BR", WEIGHTS["funding"], "funding:pix"))

    def company_votes(self, rec, votes):
        comp = (rec.get("company") or "").lower()
        for name, cc in COMPANIES.items():
            if cc and re.search(r"(?<![a-z])" + re.escape(name) + r"(?![a-z])", comp):
                votes.append((cc, WEIGHTS["company"], f"company:{name}"))
                break
        for field in ("company", "bio"):
            cc = self.mentioned_country(rec.get(field))
            if cc:
                votes.append((cc, WEIGHTS["mention"], f"{field}_mentions:{cc}"))

    # -- combine -------------------------------------------------------------
    def infer(self, rec):
        votes = []
        for f in (self.package_votes, self.email_votes, self.language_votes,
                  self.network_votes, self.contributor_votes, self.web_votes,
                  self.manifest_url_votes, self.funding_votes, self.company_votes):
            f(rec, votes)
        votes = [v for v in votes if v[0]]
        if not votes:
            return None, "none", 0.0, ""
        score = defaultdict(float)
        for cc, w, _ in votes:
            score[cc] += w
        ranked = sorted(score.items(), key=lambda kv: kv[1], reverse=True)
        top_cc, top = ranked[0]
        second = ranked[1][1] if len(ranked) > 1 else 0.0
        if top >= 4 and top >= 2 * second:
            conf = "high"
        elif top >= 2 and top >= 1.5 * second:
            conf = "medium"
        else:
            conf = "low"
        # Contributors alone were right only ~68% of the time on known owners,
        # so a guess resting only on them is never more than "low".
        if all(why.startswith("contributors:") for _, _, why in votes):
            conf = "low"
        evidence = "; ".join(f"{cc}<-{why}" for cc, _, why in votes)
        return top_cc, conf, round(top, 1), evidence


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    import argparse
    ap = argparse.ArgumentParser(description="Infer the country of repo owners without a location.")
    ap.add_argument("--input", default="java_repos_final_5290.csv",
                    help="CSV with a 'repo' column (owner/name) and a 'stars' column")
    ap.add_argument("--known", default="owner_locations.csv",
                    help="output of owner_locations.py (known countries, used for the accuracy check)")
    args = ap.parse_args()
    repos = read_repo_list(args.input)
    repos["owner"] = repos["repo"].str.split("/").str[0]
    if "stars" in repos:
        repos = repos.sort_values("stars", ascending=False)
    top_repo = {}                                    # owner -> most-starred repo
    repo_lists = {}                                  # owner -> top CONTRIB_REPOS repos
    for full in repos["repo"]:
        o, r = full.split("/", 1)
        top_repo.setdefault(o.lower(), (o, r))
        lst = repo_lists.setdefault(o.lower(), [])
        if len(lst) < CONTRIB_REPOS:
            lst.append(r)
    owner_repos = {o: r for o, r in top_repo.values()}
    owner_repo_lists = {o: repo_lists[o.lower()] for o in owner_repos}

    known = pd.read_csv(args.known)                 # from owner_locations.py
    known_cc = {o.lower(): cc for o, cc in zip(known["owner"], known["country_code"])
                if isinstance(cc, str)}

    cache = fetch_signals(owner_repos)
    contrib = fetch_contributors(owner_repo_lists)
    inf = Inferer()
    rows = []
    for o in owner_repos:
        rec = cache.get(o.lower())
        if not rec:
            continue
        rec = dict(rec, contributors=(contrib.get(o.lower()) or {}).get("contributors"))
        cc, conf, score, evidence = inf.infer(rec)
        rows.append({"owner": o, "type": rec.get("type"),
                     "known_country": known_cc.get(o.lower()),
                     "inferred_country": cc, "confidence": conf, "score": score,
                     "evidence": evidence})
    df = pd.DataFrame(rows)
    df.to_csv("owner_country_inferred.csv", index=False, encoding="utf-8-sig")

    # Accuracy on owners whose country is known
    val = df[df["known_country"].notna()].copy()
    val["correct"] = val["inferred_country"] == val["known_country"]
    tiers = ["high", "medium", "low", "none"]
    vt = (val.groupby("confidence")
          .agg(owners=("owner", "size"), correct=("correct", "sum"))
          .reindex(tiers).fillna(0).astype(int))
    vt["accuracy_%"] = (vt["correct"] / vt["owners"].replace(0, pd.NA) * 100).round(1)
    vt["share_of_known_%"] = (vt["owners"] / len(val) * 100).round(1)
    vt.to_csv("inference_validation.csv", encoding="utf-8-sig")
    print(f"\n── Accuracy check on {len(val)} owners whose country is known")
    print(vt.to_string())
    wrong = val[~val["correct"] & val["confidence"].isin(["high", "medium"])]
    if len(wrong):
        print("\nMost common mistakes (known -> guessed), high/medium only:")
        print((wrong["known_country"] + " -> " + wrong["inferred_country"])
              .value_counts().head(10).to_string())

    # Guesses for owners WITHOUT a known country
    unk = df[df["known_country"].isna()]
    print(f"\n── Owners without a location: {len(unk)}")
    print(unk["confidence"].value_counts().reindex(tiers).fillna(0).astype(int).to_string())

    # Final table: known + confident guesses
    use = unk[unk["confidence"].isin(["high", "medium"])]
    final = pd.DataFrame({
        "known": df["known_country"].value_counts(),
        "inferred_high": use[use["confidence"] == "high"]["inferred_country"].value_counts(),
        "inferred_medium": use[use["confidence"] == "medium"]["inferred_country"].value_counts(),
    }).fillna(0).astype(int)
    final["total"] = final.sum(axis=1)
    final.index = [inf.geo.describe(cc)[0] for cc in final.index]
    final = final.sort_values("total", ascending=False)
    final.to_csv("owners_by_country_final.csv", encoding="utf-8-sig")
    print("\n── Owners per country (known + high/medium guesses), top 20")
    print(final.head(20).to_string())
    print("\nSaved owner_country_inferred.csv, inference_validation.csv, "
          "owners_by_country_final.csv")


if __name__ == "__main__":
    main()
