"""
owner_locations.py
==================
For the repos in java_repos_final_5290.csv: how many owners have a location
set on GitHub, and which country / continent they are in.

How it works:
  1. Fetches the location field of every repo owner (GraphQL, 50 per request).
  2. Maps the free-text location to a country, offline:
       - country names and common aliases ("USA", "UK", "Deutschland", "中国")
       - US states, and big states/provinces of other countries
       - city names (34k cities > 15,000 people; the biggest one wins, so
         "Cairo" -> Egypt, "Alexandria" -> Egypt, "London" -> UK)
     Locations it can't place (e.g. "Earth", "Remote") count as unrecognized.

Outputs:
  owner_locations.csv       one row per owner: location, country, continent
  owners_by_country.csv     owners and repos per country
  owners_by_continent.csv   owners and repos per continent

Usage:
  pip install geonamescache
  $env:GITHUB_TOKEN = "ghp_xxx"
  py owner_locations.py
"""

import argparse
import re
import unicodedata

import geonamescache
import pandas as pd

from classify_egypt_accounts import (
    make_session, post_graphql, load_cache, append_cache, _safe_login, JUNK_LOCATIONS,
    location_status,
)

CACHE_FILE = "cache_owner_locations.jsonl"
BATCH_SIZE = 50
MIN_CITY_POP_ALIASES = 300_000    # use other-language city names only for big cities

CONTINENTS = {"AF": "Africa", "AS": "Asia", "EU": "Europe", "NA": "North America",
              "OC": "Oceania", "SA": "South America", "AN": "Antarctica"}

# Extra names people write for countries (lowercase).
COUNTRY_ALIASES = {
    "usa": "US", "us": "US", "u.s.": "US", "u.s.a.": "US", "u.s.a": "US", "america": "US",
    "united states of america": "US", "the united states": "US",
    "uk": "GB", "u.k.": "GB", "england": "GB", "scotland": "GB", "wales": "GB",
    "great britain": "GB", "britain": "GB", "northern ireland": "GB",
    "deutschland": "DE", "allemagne": "DE", "españa": "ES", "espana": "ES", "italia": "IT",
    "brasil": "BR", "méxico": "MX", "türkiye": "TR", "turkiye": "TR", "turkey": "TR",
    "russia": "RU", "россия": "RU", "south korea": "KR", "korea": "KR", "republic of korea": "KR",
    "대한민국": "KR", "한국": "KR", "north korea": "KP", "vietnam": "VN", "viet nam": "VN",
    "việt nam": "VN", "czech republic": "CZ", "czechia": "CZ", "holland": "NL",
    "the netherlands": "NL", "nederland": "NL", "schweiz": "CH", "suisse": "CH",
    "österreich": "AT", "polska": "PL", "uae": "AE", "u.a.e": "AE", "emirates": "AE",
    "ksa": "SA", "saudi": "SA", "hong kong sar": "HK", "macau": "MO", "iran": "IR",
    "syria": "SY", "palestine": "PS", "ivory coast": "CI", "drc": "CD",
    "中国": "CN", "中國": "CN", "china mainland": "CN", "mainland china": "CN", "prc": "CN",
    "日本": "JP", "台湾": "TW", "台灣": "TW", "香港": "HK", "新加坡": "SG",
    "india": "IN", "bharat": "IN", "भारत": "IN", "مصر": "EG", "egypt": "EG", "misr": "EG",
    "السعودية": "SA", "الامارات": "AE", "الإمارات": "AE", "المغرب": "MA", "الأردن": "JO",
    "україна": "UA", "беларусь": "BY", "қазақстан": "KZ", "ไทย": "TH", "indonesia": "ID",
    "philippines": "PH", "the philippines": "PH", "bangladesh": "BD", "pakistan": "PK",
    "maroc": "MA", "algérie": "DZ", "algerie": "DZ", "tunisie": "TN", "égypte": "EG",
    "egypte": "EG", "saudiarabia": "SA", "ny state": "US", "new york state": "US",
    "netherlands": "NL", "russian federation": "RU", "perú": "PE", "cn": "CN",
    "cheng du": "CN", "korea, republic of": "KR",
    # nationality words people write as their location
    "russian": "RU", "chinese": "CN", "chinese mainland": "CN", "japanese": "JP",
    "korean": "KR", "vietnamese": "VN", "brazilian": "BR", "indian": "IN", "german": "DE",
    "french": "FR", "italian": "IT", "spanish": "ES", "turkish": "TR", "polish": "PL",
    "ukrainian": "UA", "egyptian": "EG", "american": "US", "british": "GB", "canadian": "CA",
}

