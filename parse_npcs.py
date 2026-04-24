"""
Parse NPC stat blocks from Danger Gal Dossier extracted text.
"""
import re
import json

INPUT_PATH = r"/text_output/pdf_extract.txt"
OUTPUT_JSON = r"C:\Users\gtc19\PycharmProjects\CPRED_DR_Framework\npc_data.json"
OUTPUT_SUMMARY = r"C:\Users\gtc19\PycharmProjects\CPRED_DR_Framework\npc_summary.txt"

with open(INPUT_PATH, "r", encoding="utf-8") as f:
    full_text = f.read()

# Split into per-page sections
page_sections = re.split(r'\n={60}\nPAGE (\d+)\n={60}\n', full_text)
# page_sections: [pre, page_num, content, page_num, content, ...]
pages = {}
for i in range(1, len(page_sections)-1, 2):
    pg_num = int(page_sections[i])
    content = page_sections[i+1] if i+1 < len(page_sections) else ""
    # Strip the repeated ====\n line that appears inside some pages
    content = re.sub(r'={60}\n', '', content)
    pages[pg_num] = content.strip()

print(f"Total pages parsed: {len(pages)}")

# ---- Identify NPC pages ----
# NPC pages have a clear structure:
#   FACTION NAME (all caps header)
#   NPC NAME (all caps)
#   Descriptor subtitle
#   level ... rep ... HP ...
#   role ...
#   STATS line
#   INT REF DEX TECH COOL WILL MOVE BODY EMP values
#   weapons / armor section
#   skill bases section
#   GEAR section
#   cyberware section
#   bio section

STAT_LABELS = ["int", "ref", "dex", "tech", "cool", "will", "move", "body", "emp"]

def extract_stats(text):
    """Extract the 9 core stats from a stat block."""
    # The stats line looks like:
    # 7 8 5 4 8 6 4 5 4
    # int ref DeX tecH cool Will MoVe BoDy eMp
    # Stats may have parenthetical armor-modified values like: 5 8(6) 6(4) 3 3 6 6(4) 7 4
    stat_line_re = re.compile(
        r'([\d]+(?:\([\d]+\))?)\s+'  # INT
        r'([\d]+(?:\([\d]+\))?)\s+'  # REF
        r'([\d]+(?:\([\d]+\))?)\s+'  # DEX
        r'([\d]+(?:\([\d]+\))?)\s+'  # TECH
        r'([\d]+(?:\([\d]+\))?)\s+'  # COOL
        r'([\d]+(?:\([\d]+\))?)\s+'  # WILL
        r'([\d]+(?:\([\d]+\))?)\s+'  # MOVE
        r'([\d]+(?:\([\d]+\))?)\s+'  # BODY
        r'([\d]+(?:\([\d]+\))?)'     # EMP
    )
    # Look for the stat labels line to anchor the search
    label_idx = text.lower().find("int ref")
    if label_idx == -1:
        label_idx = text.lower().find("int\tref")

    # Search in a window around the label
    search_area = text[max(0, label_idx-200):label_idx+200] if label_idx > 0 else text[:500]
    m = stat_line_re.search(search_area)
    if m:
        labels = ["INT", "REF", "DEX", "TECH", "COOL", "WILL", "MOVE", "BODY", "EMP"]
        return {labels[i]: m.group(i+1) for i in range(9)}
    return {}

def extract_section(text, start_keyword, end_keywords):
    """Extract text between start_keyword and the first of end_keywords."""
    start_re = re.compile(re.escape(start_keyword), re.IGNORECASE)
    m = start_re.search(text)
    if not m:
        return ""
    start = m.end()
    end = len(text)
    for ek in end_keywords:
        em = re.compile(re.escape(ek), re.IGNORECASE).search(text, start)
        if em and em.start() < end:
            end = em.start()
    return text[start:end].strip()

