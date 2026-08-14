#!/usr/bin/env python3
"""
Unit tests for content type classification heuristic in GamerPower scraper.
"""

import pytest
from backend.scrapers.gamerpower import classify_content_type


@pytest.mark.parametrize(
    "title,gp_type,expected",
    [
        # Required Table Tests from Issue #2 Specification
        ("EVERSPACE 2 Decal DLC Steam", None, "dlc"),
        ("Moonlighter", None, "game"),
        ("Chop Shop Playtest", None, "game"),
        ("Payday 2: Free In-game Items", None, "dlc"),
        ("World of Tanks Blitz - Welcome Bundle", None, "dlc"),

        # Playtest & Beta Priority Overrides (Should always be "game")
        ("Drop Loot (Playtest) Steam", None, "game"),
        ("DungeonLoot: Open Beta Has Arrived!", None, "game"),
        ("Zero King (Beta) Steam", None, "game"),
        ("Project Beta Playtest Pack", None, "game"),

        # Real titles from games.json with various DLC keywords
        ("Age of Wonders 4: Special Godir Helmet Steam", None, "dlc"),
        ("Destiny 2: Be True Emblem Code", None, "dlc"),
        ("Deadswitch Combat: Weapons Skins Steam", None, "dlc"),
        ("Overstep Skin", None, "dlc"),
        ("GOALS: AMD Kit", None, "dlc"),
        ("Thunder League Online: Free Points", None, "dlc"),
        ("Fantasy Grounds Dragons NPC Dice Pack Volume 1 Steam", None, "dlc"),
        ("3on3 FreeStyle: Beginner's Starter Kit", None, "dlc"),
        ("DAVE THE DIVER - Godzilla Content Pack", None, "dlc"),
        ("Dominion Synergy Gift Pack", None, "dlc"),
        ("DK Online: Season 4 First Steps Pack", None, "dlc"),
        ("Exoprimal: Alienware Decal Steam", None, "dlc"),
        ("Free Bomb Bots Arena Gift Pack Keys", None, "dlc"),
        ("Dream of Mirror Online Summer Fun DLC Pack Steam Keys", None, "dlc"),

        # Standard Full Games (without DLC terms)
        ("Airship: Kingdoms Adrift", None, "game"),
        ("Steelrising", None, "game"),
        ("Caravan SandWitch", None, "game"),
        ("Two Point Hospital", None, "game"),
        ("Deponia", None, "game"),
        ("Dwarven Realms", None, "game"),
        ("happiness market", None, "game"),

        # GamerPower API 'type' field tests
        ("Some Mystery Item", "DLC", "dlc"),
        ("Some Item Code", "In-game Content", "dlc"),
        ("Loot Crate Giveaway", "Loot", "dlc"),
        ("Full Indie Game", "Game", "game"),
        ("Early Access RPG", "Early Access", "game"),

        # Edge cases: empty / None
        ("", None, "game"),
        (None, None, "game"),
    ],
)
def test_classify_content_type(title, gp_type, expected):
    assert classify_content_type(title, gp_type) == expected
