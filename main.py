import os
import time
import aiohttp
import asyncio
from bs4 import BeautifulSoup

from typing import List, Dict
import pandas as pd
import unicodedata

import urllib.parse as uparse
import datetime as dt
from zoneinfo import ZoneInfo
import dateparser, pytz

from thefuzz import fuzz, process
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed


os.environ["TZ"] = "Asia/Ho_Chi_Minh"
time.tzset()
utc = ZoneInfo("UTC")

import json

async def make_soup(url, timeout=90):
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/47.0.2526.106 Safari/537.36"
    }
    timeout = aiohttp.ClientTimeout(total=timeout)
    async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
        async with session.get(url) as response:
            soup = BeautifulSoup(await response.text(), "html.parser")

    return soup


@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
async def make_json(url, timeout=90):
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/47.0.2526.106 Safari/537.36"
    }
    timeout = aiohttp.ClientTimeout(total=timeout)
    async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
        async with session.get(url) as response:
            resp = await response.json()

    return resp


@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
async def make_json_new(url, timeout=90):
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/47.0.2526.106 Safari/537.36"
    }
    timeout = aiohttp.ClientTimeout(total=timeout)
    async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
        async with session.get(url) as response:
            resp = await response.text()

    return resp


async def store_leagues_links(
    standings_url: str = "https://bongda24h.vn/bong-da-anh/bang-xep-hang-1.html",
):
    standings = await make_soup(standings_url)
    leagues_link = [
        uparse.urljoin(standings_url, link.get("href"))
        for link in standings.select("div.nav-score a")
    ]
    pd.DataFrame(leagues_link, columns=["leagues_link"]).to_csv(
        "data/league_links.csv", index=False, mode="a"
    )

    pd.read_csv("data/league_links.csv").drop_duplicates(
        subset=["leagues_link"]
    ).to_csv("data/league_links.csv", index=False, mode="w")


async def store_club_details(
    leagues_link: List[str],
    base_url: str = "https://bongda24h.vn/",
    countries_url: str = "https://bongda24h.vn/bang-xep-hang-fifa-nam.html",
):
    for i, link in enumerate(leagues_link):
        if "://" not in link:
            continue
        lg_tbl = await make_soup(link)

        clubs = lg_tbl.select("a.link-clb")

        if not clubs:
            continue

        club_name_img = [
            (
                club.select(":scope>img")[0].get("alt"),
                club.select(":scope>img")[0].get("src"),
                uparse.urljoin(base_url, club.get("href")),
            )
            for club in clubs
        ]

        df = pd.DataFrame(
            club_name_img, columns=["club_name", "club_logo", "club_link"]
        )
        df["league"] = lg_tbl.select("div.nav-score a.active")[0].text.strip()
        df.to_csv("data/club_details.csv", index=False, mode="a")

        print(i, link)
        time.sleep(10)

    countries = (await make_soup(countries_url)).select(
        "section.section.calc div.fifa-text>a"
    )

    cnt_name_img = [
        (
            country.text.strip(),
            None,
            uparse.urljoin(base_url, country.get("href")),
            "World Cup",
        )
        for country in countries
    ]
    df = pd.DataFrame(
        cnt_name_img, columns=["club_name", "club_logo", "club_link", "league"]
    )
    df.to_csv("data/club_details.csv", index=False, mode="a")

    pd.read_csv("data/club_details.csv").drop_duplicates(subset=["club_name"]).to_csv(
        "data/club_details.csv", index=False, mode="w"
    )


async def get_livescores(club: str, date: str = dt.date.today().isoformat()):
    scores = (
        (await make_soup(f"https://bongda24h.vn/LiveScore/AjaxLivescore?date={date}"))
    ).select("div.calc > div")

    matches = []
    lg_name = "extra_details"
    for i, div in enumerate(scores):
        if div.get("class") == ["football-header"]:
            lg_name = div.select("h3")[0].text.strip()
            continue
        elif div.get("class") == ["football-match-livescore"]:
            home, away = (
                div.select(".club1>img")[0].get("alt").strip(),
                div.select(".club2>img")[0].get("alt").strip(),
            )

            if club not in (home, away):
                continue

            score = div.select("span.soccer-scores")[0].text.strip()
            score = None if "?" in score else score
            time_str = div.select("span.time")[0].text.strip()
            time_ = dateparser.parse(time_str)
            time_ = time_.astimezone(utc).time().isoformat() if time_ else time_str
            match = {
                "league": lg_name,
                "time": time_,
                "date": dateparser.parse(div.select("span.date")[0].text.strip())
                .astimezone(utc)
                .date()
                .isoformat(),
                "round": div.select("span.vongbang, span.vongbang2")[0]
                .get("title")
                .strip(),
                "home": {
                    "name": home,
                    "logo": div.select(".club1>img")[0].get("src"),
                    "link": div.select(".club1")[0].get("href"),
                },
                "away": {
                    "name": away,
                    "logo": div.select(".club2>img")[0].get("src"),
                    "link": div.select(".club2")[0].get("href"),
                },
                "scores": score,
            }

            matches.append(match)

    return matches