# A continent alone doesn't say which country -> not placed.
CONTINENT_ONLY = {"north america", "south america", "latin america", "central america",
                  "europe", "asia", "africa", "middle east", "oceania", "mena", "emea",
                  "apac", "southeast asia", "south asia", "east asia", "scandinavia", "nordics",
                  "antarctica"}   # nobody really lives there; it's a joke location

# States / provinces / regions people often write without the country.
REGION_ALIASES = {
    # US states
    **{s: "US" for s in [
        "alabama", "alaska", "arizona", "arkansas", "california", "colorado", "connecticut",
        "delaware", "florida", "hawaii", "idaho", "illinois", "indiana", "iowa", "kansas",
        "kentucky", "louisiana", "maine", "maryland", "massachusetts", "michigan",
        "minnesota", "mississippi", "missouri", "montana", "nebraska", "nevada",
        "new hampshire", "new jersey", "new mexico", "north carolina", "north dakota", "ohio",
        "oklahoma", "oregon", "pennsylvania", "rhode island", "south carolina",
        "south dakota", "tennessee", "texas", "utah", "vermont", "virginia", "washington",
        "west virginia", "wisconsin", "wyoming", "bay area", "sf bay area", "silicon valley",
        "nyc", "new york city", "sf", "dc", "washington dc", "washington d.c."]},
    # China
    **{s: "CN" for s in [
        "guangdong", "zhejiang", "jiangsu", "sichuan", "hubei", "hunan", "shandong", "fujian",
        "henan", "hebei", "anhui", "shaanxi", "shanxi", "jiangxi", "yunnan", "guangxi",
        "liaoning", "jilin", "heilongjiang", "guizhou", "hainan", "gansu", "inner mongolia",
        "xinjiang", "广东", "浙江", "江苏", "四川", "湖北", "湖南", "山东", "福建", "河南",
        "河北", "安徽", "陕西", "江西", "云南", "广西", "辽宁", "重庆", "天津"]},
    # India
    **{s: "IN" for s in [
        "karnataka", "maharashtra", "telangana", "tamil nadu", "tamilnadu", "kerala", "gujarat",
        "uttar pradesh", "west bengal", "andhra pradesh", "rajasthan", "haryana", "odisha",
        "madhya pradesh", "bihar", "jharkhand", "uttarakhand", "assam", "goa", "ncr",
        "delhi ncr", "new delhi"]},
    # Canada
    **{s: "CA" for s in ["ontario", "quebec", "québec", "british columbia", "alberta",
                         "manitoba", "nova scotia", "saskatchewan", "new brunswick"]},
    # Others
    "bavaria": "DE", "bayern": "DE", "nrw": "DE", "baden-württemberg": "DE",
    "new south wales": "AU", "nsw": "AU", "victoria, australia": "AU", "queensland": "AU",
    "catalonia": "ES", "catalunya": "ES", "andalusia": "ES", "lombardy": "IT",
    "île-de-france": "FR", "ile-de-france": "FR", "punjab, pakistan": "PK", "sindh": "PK",
    "west java": "ID", "jawa barat": "ID", "east java": "ID", "jawa timur": "ID",
}

US_STATE_CODES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA",
    "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT",
    "VA", "WA", "WV", "WI", "WY", "DC",
}


# ─────────────────────────────────────────────────────────────────────────────
# Location -> country
# ─────────────────────────────────────────────────────────────────────────────

def _fold(s):
    """'timișoara' -> 'timisoara' (accents ignored)."""
    return "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))


def _has_cjk_or_other_script(s):
    return re.search(r"[^\x00-ɏ]", s) is not None


