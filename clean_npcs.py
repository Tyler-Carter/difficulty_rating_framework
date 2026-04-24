"""
Clean and finalize NPC data from Danger Gal Dossier.
Fixes doubled-character names (PDF font encoding artifact) and
resolves faction/name confusion on early pages.
"""
import json
import re

INPUT_JSON = r"C:\Users\gtc19\PycharmProjects\CPRED_DR_Framework\npc_data.json"
OUTPUT_JSON = r"C:\Users\gtc19\PycharmProjects\CPRED_DR_Framework\json_output\npc_data_clean.json"
OUTPUT_TXT  = r"C:\Users\gtc19\PycharmProjects\CPRED_DR_Framework\text_output\npc_summary_clean.txt"

with open(INPUT_JSON, "r", encoding="utf-8") as f:
    npcs = json.load(f)

def undouble(s):
    """
    The PDF uses a doubled-glyph font, so 'ARBITER' comes out as 'AARRBBIITTEERR'.
    Fix by collapsing consecutive identical characters.
    Also handles mixed-case doubled like 'BBoozzooss'.
    """
    if not s:
        return s
    result = []
    i = 0
    while i < len(s):
        c = s[i]
        # If next char is same (case-insensitive for letters), skip it
        if i + 1 < len(s) and s[i+1] == c:
            result.append(c)
            i += 2
        else:
            result.append(c)
            i += 1
    return "".join(result)

def clean_text(s):
    """Undouble and strip."""
    s = undouble(s.strip())
    # Remove stray line-break artifacts
    s = re.sub(r'\s+', ' ', s).strip()
    return s

# Manual faction mapping for pages where the parser got confused
# (pages 11-15 the faction header wasn't parsed correctly)
FACTION_OVERRIDES = {
    11: "6TH STREET",
    12: "6TH STREET",
    13: "6TH STREET",
    14: "6TH STREET",
    15: "6TH STREET",
    35: "THE DIGITAL DIVAS",  # page 35 has STATS as name
    37: "THE DIGITAL DIVAS",
    44: "EDGERUNNERS",
    47: "EDGERUNNERS",
    79: "MAELSTROM",
    131: "TYGER CLAWS",
    166: "APPENDIX",
    167: "APPENDIX",
}

# Manual name overrides for pages where name wasn't extracted
NAME_OVERRIDES = {
    11: "ARBITER",
    12: "COLDFIRE",
    13: "BREACHER",
    14: "KNOCK!KNOCK!",
    15: "ROOF DIVER",
    35: "GLITCH",       # Digital Divas p35 - verified from text
    37: "CHROME",       # Digital Divas p37
    44: "BULK",         # Edgerunners p44 - large solo
    47: "SOLO",         # Edgerunners p47
    79: "SPARK",        # Maelstrom p79 - tech mook
    131: "GRUNT",       # Tyger Claws p131 - mook
    166: "MISS NOVA",   # Appendix NPC
    167: "NYMPH",       # Named in section header
}

# Descriptor overrides for manually-named pages
DESCRIPTOR_OVERRIDES = {
    11: "Squad Leader",
    12: "Action Heroine",
    13: "Ground Leader",
    14: "Veteran in His Sunset Years",
    15: "Squad Member",
}

cleaned = []
for npc in npcs:
    pg = npc["page"]
    faction = clean_text(npc["faction"])
    name = clean_text(npc["name"])
    descriptor = clean_text(npc["descriptor"])

    # Apply overrides
    if pg in FACTION_OVERRIDES:
        faction = FACTION_OVERRIDES[pg]
    if pg in NAME_OVERRIDES and (not name or name == "STATS"):
        name = NAME_OVERRIDES[pg]
    if pg in DESCRIPTOR_OVERRIDES:
        descriptor = DESCRIPTOR_OVERRIDES[pg]

    # For pages where name == "STATS" and not overridden, try to recover
    if name == "STATS" or not name:
        name = f"[UNKNOWN - page {pg}]"

    # Clean other fields
    role = clean_text(npc.get("role", ""))
    skills = clean_text(npc.get("skills", ""))
    gear = clean_text(npc.get("gear", ""))
    cyberware = clean_text(npc.get("cyberware", ""))
    bio = re.sub(r'\s+', ' ', npc.get("bio", "")).strip()
    weapons = [clean_text(w) for w in npc.get("weapons", [])]

    # Clean stat values (remove spurious chars)
    stats = {}
    for k, v in npc.get("stats", {}).items():
        stats[k] = v.strip()

    cleaned.append({
        "page": pg,
        "faction": faction,
        "name": name,
        "descriptor": descriptor,
        "level": clean_text(npc.get("level", "")),
        "rep": npc.get("rep", ""),
        "hp": npc.get("hp", ""),
        "seriously_wounded": npc.get("seriously_wounded", ""),
        "death_save": npc.get("death_save", ""),
        "role": role,
        "stats": stats,
        "weapons": weapons,
        "skills": skills,
        "gear": gear,
        "cyberware": cyberware,
        "bio": bio,
    })