def parse_level_rep_hp(text):
    """Parse level, rep, HP, death save from the NPC header block."""
    result = {}
    # level pattern: "level M ini -B oss rep 5 ... HP 40"
    # Normalized: "level Hardened Boss rep 5 ... HP 40"
    level_m = re.search(r'level\s+(.+?)\s+rep\s+(\d+)', text, re.IGNORECASE)
    if level_m:
        result['level'] = re.sub(r'\s+', ' ', level_m.group(1)).strip()
        result['rep'] = level_m.group(2)
    hp_m = re.search(r'HP\s+(\d+)', text, re.IGNORECASE)
    if hp_m:
        result['hp'] = hp_m.group(1)
    death_m = re.search(r'Death\s+(\d+)', text, re.IGNORECASE)
    if not death_m:
        death_m = re.search(r'D\s*[Ss]ave\s*(\d+)', text)
    if death_m:
        result['death_save'] = death_m.group(1)
    sw_m = re.search(r'Seriously\s+Wounded\s+(\d+)', text, re.IGNORECASE)
    if not sw_m:
        # Sometimes "S w e o r u io n u d s e l d y" with number after
        sw_m = re.search(r'wounded\s+(\d+)', text, re.IGNORECASE)
    if sw_m:
        result['seriously_wounded'] = sw_m.group(1)
    return result

def parse_role(text):
    """Extract role(s) from stat block."""
    role_m = re.search(r'role\s+(.+?)(?=\n|STATS|stat)', text, re.IGNORECASE | re.DOTALL)
    if role_m:
        role_text = role_m.group(1).strip()
        role_text = re.sub(r'\s+', ' ', role_text)
        return role_text[:150]  # cap length
    return ""

def parse_weapons(text):
    """Extract weapons section."""
    weapons = []
    # Look for weapons section
    w_start = text.lower().find("weapons")
    a_start = text.lower().find("armor")
    skill_start = text.lower().find("skill bases")
    if w_start == -1:
        return weapons
    end = skill_start if skill_start > w_start else len(text)
    w_text = text[w_start:end]
    # Each weapon line: name ... ROF# damage
    weapon_re = re.compile(r'([A-Za-z][^\n]+?)\s+ROF(\d)\s+([\dd+()\s]+)', re.IGNORECASE)
    for m in weapon_re.finditer(w_text):
        name = re.sub(r'\s+', ' ', m.group(1)).strip()
        weapons.append(f"{name} ROF{m.group(2)} {m.group(3).strip()}")
    return weapons

def parse_skills(text):
    """Extract skills section."""
    skill_start = text.lower().find("skill bases")
    if skill_start == -1:
        return ""
    gear_start = text.lower().find("\ngear\n", skill_start)
    if gear_start == -1:
        gear_start = text.lower().find("gear\n", skill_start)
    cyber_start = text.lower().find("cyberware", skill_start)

    end = len(text)
    for pos in [gear_start, cyber_start]:
        if pos > skill_start and pos < end:
            end = pos

    skills_text = text[skill_start + len("skill bases"):end].strip()
    skills_text = re.sub(r'\s+', ' ', skills_text)
    return skills_text

def parse_gear(text):
    """Extract gear section."""
    gear_start = -1
    for pat in ["GEAR\n", "gear\n", "GEAR ", "gear "]:
        idx = text.find(pat)
        if idx > 0:
            gear_start = idx
            break
    if gear_start == -1:
        return ""
    cyber_start = text.lower().find("cyberware", gear_start)
    end = cyber_start if cyber_start > gear_start else len(text)
    gear_text = text[gear_start + 4:end].strip()
    gear_text = re.sub(r'\s+', ' ', gear_text)
    return gear_text

def parse_cyberware(text):
    """Extract cyberware section."""
    cyber_start = text.lower().find("cyberware")
    if cyber_start == -1:
        return ""
    # Cyberware ends at bio (which starts after a blank line followed by longer prose)
    bio_markers = ["DAEH\nYDOB", "DAEH YDOB", "\n\n\n"]
    end = len(text)
    for bm in bio_markers:
        idx = text.find(bm, cyber_start)
        if idx > cyber_start and idx < end:
            end = idx
    cyber_text = text[cyber_start + len("cyberware"):end].strip()
    cyber_text = re.sub(r'\s+', ' ', cyber_text)
    return cyber_text