def search(term: str, db: List[str], cutoff: int = 60, limit: int = 5):
    result = process.extractBests(
        term, db, scorer=fuzz.ratio, score_cutoff=cutoff, limit=limit
    )
    return [r[0] for r in result]


async def get_news(club_url: str):
    news_list = (await make_soup(club_url)).select(
        "article.post-list, article.article-list"
    )

    news_proc = []
    for news in news_list:
        summary = news.select(".article-summary")
        tags_time = news.select(".tags-time")
        df = {
            "link": uparse.urljoin(
                club_url, news.select(".article-image>a")[0].get("href")
            ),
            "title": news.select(".article-title")[0].text.strip(),
            "summary": summary[0].text.strip() if summary else None,
            "time": tags_time[0].text.strip() if tags_time else None,
        }

        news_proc.append(df)

    return news_proc


def get_text2(sel):
    text = sel.attrs.get("title")
    if not text:
        text = sel.text.strip()

    return unicodedata.normalize("NFKC", text).strip() if text else None


def get_text(sel):
    text = sel.text.strip()
    if not text:
        text = text = sel.attrs.get("title")

    return unicodedata.normalize("NFKC", text).strip() if text else None


def get_image(sel):
    text = sel.text.strip()
    if not text:
        text = text = sel.attrs.get("src")

    return unicodedata.normalize("NFKC", text).strip() if text else None


def get_src(sel):
    return sel.attrs.get("src")


def get_href(sel):
    return sel.attrs.get("href")


def process_players(tbl_trs: List, header_col_pos: Dict, db: pd.DataFrame):
    tbl_body = []
    for tr in tbl_trs:
        tds = tr.select(":scope > td")
        df = {}
        for col, pos in header_col_pos.items():
            td = tds[pos]
            if col == "Name/Position":
                player = td.select("tr")[0]
                df["name"] = get_text(player.select("td.hauptlink>a")[0])
                df["image"] = get_src(player.select("td img")[0])

            elif col == "Club":
                club = get_text2(td.select("img")[0])

                club_in_record = search(club, db.index, cutoff=70, limit=1)
                club_details = (
                    db.loc[club_in_record].reset_index().to_dict(orient="records")[0]
                    if club_in_record
                    else None
                )

                df.update({"club": club_details}) if club_details else None

            elif col == "Nat.":
                result = {}
                for i, nation in enumerate(td.select("img")):
                    nation = get_text2(nation)
                    nation_in_record = search(nation, db.index, cutoff=80, limit=1)
                    nation_details = (
                        db.loc[nation_in_record]
                        .reset_index()
                        .to_dict(orient="records")[0]
                        if nation_in_record
                        else None
                    )

                    if nation_details:
                        result[i] = nation_details
                    else:
                        logger.warning(f"{nation} not found in database")

                df.update({"country": result}) if result else None

            elif col == "Age":
                df["age"] = get_text(td) if len(tds) > pos else None

        tbl_body.append(df) if df else None

    return tbl_body


async def search_player(player: str, db: pd.DataFrame):
    url = f"https://www.transfermarkt.com/schnellsuche/ergebnis/schnellsuche?query={player}"

    pageSoup = await make_soup(url)
    result_tbls = pageSoup.select("div:has(>h2.content-box-headline)")
    results = {}

    for result_tbl in result_tbls:
        hd_cnt = 0
        header_col_pos = {}

        tbl_heads = result_tbl.select("div.responsive-table>div>table>thead>tr>th")
        for th in tbl_heads:
            p = int(th.attrs.get("colspan", 1))
            text = get_text(th)

            hd_cnt += p
            header_col_pos[text] = hd_cnt - 1

        tbl_trs = result_tbl.select("div.responsive-table>div>table>tbody>tr")

        if (
            "players"
            in get_text(result_tbl.select("h2.content-box-headline")[0]).lower()
        ):
            results["players"] = process_players(tbl_trs, header_col_pos, db)
        # elif "clubs" in get_text(result_tbl.select("h2.content-box-headline")[0]).lower():
        #     results["clubs"] = process_clubs(tbl_trs, header_col_pos)

    return results.get("players") if results.get("players") else []


async def process_for_upcoming_match_by_id(name: str, id: str, isClub: bool):
    api_link = uparse.urljoin(
        "https://www.transfermarkt.com/ceapi/nextMatches/",
        f'{"team" if isClub else "player"}/{id}',
    )
    try:
        json_resp = await make_json(api_link)
    except Exception as e:
        logger.warning(f"Failed to fetch {api_link},Error Occurerd: {str(e)}")

    if len(json_resp["matches"]) == 0:
        return {"name": name, "upcoming_match": "No data found"}

    team_map = {}
    for team_id, team in json_resp["teams"].items():
        team_map[int(team_id)] = team["name"]

    match = json_resp["matches"][0]

    return {
        "name": name,
        "upcoming_match": {
            "label": match["competition"]["label"],
            "home": team_map[match["match"]["home"]],
            "away": team_map[match["match"]["away"]],
            "time": dt.datetime.utcfromtimestamp(match["match"]["time"])
            .replace(tzinfo=pytz.UTC)
            .astimezone(pytz.timezone("Asia/Ho_Chi_Minh"))
            .strftime("%A, %m/%d/%Y - %I:%M %p %z"),
        },
    }