class Geo:
    def __init__(self):
        gc = geonamescache.GeonamesCache()
        self.countries = gc.get_countries()
        self.country_by_name = {c["name"].lower(): cc for cc, c in self.countries.items()}
        self.country_by_name.update(COUNTRY_ALIASES)
        # name -> (countrycode, population), biggest wins. Real names are kept
        # apart from alternative names, so a real name always wins ("Islamabad"
        # is also an old name of Chittagong, which is bigger).
        self.cities = {}
        self.city_alt = {}
        self.us_cities = set()      # for "Alexandria, VA" -> US, not Egypt
        self.script_names = {}      # non-latin names, matched as substrings

        def keep(table, name, c):
            for n in {name, _fold(name)}:
                if n not in table or table[n][1] < c["population"]:
                    table[n] = (c["countrycode"], c["population"])

        for c in gc.get_cities().values():
            if c["countrycode"] == "US":
                self.us_cities.add(c["name"].lower())
                self.us_cities.add(_fold(c["name"].lower()))
            keep(self.cities, c["name"].lower(), c)
            if c["population"] >= MIN_CITY_POP_ALIASES:
                for a in c.get("alternatenames") or []:
                    # 2-letter Latin nicknames ("Pa") mislead; 2-character Chinese names (北京) don't
                    if len(a) >= 3 or (len(a) == 2 and _has_cjk_or_other_script(a)):
                        keep(self.city_alt, a.lower(), c)
        for name, cc in list(self.country_by_name.items()) + list(REGION_ALIASES.items()):
            if _has_cjk_or_other_script(name):
                self.script_names[name] = (cc, 10**9)
        for name, (cc, pop) in list(self.cities.items()) + list(self.city_alt.items()):
            if _has_cjk_or_other_script(name) and len(name) >= 2:
                if name not in self.script_names or self.script_names[name][1] < pop:
                    self.script_names[name] = (cc, pop)
        # long country names first, so "south korea" wins over "korea"
        self.long_country_names = sorted(
            (n for n in self.country_by_name if len(n) >= 4 and not _has_cjk_or_other_script(n)),
            key=len, reverse=True)

    def city(self, name):
        """(countrycode, population) for a city name, or None. Parts of one or
        two letters are never cities ("PA" is also a nickname of a Chinese city)."""
        if len(name) <= 2:
            return None
        for table in (self.cities, self.city_alt):
            for n in (name, _fold(name)):
                if n in table:
                    return table[n]
        return None

    def country_of(self, location):
        """Returns (country_code, how_matched) or (None, reason)."""
        if not isinstance(location, str) or not location.strip():
            return None, "empty"
        raw = location.strip()
        low = raw.lower()
        if low in JUNK_LOCATIONS:
            return None, "junk"
        if low.strip(" .") in CONTINENT_ONLY:
            return None, "continent_only"
        if location_status(raw) == "egypt":               # small Egyptian towns too
            return "EG", "egypt_places"
        raw_parts = [p.strip() for p in re.split(r"[,/|;·•()\n]| - | – ", raw) if p.strip()]
        parts = [p.lower().strip(" .") for p in raw_parts]

        for p in reversed(parts):                         # 1. a part is a country
            if p in self.country_by_name:
                return self.country_by_name[p], "country"
        for p in reversed(parts):                         # 2. a part is a state/province
            if p in REGION_ALIASES:
                return REGION_ALIASES[p], "region"
        if low in REGION_ALIASES:
            return REGION_ALIASES[low], "region"
        has_state_code = any(p.strip(" .") in US_STATE_CODES for p in raw_parts[1:])
        if has_state_code and any(p in self.us_cities or _fold(p) in self.us_cities for p in parts):
            return "US", "us_city_state"                  # 3a. "Alexandria, VA"
        best = None                                       # 3b. a part is a city
        for p in parts:
            hit = self.city(p)
            if hit and (best is None or hit[1] > best[1]):
                best = hit
        if best:
            return best[0], "city"
        if has_state_code:                                # 4. "Smallville, TX"
            return "US", "us_state_code"
        for n in self.long_country_names:                 # 5. country name inside text
            if re.search(r"(?<![a-z])" + re.escape(n) + r"(?![a-z])", low):
                return self.country_by_name[n], "country_in_text"
        hits = [(n, v) for n, v in self.script_names.items() if n in low]
        if hits:                                          # 6. 北京, 東京都, ...
            return max(hits, key=lambda h: (len(h[0]), h[1][1]))[1][0], "script_name"
        tokens = raw.replace(".", " ").split()            # 7. no commas: "Omaha NE"
        if len(tokens) >= 2 and tokens[-1] in US_STATE_CODES:
            city = " ".join(tokens[:-1]).lower()
            if city in self.us_cities or _fold(city) in self.us_cities:
                return "US", "us_city_state"
        words = re.findall(r"[a-zà-ÿ]+", low)              # 8. place inside text
        grams = [" ".join(words[i:i + 2]) for i in range(len(words) - 1)] + words
        for w in grams:
            if w in REGION_ALIASES:
                return REGION_ALIASES[w], "region_in_text"
        for w in grams:
            hit = self.city(w)
            if hit and hit[1] >= 100_000:
                return hit[0], "city_in_text"
        return None, "unrecognized"

    def describe(self, cc):
        c = self.countries.get(cc)
        if not c:
            return cc, "Unknown"
        return c["name"], CONTINENTS.get(c["continentcode"], c["continentcode"])


REPO_COLUMNS = ["repo", "name", "full_name", "project_name", "repo_name", "github_url", "url"]