def parse_bio(text):
    """Extract biography section (after cyberware)."""
    # Bio appears after DAEH YDOB watermark text or after cyberware
    bio_start = -1
    for bm in ["DAEH\nYDOB", "DAEH YDOB"]:
        idx = text.find(bm)
        if idx > 0:
            bio_start = idx + len(bm)
            break

    if bio_start == -1:
        # Try to find it after cyberware
        cyber_start = text.lower().find("cyberware")
        if cyber_start > 0:
            # Bio is several lines after cyberware
            # Look for a paragraph-like block
            after_cyber = text[cyber_start + 200:]
            # Find first paragraph (line starting with capital letter, not ALL CAPS)
            para_m = re.search(r'\n([A-Z][a-z].{20,})', after_cyber)
            if para_m:
                bio_start = cyber_start + 200 + para_m.start()

    if bio_start == -1:
        return ""

    bio_text = text[bio_start:].strip()
    # Clean up
    bio_text = re.sub(r'\s+', ' ', bio_text)
    # Cap at ~1000 chars
    return bio_text[:1000]


# ---- Main parsing loop ----
# Strategy: look for pages that contain a stat block pattern
# Key pattern: lines with STATS header followed by 9 numbers, then skill bases

NPC_STAT_PATTERN = re.compile(
    r'STATS\s*\n'
    r'\s*([\d]+(?:\([\d]+\))?)\s+'
    r'([\d]+(?:\([\d]+\))?)\s+'
    r'([\d]+(?:\([\d]+\))?)\s+'
    r'([\d]+(?:\([\d]+\))?)\s+'
    r'([\d]+(?:\([\d]+\))?)\s+'
    r'([\d]+(?:\([\d]+\))?)\s+'
    r'([\d]+(?:\([\d]+\))?)\s+'
    r'([\d]+(?:\([\d]+\))?)\s+'
    r'([\d]+(?:\([\d]+\))?)',
    re.IGNORECASE
)

FACTION_PATTERN = re.compile(r'^([A-Z][A-Z0-9 \-]+[A-Z0-9])\s*$', re.MULTILINE)
NPC_NAME_PATTERN = re.compile(r'^([A-Z][A-Z0-9!? \-\'\./]+[A-Z0-9!?])\s*$', re.MULTILINE)

npcs = []

# We'll process pages looking for stat blocks
sorted_page_nums = sorted(pages.keys())

i = 0
while i < len(sorted_page_nums):
    pg_num = sorted_page_nums[i]
    content = pages[pg_num]

    if NPC_STAT_PATTERN.search(content):
        # This page has a stat block - try to find NPC name
        # The NPC name is typically an ALL-CAPS line near the top
        lines = content.split('\n')

        # Find faction and NPC name from the top lines
        faction = ""
        npc_name = ""
        descriptor = ""

        for j, line in enumerate(lines[:20]):
            line = line.strip()
            if not line:
                continue
            # Check if it's all caps (faction or NPC name)
            if re.match(r'^[A-Z][A-Z0-9 \-&!\'\./]+$', line) and len(line) > 3:
                # First all-caps = faction, second all-caps = NPC name
                if not faction:
                    faction = line
                elif not npc_name:
                    npc_name = line
                    # Descriptor is next non-empty line
                    for k in range(j+1, min(j+5, len(lines))):
                        dl = lines[k].strip()
                        if dl and not re.match(r'^level', dl, re.IGNORECASE):
                            descriptor = dl
                            break
                    break

        if not npc_name and faction:
            npc_name = faction
            faction = ""

        # Extract stat values
        stat_m = NPC_STAT_PATTERN.search(content)
        stats = {}
        if stat_m:
            labels = ["INT", "REF", "DEX", "TECH", "COOL", "WILL", "MOVE", "BODY", "EMP"]
            for idx_s, label in enumerate(labels):
                stats[label] = stat_m.group(idx_s + 1)

        meta = parse_level_rep_hp(content)
        role = parse_role(content)
        weapons = parse_weapons(content)
        skills = parse_skills(content)
        gear = parse_gear(content)
        cyberware = parse_cyberware(content)
        bio = parse_bio(content)

        npc = {
            "page": pg_num,
            "faction": faction,
            "name": npc_name,
            "descriptor": descriptor,
            "level": meta.get("level", ""),
            "rep": meta.get("rep", ""),
            "hp": meta.get("hp", ""),
            "seriously_wounded": meta.get("seriously_wounded", ""),
            "death_save": meta.get("death_save", ""),
            "role": role,
            "stats": stats,
            "weapons": weapons,
            "skills": skills,
            "gear": gear,
            "cyberware": cyberware,
            "bio": bio,
        }
        npcs.append(npc)
        print(f"  Page {pg_num}: [{faction}] {npc_name} ({descriptor[:40] if descriptor else 'no descriptor'})")

    i += 1

