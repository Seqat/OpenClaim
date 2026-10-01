#!/usr/bin/env python3
"""
Unit tests for giveaway notice detection in GamerPower scraper.
Fixtures are real GamerPower API strings (fetched 2026-10-01) unless marked synthetic.
"""

from unittest.mock import MagicMock, patch

import pytest

from backend.scrapers.gamerpower import detect_notices, fetch_gamerpower_games

ALIENWARE_STEPS = (
    "1. Log in to your free Alienware account and click the button to unlock your key.\r\n"
    "2. Launch the Steam client and click the Games menu option.\r\n"
    "3. Choose \"activate a Product on Steam\" to redeem your Steam key."
)


@pytest.mark.parametrize(
    "title,description,instructions,expected",
    [
        # Alienware Arena
        (
            "RIDE 6 Welcome Bikes Pack Steam Key Giveaway",
            "Claim your free RIDE 6 Welcome Bikes Pack (DLC) Steam Key and unlock three unique bikes. "
            "Please note the base game is required to enjoy this DLC content plus 10 ARP (Arena Reward Points).",
            "1. Log in to your free Alienware account and click the button to unlock your key (10 ARP required).\r\n"
            "2. Launch the Steam client and click the Games menu option.\r\n"
            "3. Choose \"activate a Product on Steam\" to redeem your Steam key.",
            ["alienware_arena"],
        ),
        (
            "Chop Shop Playtest (Steam) Key Giveaway",
            "Claim your free Chop Shop Playtest Steam Key and join the playtest!",
            ALIENWARE_STEPS,
            ["alienware_arena"],
        ),
        # Pinned real case: the title and description only say "Alienware Decal"; the match
        # comes from the instructions ("free Alienware account"), not from the decal wording.
        (
            "Exoprimal: Alienware Decal Steam Key Giveaway",
            "Claim your free Exoprimal: Alienware Decal Steam Key and customize your exosuit! "
            "Please note the base game Exoprimal is required to enjoy this content.",
            "1. Log in or register to your free Alienware account.\r\n"
            "2. Click the button to unlock your free Steam key.\r\n"
            "3. Launch the Steam client and click the Games menu option.\r\n"
            "4. Choose \"activate a Product on Steam\" to redeem your Steam key.",
            ["alienware_arena"],
        ),
        # Multiple codes come back sorted
        (
            "Overstep Skin Key Giveaway",
            "Grab this key and unlock an exclusive skin for Overstep! Please note you must redeem this key in-game.",
            "1. Download and install Overstep on Steam for free.\r\n"
            "2. Login into your Alienwarearena account and grab your key.\r\n"
            "3. Open the game and click on the main menu and enter the code.",
            ["alienware_arena", "redeem_in_game"],
        ),
        # AMD
        (
            "GOALS: AMD Kit Key Giveaway",
            "Claim your free key with the AMD Advanced Kit and enjoy GOALS in style. "
            "Please note the base game GOALS (free-to-play) is required to enjoy this DLC content.",
            "1. Create or log in to your free AMD account.\n"
            "2. Connect one account to your AMD Account (Twitch, Google or Microsoft)\n"
            "3. Click the button to unlock your key.\n"
            "4. Follow the giveaway instructions to redeem your key.",
            ["amd_account"],
        ),
        # DungeonLoot
        (
            "No Brakes Club Playtest Steam Key Giveaway",
            "Coffee Beans Dev is teaming up with our sister site DungeonLoot, to give away Steam playtest keys "
            "for No Brakes Club!",
            "1. Click the button to visit the giveaway page.\n"
            "2. Log in to your free DungeonLoot account and click the button to unlock your key.\n"
            "3. Launch the Steam client software and log in to your Steam account.",
            ["dungeonloot_account"],
        ),
        # Raw HTML in instructions
        (
            "DungeonLoot: Open Beta Has Arrived!",
            "The GamerPower team is on a quest to bring more loot to gamers, so we created DungeonLoot.",
            "1. Click the button to visit  <a href=\"https://www.dungeonloot.com\" target=\"_blank\">DungeonLoot</a>.\r\n"
            "2. Simply create an account. \r\n"
            "3. Select your favorite giveaway and grab the loot. It's that easy!",
            ["dungeonloot_account"],
        ),
        # Newsletter
        (
            "Age of Wonders 4: Special Godir Helmet Steam Key Giveaway",
            "Claim your free Age of Wonders 4: Special Godir Helmet Steam Key! To grab a key you just need to "
            "subscribe to their newsletter! That's it!",
            "1. Subscribe to their newsletter and grab your Steam key.\r\n"
            "2. Launch the Steam client and click the Games menu option.",
            ["newsletter_signup"],
        ),
        ("Synthetic", "", "Newsletter sign-up required to get the code.", ["newsletter_signup"]),
        # Redeem in-game
        (
            "Free Bomb Bots Arena Gift Pack Keys",
            "Claim your Bomb Bots Arena exclusive gift pack key and unlock in-game items for Bomb Bots Arena!\r\n\r\n"
            "*Please note these are not Steam keys, if you pick the Steam version please follow the instructions "
            "and redeem the key inside the game.",
            "1. Login and click the button to unlock your key.\r\n2. Follow the giveaway instructions to redeem your key.",
            ["redeem_in_game"],
        ),
        # HTML entities are unescaped before matching
        ("Synthetic", "", "Log in to your free Alienware&nbsp;Arena account", ["alienware_arena"]),
    ],
)
def test_detect_notices_positive(title, description, instructions, expected):
    assert detect_notices(title, description, instructions) == expected