def read_repo_list(path):
    """Reads a repo list CSV whatever the column is called (repo, name, full_name,
    project_name, github_url, url) and whatever the format ("owner/name" or a full
    GitHub link). Returns a DataFrame with a clean "repo" column (owner/name)."""
    df = pd.read_csv(path)
    col = next((c for c in REPO_COLUMNS if c in df.columns), None)
    if col is None:
        raise SystemExit(f"ERROR: {path} needs one of these columns: {', '.join(REPO_COLUMNS)} "
                         f"(found: {', '.join(df.columns)})")
    repo = (df[col].astype(str).str.strip()
            .str.replace(r"^(https?://)?(www\.)?github\.com/", "", regex=True)
            .str.replace(r"\.git$", "", regex=True).str.strip("/"))
    df = df.drop(columns=["repo"], errors="ignore")
    df.insert(0, "repo", repo)
    df = df[df.repo.str.count("/") == 1].drop_duplicates("repo")
    print(f"Read {len(df)} repos from {path} (column '{col}')")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# GitHub
# ─────────────────────────────────────────────────────────────────────────────

def owners_query(logins):
    parts = []
    for i, login in enumerate(logins):
        parts.append(f"""
        a{i}: repositoryOwner(login: "{_safe_login(login)}") {{
          login
          __typename
          ... on User {{ location }}
          ... on Organization {{ location }}
        }}""")
    return "query { rateLimit { remaining resetAt } " + " ".join(parts) + " }"


def fetch_owners(session, logins):
    cache = load_cache(CACHE_FILE)
    todo = [l for l in logins if l.lower() not in cache]
    print(f"Owner profiles: {len(logins) - len(todo)} cached, {len(todo)} to fetch")
    if todo and session is None:
        session = make_session()
    for start in range(0, len(todo), BATCH_SIZE):
        batch = todo[start:start + BATCH_SIZE]
        data = post_graphql(session, owners_query(batch))
        if data is None:
            continue                      # failed batch: retried on next run
        payload = data.get("data") or {}
        records = []
        for i, login in enumerate(batch):
            node = payload.get(f"a{i}")
            rec = {"login": login, "found": node is not None,
                   "type": (node or {}).get("__typename"),
                   "location": (node or {}).get("location")}
            records.append(rec)
            cache[login.lower()] = rec
        append_cache(CACHE_FILE, records)
        print(f"  {min(start + BATCH_SIZE, len(todo))}/{len(todo)}", end="\r", flush=True)
    print()
    return cache


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="java_repos_final_5290.csv")
    args = ap.parse_args()

    repos = read_repo_list(args.input)
    repos["owner"] = repos["repo"].str.split("/").str[0]
    repo_count = repos.groupby(repos["owner"].str.lower()).size()
    owners = list({o.lower(): o for o in repos["owner"]}.values())   # one per owner
    print(f"{len(repos)} repos, {len(owners)} different owners")

    cache = fetch_owners(None, owners)    # needs GITHUB_TOKEN only if something isn't cached

    geo = Geo()
    rows = []
    for o in owners:
        rec = cache.get(o.lower(), {})
        cc, how = geo.country_of(rec.get("location"))
        country, continent = geo.describe(cc) if cc else (None, None)
        rows.append({
            "owner": o, "type": rec.get("type"), "found": rec.get("found"),
            "location": rec.get("location"), "country_code": cc, "country": country,
            "continent": continent, "matched_by": how, "repos": int(repo_count[o.lower()]),
        })
    df = pd.DataFrame(rows)
    df.to_csv("owner_locations.csv", index=False, encoding="utf-8-sig")

    has_loc = df["matched_by"].ne("empty") & df["found"].fillna(False)
    placed = df["country"].notna()
    print(f"\nOwners: {len(df)}")
    print(f"  with a location set:   {has_loc.sum()} ({has_loc.mean():.1%})")
    print(f"  placed in a country:   {placed.sum()} ({placed.mean():.1%})")
    print(f"  location not placeable (e.g. 'Earth', 'Remote'): {(has_loc & ~placed).sum()}")
    print(f"  no location / account gone: {(~has_loc).sum()}")

    for col, out in [("country", "owners_by_country.csv"), ("continent", "owners_by_continent.csv")]:
        t = (df[placed].groupby(col)
             .agg(owners=("owner", "size"), repos=("repos", "sum"))
             .sort_values("owners", ascending=False))
        t["percent_of_placed_owners"] = (t["owners"] / placed.sum() * 100).round(1)
        t.to_csv(out, encoding="utf-8-sig")
        print(f"\nBy {col}:")
        print(t.head(25).to_string())
    print("\nSaved owner_locations.csv, owners_by_country.csv, owners_by_continent.csv")


if __name__ == "__main__":
    main()