print(f"\nTotal NPCs found: {len(npcs)}")

# Save JSON
with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(npcs, f, indent=2, ensure_ascii=False)
print(f"Saved JSON to {OUTPUT_JSON}")

# Save human-readable summary
with open(OUTPUT_SUMMARY, "w", encoding="utf-8") as f:
    f.write(f"DANGER GAL DOSSIER - NPC DATA\n")
    f.write(f"Extracted from PDF: 178 pages, {len(npcs)} NPCs found\n")
    f.write("="*80 + "\n\n")

    current_faction = ""
    for npc in npcs:
        if npc["faction"] != current_faction:
            current_faction = npc["faction"]
            f.write(f"\n{'#'*80}\n")
            f.write(f"FACTION: {current_faction}\n")
            f.write(f"{'#'*80}\n\n")

        f.write(f"{'='*60}\n")
        f.write(f"NAME: {npc['name']}\n")
        if npc['descriptor']:
            f.write(f"DESCRIPTOR: {npc['descriptor']}\n")
        f.write(f"FACTION: {npc['faction']}\n")
        f.write(f"PAGE: {npc['page']}\n")
        f.write(f"LEVEL: {npc['level']}  REP: {npc['rep']}  HP: {npc['hp']}  ")
        f.write(f"SERIOUSLY WOUNDED: {npc['seriously_wounded']}  DEATH SAVE: {npc['death_save']}\n")
        f.write(f"ROLE: {npc['role']}\n")

        if npc['stats']:
            s = npc['stats']
            f.write(f"STATS:\n")
            f.write(f"  INT:{s.get('INT','?')}  REF:{s.get('REF','?')}  DEX:{s.get('DEX','?')}  ")
            f.write(f"TECH:{s.get('TECH','?')}  COOL:{s.get('COOL','?')}  WILL:{s.get('WILL','?')}  ")
            f.write(f"MOVE:{s.get('MOVE','?')}  BODY:{s.get('BODY','?')}  EMP:{s.get('EMP','?')}\n")

        if npc['weapons']:
            f.write(f"WEAPONS:\n")
            for w in npc['weapons']:
                f.write(f"  - {w}\n")

        if npc['skills']:
            f.write(f"SKILLS: {npc['skills']}\n")

        if npc['gear']:
            f.write(f"GEAR: {npc['gear']}\n")

        if npc['cyberware']:
            f.write(f"CYBERWARE: {npc['cyberware']}\n")

        if npc['bio']:
            f.write(f"BIO: {npc['bio']}\n")

        f.write("\n")

print(f"Saved summary to {OUTPUT_SUMMARY}")

# Print summary to console
print("\n" + "="*70)
print("NPC LIST BY FACTION:")
print("="*70)
current_faction = ""
for npc in npcs:
    if npc["faction"] != current_faction:
        current_faction = npc["faction"]
        print(f"\n  [{current_faction}]")
    s = npc['stats']
    stat_str = ""
    if s:
        stat_str = (f"INT:{s.get('INT','?')} REF:{s.get('REF','?')} DEX:{s.get('DEX','?')} "
                    f"TECH:{s.get('TECH','?')} COOL:{s.get('COOL','?')} WILL:{s.get('WILL','?')} "
                    f"MOVE:{s.get('MOVE','?')} BODY:{s.get('BODY','?')} EMP:{s.get('EMP','?')}")
    print(f"    p{npc['page']:3d}: {npc['name']:<30} HP:{npc['hp']:<4}  {stat_str}")
