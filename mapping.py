HEROES = {
    "abrams":       {"name": "Abrams",                   "image": "hero_abrams"},
    "apollo":       {"name": "Apollo",                    "image": "hero_apollo"},
    "bebop":        {"name": "Bebop",                     "image": "hero_bebop"},
    "billy":        {"name": "Billy",                     "image": "hero_billy"},
    "calico":       {"name": "Calico",                    "image": "hero_calico"},
    "celeste":      {"name": "Celeste",                   "image": "hero_celeste"},
    "drifter":      {"name": "Drifter",                   "image": "hero_drifter"},
    "dynamo":       {"name": "Dynamo",                    "image": "hero_dynamo"},
    "graves":       {"name": "Graves",                    "image": "hero_graves"},
    "grey_talon":   {"name": "Grey Talon",                "image": "hero_grey_talon"},
    "haze":         {"name": "Haze",                      "image": "hero_haze"},
    "holliday":     {"name": "Holliday",                  "image": "hero_holliday"},
    "infernus":     {"name": "Infernus",                  "image": "hero_infernus"},
    "ivy":          {"name": "Ivy",                       "image": "hero_ivy"},
    "kelvin":       {"name": "Kelvin",                    "image": "hero_kelvin"},
    "lady_geist":   {"name": "Lady Geist",                "image": "hero_lady_geist"},
    "lash":         {"name": "Lash",                      "image": "hero_lash"},
    "mcginnis":     {"name": "McGinnis",                  "image": "hero_mcginnis"},
    "mina":         {"name": "Mina",                      "image": "hero_mina"},
    "mirage":       {"name": "Mirage",                    "image": "hero_mirage"},
    "mo_krill":     {"name": "Mo & Krill",                "image": "hero_mo_and_krill"},
    "paige":        {"name": "Paige",                     "image": "hero_paige"},
    "paradox":      {"name": "Paradox",                   "image": "hero_paradox"},
    "pocket":       {"name": "Pocket",                    "image": "hero_pocket"},
    "rem":          {"name": "Rem",                       "image": "hero_rem"},
    "seven":        {"name": "Seven",                     "image": "hero_seven"},
    "shiv":         {"name": "Shiv",                      "image": "hero_shiv"},
    "sinclair":     {"name": "The Magnificent Sinclair",  "image": "hero_sinclair"},
    "the_doorman":  {"name": "The Doorman",               "image": "hero_the_doorman"},
    "venator":      {"name": "Venator",                   "image": "hero_venator"},
    "victor":       {"name": "Victor",                    "image": "hero_victor"},
    "vindicta":     {"name": "Vindicta",                  "image": "hero_vindicta"},
    "viscous":      {"name": "Viscous",                   "image": "hero_viscous"},
    "vyper":        {"name": "Vyper",                     "image": "hero_vyper"},
    "warden":       {"name": "Warden",                    "image": "hero_warden"},
    "wraith":       {"name": "Wraith",                    "image": "hero_wraith"},
    "yamato":       {"name": "Yamato",                    "image": "hero_yamato"},
    # Hero Labs
    "fathom":       {"name": "Fathom",                    "image": "hero_fathom"},
    "raven":        {"name": "Raven",                     "image": "hero_raven"},
    "trapper":      {"name": "Trapper",                   "image": "hero_trapper"},
    "wrecker":      {"name": "Wrecker",                   "image": "hero_wrecker"},
}

HERO_ALIASES = {
    "mo and krill": "mo_krill",
    "mo&krill":     "mo_krill",
    "grey talon":   "grey_talon",
    "greytalon":    "grey_talon",
    "lady geist":   "lady_geist",
    "ladygeist":    "lady_geist",
    "the doorman":  "the_doorman",
    "doorman":      "the_doorman",
    "the magnificent sinclair": "sinclair",
    "magnificent sinclair":     "sinclair",
}

GAME_MODES = {
    "standard":     "Standard Match",
    "ranked":       "Ranked Match",
    "streetbrawl":  "Street Brawl",
    "street_brawl": "Street Brawl",
    "custom":       "Custom Match",
    "bot_match":    "Bot Match",
    "tutorial":     "Tutorial",
    "hero_labs":    "Hero Labs",
}


def lookup_hero(raw_name: str) -> dict | None:
    key = raw_name.strip().lower().replace(" ", "_")
    if key in HEROES:
        return HEROES[key]
    alias_key = raw_name.strip().lower()
    if alias_key in HERO_ALIASES:
        return HEROES.get(HERO_ALIASES[alias_key])
    cleaned = key.replace("hero_", "")
    if cleaned in HEROES:
        return HEROES[cleaned]
    return None


def get_game_mode_display(raw_mode: str) -> str:
    key = raw_mode.strip().lower().replace(" ", "_")
    return GAME_MODES.get(key, raw_mode.title())