async def process_for_upcoming_match_new_by_id(name: str, img_url: str, id: str, isClub: bool):
    api_link = uparse.urljoin(
        "https://www.transfermarkt.com/ceapi/nextMatches/",
        f'{"team" if isClub else "player"}/{id}',
    )
    try:
        json_resp = await make_json(api_link)
    except Exception as e:
        logger.warning(f"Failed to fetch {api_link},Error Occurerd: {str(e)}")

    if len(json_resp["matches"]) == 0:
        return {"name": name, "image": img_url,  "upcoming_match": "No data found"}

    team_map = {}
    for team_id, team in json_resp["teams"].items():
        team_map[int(team_id)] = {'name': team["name"], 'img': team["image2x"]}

    match = json_resp["matches"][0]

    return {
        "name": name,
        "upcoming_match": {
            "label": match["competition"]["label"],
            "home": team_map[match["match"]["home"]].get('name'),
            "home_img": team_map[match["match"]["home"]].get('img'),
            "away": team_map[match["match"]["away"]].get('name'),
            "away_img": team_map[match["match"]["away"]].get('img'),
            "time": dt.datetime.utcfromtimestamp(match["match"]["time"])
            .replace(tzinfo=pytz.UTC)
            .astimezone(pytz.timezone("Asia/Ho_Chi_Minh"))
            .strftime("%A, %m/%d/%Y - %I:%M %p %z"),
        },
    }


async def upcoming_matches(query: str, findBy: str):
    if findBy not in ["clubs", "players"]:
        return []

    url = f"https://www.transfermarkt.com/schnellsuche/ergebnis/schnellsuche?query={query}"

    try:
        pageSoup = await make_soup(url)
    except Exception as e:
        logger.warning(f"Failed to fetch {url},Error Occurerd: {str(e)}")

    result_tbls = pageSoup.select("div:has(>h2.content-box-headline)")
    tasks = []

    for result_tbl in result_tbls:
        if (
            findBy
            not in get_text(result_tbl.select("h2.content-box-headline")[0]).lower()
        ):
            continue

        tbl_trs = result_tbl.select("div.responsive-table>div>table>tbody>tr")

        for tr in tbl_trs:
            player = tr.find("td", {"class": "hauptlink"}).select_one("a")

            if player:
                name = get_text(player)
                player_id = get_href(player).split("/")[-1]
                tasks.append(process_for_upcoming_match_by_id(name, player_id, findBy == "clubs"))

    return await asyncio.gather(*tasks)


async def upcoming_matches_new(query: str, findBy: str):
    if findBy not in ["clubs", "players"]:
        return []

    url = f"https://www.transfermarkt.com/schnellsuche/ergebnis/schnellsuche?query={query}"

    try:
        pageSoup = await make_soup(url)
    except Exception as e:
        logger.warning(f"Failed to fetch {url},Error Occurerd: {str(e)}")

    result_tbls = pageSoup.select("div:has(>h2.content-box-headline)")
    tasks = []

    for result_tbl in result_tbls:
        if (
            findBy
            not in get_text(result_tbl.select("h2.content-box-headline")[0]).lower()
        ):
            continue

        tbl_trs = result_tbl.select("div.responsive-table>div>table>tbody>tr")

        for tr in tbl_trs:
            image_url = ""
            image = tr.find("td", {"class": "zentriert suche-vereinswappen"})
            if image:
                image_url = get_image(image.select_one("img"))

            player = tr.find("td", {"class": "hauptlink"}).select_one("a")

            if player:
                name = get_text(player)
                player_id = get_href(player).split("/")[-1]
                if findBy == "players" and query.upper() in name.upper():
                    tasks.append(process_for_upcoming_match_new_by_id(name, image_url, player_id, findBy == "clubs"))
                
                if findBy == "clubs":
                    tasks.append(process_for_upcoming_match_new_by_id(name, image_url, player_id, findBy == "clubs"))

    return await asyncio.gather(*tasks)


async def trending_matches(country: str):
    url = f"https://trends.google.com/trends/api/dailytrends?hl=en-US&tz=-420&geo={country}&hl=en-US&ns=15"

    try:
        pageSoup = await make_json_new(url)

        data = json.loads(pageSoup.lstrip(")]}\',\n"))
        data = data['default']['trendingSearchesDays']
        # new_string = pageSoup.replace(")]}',\n", "")
        # new_string_str = ''.join(new_string.replace('\"', '"'))
    except Exception as e:
        logger.infor(f"Failed to fetch {url},Error Occurerd: {str(e)}")
        return {str(e)}
        
    return data

# async def trending_matches(country: str):
#     url = 'https://trends.google.com.vn/trends/trendingsearches/daily?geo=VN&hl=en-US'
#     chrome_options = Options()  
#     chrome_options.add_argument("--headless") # Opens the browser up in background

#     with Chrome(options=chrome_options) as browser:
#         browser.get(url)
#         html = browser.page_source

#     page_soup = BeautifulSoup(html, 'html.parser')
        
#     return page_soup
