"""What game is this?

A gaming stream says which game it is: in its title, in the category Twitch shows,
in the channel name. Knowing the game changes two things:

- the AI is told what kind of moment it is looking at (a clutch in the same game
  means something different from a talking segment), and
- every post carries the tags people actually search for (#GTA6), not just
  #gaming.

The game is read from the title only. It is a hint for the copy, never a filter:
a stream whose title says GTA 6 but which is really a chat stream still gets
clips, they just get GTA tags on them.
"""

from __future__ import annotations

import re

from . import roman

# name, words that mean it, tags to put on the post
GAMES: list[tuple[str, list[str], list[str]]] = [
    ("Grand Theft Auto VI", ["grand theft auto vi", "grand theft auto 6", "grand theft auto six", "gta vi", "gta 6",
                             "gta six", "gta6"],
     ["GTA6", "GTA6Game", "ViceCity", "RockstarGames", "GTA6Launch"]),
    ("Grand Theft Auto V", ["grand theft auto v", "grand theft auto 5", "gta online", "gta v", "gta 5", "gta5", "gtav"],
     ["GTA5", "GTAOnline", "RockstarGames", "GTA5RP"]),
    ("Grand Theft Auto IV", ["grand theft auto iv", "gta 4", "gta4"], ["GTA4", "RockstarGames"]),
    ("Fortnite", ["fortnite"], ["Fortnite", "FortniteOG", "BattleRoyale"]),
    ("Minecraft", ["minecraft"], ["Minecraft", "MinecraftGame"]),
    ("Valorant", ["valorant"], ["Valorant", "ValRadiant"]),
    ("League of Legends", ["league of legends", "league of legend"], ["LeagueOfLegends", "LoL", "RiotGames"]),
    ("Counter-Strike", ["counter-strike", "counter strike", "cs2", "csgo"], ["CS2", "CounterStrike", "Esports"]),
    ("Elden Ring", ["elden ring"], ["EldenRing", "SoulsLike", "FromSoftware"]),
    ("Palworld", ["palworld"], ["Palworld", "Survival"]),
    ("Call of Duty", ["call of duty", "warzone"], ["CallOfDuty", "Warzone", "COD"]),
    ("Helldivers 2", ["helldivers 2", "helldivers2"], ["Helldivers2", "StarshipTroopers", "CoOp"]),
    ("Cyberpunk 2077", ["cyberpunk 2077", "cyberpunk"], ["Cyberpunk2077", "NightCity"]),
    ("Starfield", ["starfield"], ["Starfield", "Bethesda"]),
    ("Black Myth Wukong", ["black myth", "wukong"], ["BlackMythWukong", "ActionRPG"]),
    ("Marvel Rivals", ["marvel rivals"], ["MarvelRivals", "Heroes"]),
    ("Overwatch 2", ["overwatch 2", "overwatch"], ["Overwatch2", "OW2", "Blizzard"]),
    ("ARK", ["ark: survival", "ark survival"], ["ARK", "Survival"]),
    ("Dead by Daylight", ["dead by daylight"], ["DeadByDaylight", "Asymmetric"]),
    ("Rocket League", ["rocket league"], ["RocketLeague", "CarSports"]),
    ("Apex Legends", ["apex legends"], ["ApexLegends", "EApex"]),
    ("PUBG", ["pubg", "playerunknown"], ["PUBG", "BattleRoyale"]),
    ("Grand Theft Auto: San Andreas", ["grand theft auto san andreas", "gta sa"], ["GTA", "SanAndreas"]),
    # Vice City is only the old game when the title says GTA before it: a GTA VI title that talks about its Vice City
    # map is still GTA VI.
    ("Grand Theft Auto: Vice City", ["grand theft auto vice city", "gta vice city", "gta vc"],
     ["GTAViceCity", "ViceCity", "RockstarGames"]),
    # The games Indian streams and clip channels are built around, mostly on a phone.
    ("BGMI", ["bgmi", "battlegrounds mobile india", "battleground mobile india"],
     ["BGMI", "BGMIIndia", "BattlegroundsMobileIndia", "Krafton"]),
    ("Free Fire", ["free fire", "freefire", "free fire max", "garena free fire"],
     ["FreeFire", "FreeFireMax", "Garena", "FFIndia"]),
    ("Call of Duty: Mobile", ["call of duty mobile", "call of duty: mobile", "cod mobile", "codm"],
     ["CODMobile", "CallOfDutyMobile", "CODM"]),
    ("Roblox", ["roblox"], ["Roblox", "RobloxGaming"]),
    ("Clash of Clans", ["clash of clans"], ["ClashOfClans", "COC", "Supercell"]),
    ("Clash Royale", ["clash royale", "clash royal"], ["ClashRoyale", "Supercell"]),
    ("Brawl Stars", ["brawl stars"], ["BrawlStars", "Supercell"]),
    ("Genshin Impact", ["genshin impact", "genshin"], ["GenshinImpact", "Genshin", "HoYoverse"]),
    ("eFootball", ["efootball", "e football"], ["eFootball", "PES", "Konami"]),
]

# for a stream whose game nobody can name
GENERIC = ["Gaming", "Gameplay", "GamingClips", "StreamHighlights"]

# longest word first, so "gta 6" is read before "gta"
_ALIASES: list[tuple[str, str, list[str]]] = sorted(
    ((alias, name, tags) for name, aliases, tags in GAMES for alias in aliases),
    key=lambda a: -len(a[0]),
)

_WORD = re.compile(r"[^a-z0-9]+")


def _norm(text: str) -> str:
    # Hindi titles (जीटीए 6, फ्री फायर) are written in Roman letters first, so that they meet the same names as English ones.
    return _WORD.sub(" ", roman.to_roman(str(text or "")).lower()).strip()


def detect(*texts) -> tuple[str | None, list[str]]:
    """The game named in the text, and the tags that belong on its posts.

    Returns (None, []) when no known game is named."""
    hay = _norm(" ".join(str(t or "") for t in texts))
    if not hay:
        return None, []
    for alias, name, tags in _ALIASES:
        if re.search(r"(?:^| )" + re.escape(_norm(alias)) + r"(?: |$)", hay):
            return name, list(tags)
    return None, []


def name_of(game: str | None) -> str:
    """The game's proper name, from a name, a tag or a spelling of its own."""
    if not game:
        return ""
    g = _norm(game)
    for name, aliases, _tags in GAMES:
        if g == _norm(name) or g in {_norm(a) for a in aliases}:
            return name
    return str(game)[:40]


def tags_of(game: str | None) -> list[str]:
    """The tags for a game, whether it is named in full, short, or by one of its tags."""
    if not game:
        return []
    g = _norm(game)
    for name, aliases, tags in GAMES:
        if g == _norm(name) or g in {_norm(a) for a in aliases} or g in {_norm(t) for t in tags}:
            return list(tags)
    tag = re.sub(r"\W", "", roman.to_roman(str(game)))[:30]       # a tag is never in Hindi letters
    return [tag] if tag else []