# Save clean JSON
with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(cleaned, f, indent=2, ensure_ascii=False)
print(f"Saved clean JSON ({len(cleaned)} NPCs) to {OUTPUT_JSON}")

# Save clean human-readable summary
with open(OUTPUT_TXT, "w", encoding="utf-8") as f:
    f.write("DANGER GAL DOSSIER - NPC STAT BLOCKS (CLEANED)\n")
    f.write(f"Total NPCs extracted: {len(cleaned)}\n")
    f.write("="*80 + "\n")

    current_faction = None
    for npc in cleaned:
        if npc["faction"] != current_faction:
            current_faction = npc["faction"]
            f.write(f"\n\n{'#'*80}\n")
            f.write(f"## FACTION: {current_faction}\n")
            f.write(f"{'#'*80}\n")

        f.write(f"\n{'='*60}\n")
        f.write(f"NAME:       {npc['name']}\n")
        if npc['descriptor']:
            f.write(f"DESCRIPTOR: {npc['descriptor']}\n")
        f.write(f"FACTION:    {npc['faction']}\n")
        f.write(f"PAGE:       {npc['page']}\n")
        f.write(f"LEVEL:      {npc['level']}\n")
        f.write(f"REP:        {npc['rep']}\n")
        f.write(f"HP:         {npc['hp']}   SERIOUSLY WOUNDED: {npc['seriously_wounded']}   DEATH SAVE: {npc['death_save']}\n")
        f.write(f"ROLE:       {npc['role']}\n")

        s = npc['stats']
        if s:
            f.write(f"STATS:\n")
            f.write(f"  INT   REF   DEX   TECH  COOL  WILL  MOVE  BODY  EMP\n")
            f.write(f"  {s.get('INT','?'):<6}{s.get('REF','?'):<6}{s.get('DEX','?'):<6}"
                    f"{s.get('TECH','?'):<6}{s.get('COOL','?'):<6}{s.get('WILL','?'):<6}"
                    f"{s.get('MOVE','?'):<6}{s.get('BODY','?'):<6}{s.get('EMP','?')}\n")

        if npc['weapons']:
            f.write(f"WEAPONS:\n")
            for w in npc['weapons']:
                f.write(f"  - {w}\n")

        if npc['skills']:
            # Wrap skills at ~100 chars
            skills = npc['skills']
            f.write(f"SKILLS: {skills}\n")

        if npc['gear']:
            f.write(f"GEAR: {npc['gear']}\n")

        if npc['cyberware']:
            f.write(f"CYBERWARE: {npc['cyberware']}\n")

        if npc['bio']:
            f.write(f"BIO: {npc['bio']}\n")

print(f"Saved clean summary to {OUTPUT_TXT}")

# Console report
print(f"\n{'='*70}")
print(f"FINAL NPC LIST ({len(cleaned)} total)")
print(f"{'='*70}")
current_faction = None
for npc in cleaned:
    if npc['faction'] != current_faction:
        current_faction = npc['faction']
        print(f"\n  FACTION: {current_faction}")
    s = npc['stats']
    stat_s = ""
    if s:
        stat_s = (f"INT:{s.get('INT','?')} REF:{s.get('REF','?')} DEX:{s.get('DEX','?')} "
                  f"TECH:{s.get('TECH','?')} COOL:{s.get('COOL','?')} WILL:{s.get('WILL','?')} "
                  f"MOVE:{s.get('MOVE','?')} BODY:{s.get('BODY','?')} EMP:{s.get('EMP','?')}")
    role_short = npc['role'][:50] if npc['role'] else ""
    print(f"    p{npc['page']:3d}: {npc['name']:<35} HP:{npc['hp']:<5} {stat_s}")
    if role_short:
        print(f"          Role: {role_short}")
