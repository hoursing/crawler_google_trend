import datetime as dt
import pandas as pd
from fastapi import FastAPI, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json

from main import search, get_livescores, get_news, search_player, upcoming_matches,upcoming_matches_new, trending_matches


class Receipt(BaseModel):
    url: str
    id: str | None = None


app = FastAPI()

origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "news and match API"}


@app.get("/search/{term}")
async def search_term(term: str):
    db = pd.read_csv("data/club_details.csv", index_col=0).fillna("")
    result = search(term, db.index)
    data = db.loc[result].reset_index().to_dict(orient="records")

    return {"search_result": data}


@app.get("/livescores/{club}")
async def livescores(club: str, date=dt.date.today().isoformat()):
    db = pd.read_csv("data/club_details.csv", index_col=0).fillna("")
    if club not in db.index:
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="club not in our record"
        )

    matches = await get_livescores(club, date=date)
    return {"matches": matches}


@app.get("/news/{club}")
async def news(club: str):
    db = pd.read_csv("data/club_details.csv", index_col=0).fillna("")
    if club not in db.index:
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="club not in our record"
        )

    news = await get_news(db.loc[club, "club_link"])

    return {"news": news}


@app.get("/searchPlayer/{player}")
async def player_search(player: str):
    db = pd.read_csv("data/club_details.csv", index_col=0).fillna("")
    result = await search_player(player, db)

    return {"search_result": result}


@app.get("/nextMatch/players/{players}")
async def get_upcoming_match(players: str):
    result = await upcoming_matches(players, "players")
    if len(result) == 0:
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="player not in our record",
        )

    return {"search_result": result}


@app.get("/nextMatchNew/players/{players}")
async def get_upcoming_match_player(players: str):
    all_players: list =  players.split(",")

    result = []
    for player in all_players:
        result_match = await upcoming_matches_new(player, "players")
        if len(result_match) > 0:
            result += result_match
        
    if len(result) == 0:
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="player not in our record",
        )

    return {"search_result": result}


@app.get("/nextMatch/clubs/{clubs}")
async def get_upcoming_match(clubs: str):
    result = await upcoming_matches(clubs, "clubs")
            
    if len(result) == 0:
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="club not in our record",
        )

    return {"search_result": result}


@app.get("/nextMatchNew/clubs/{clubs}")
async def get_upcoming_match_club(clubs: str):
    all_clubs: list =  clubs.split(",")
    result = []
    for club in all_clubs:
        result_match = await upcoming_matches_new(club, "clubs")
        if len(result_match) > 0:
            result += result_match
            
    if len(result) == 0:
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="club not in our record",
        )

    return {"search_result": result}


@app.get("/trending/{country}")
async def get_trending_match(country: str):

    result = await trending_matches(country)

    return {"search_result": result }