@pytest.mark.parametrize(
    "title,description,instructions",
    [
        # Real items without extra requirements
        (
            "Mechabellum (Epic Games) Giveaway",
            "Score Mechabellum for free via Epic Games Store!",
            "1. Click the button to visit the giveaway page.\r\n2. Log in to your Epic Games Store account.\r\n"
            "3. Click the button to add the game to your library",
        ),
        (
            "World of Tanks Blitz - Welcome Bundle (Steam) Giveaway",
            "Claim your free World of Tanks Blitz - Welcome Bundle DLC via Steam until June 15.",
            "1. Click the button to visit the giveaway page.\r\n2. Install the base game first (required).\r\n"
            "3. Download this DLC directly via Steam before the offer expires.",
        ),
        (
            "Two Point Hospital: SEGA 60th Items DLC",
            "Please note the base game Two Point Hospital is required to enjoy this DLC content.",
            "1. Install the base game Two Point Hospital first.\r\n2. Download the DLC on Steam.",
        ),
        (
            "Payday 2: Free In-game Items Giveaway",
            "OVERKILL is giving away free in-game items for Payday 2!",
            "1. Click the button to visit the giveaway page.\r\n2. Select your favorite in-game items.\r\n"
            "3. Complete the steps to unlock your in-game items!",
        ),
        (
            "Destiny 2: Be True Emblem Code",
            "Claim your Destiny 2: Be True Emblem Code for free!\r\n\r\nCODE: ML3-FD4-ND9",
            "1. Navigate to the Destiny 2 code redemption page (click on the \"Get Loot\" button).\r\n"
            "2. Choose your platform, sign in to your platform account, then just add your code and redeem it.",
        ),
        (
            "Endless Space 2 - Untold Tales DLC (Steam) Giveaway",
            "Claim your free DLC for Endless Space 2 (limited stock)!",
            "1. Login or create your free Amplitude account.\r\n2. Go to the reward page and link your Steam account.\r\n"
            "3. Go back to the reward page and click the button to redeem your reward.",
        ),
        # Synthetic: "Alienware" in the description with no account requirement
        ("Synthetic", "Unlock the Alienware decal for your ships. Base game required.", ""),
        # Synthetic: word boundaries / case sensitivity of ARP
        ("Synthetic", "Dwarven Realms is a 3D action-packed ARPG with epic powers.", ""),
        ("Synthetic", "Play the harp and the arp.", ""),
        # Synthetic: newsletter without a subscribe / sign-up verb
        ("Synthetic", "No newsletter required.", ""),
        ("Synthetic", "", "Unsubscribe from our newsletter anytime."),
        # Synthetic: keyword only inside an HTML attribute
        ("Synthetic", "", "Visit <a href=\"https://example.com/newsletter/subscribe-newsletter\">the page</a>."),
        # Title alone never triggers (title is intentionally not searched)
        ("Exoprimal: Alienware Arena Decal", "", ""),
        ("DungeonLoot: Open Beta Has Arrived!", "", ""),
    ],
)
def test_detect_notices_negative(title, description, instructions):
    assert detect_notices(title, description, instructions) == []


@pytest.mark.parametrize(
    "title,description,instructions",
    [
        (None, None, None),
        ("", "", ""),
        ("Title", None, ""),
        (None, "", None),
    ],
)
def test_detect_notices_empty_inputs(title, description, instructions):
    assert detect_notices(title, description, instructions) == []


def test_detect_notices_is_deduplicated_and_sorted():
    description = "Log in to Alienware Arena. Alienware account needed. 10 ARP. Subscribe to our newsletter."
    instructions = "Alienware Arena again. Redeem this key in-game. Not Steam keys. Subscribe to the newsletter."
    result = detect_notices("", description, instructions)
    assert result == ["alienware_arena", "newsletter_signup", "redeem_in_game"]
    assert result == sorted(set(result))


def test_fetch_gamerpower_games_includes_notices():
    payload = [
        {
            "id": 3486,
            "title": "Chop Shop Playtest (Steam) Key Giveaway",
            "description": "Claim your free Chop Shop Playtest Steam Key and join the playtest!",
            "instructions": ALIENWARE_STEPS,
            "platforms": "PC, Steam",
            "type": "Early Access",
            "status": "Active",
            "end_date": "N/A",
            "open_giveaway_url": "https://www.gamerpower.com/open/chop-shop",
            "image": "https://www.gamerpower.com/offers/1b/chop.jpg",
        },
        {
            "id": 3790,
            "title": "Mechabellum (Epic Games) Giveaway",
            "description": "Score Mechabellum for free via Epic Games Store!",
            "instructions": "1. Log in to your Epic Games Store account.",
            "platforms": "PC, Epic Games Store",
            "type": "Game",
            "status": "Active",
            "end_date": "N/A",
            "open_giveaway_url": "https://www.gamerpower.com/open/mechabellum",
            "image": "https://www.gamerpower.com/offers/1b/mechabellum.jpg",
        },
    ]
    response = MagicMock()
    response.json.return_value = payload

    with patch("backend.scrapers.gamerpower.requests.get", return_value=response):
        games = fetch_gamerpower_games()

    by_id = {g["id"]: g for g in games}
    assert by_id["steam-3486"]["notices"] == ["alienware_arena"]
    assert by_id["epicgames-3790"]["notices"] == []
