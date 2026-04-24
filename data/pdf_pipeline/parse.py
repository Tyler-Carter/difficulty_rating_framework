import re
import json

from data.config import JSON_OUTPUT_DIR, TEXT_OUTPUT_DIR

STAT_LABELS = ["int", "ref", "dex", "tech", "cool", "will", "move", "body", "emp"]

# ---------------------------------------------------------------------------
# Parse NPC stat blocks out of the extracted PDF text.
# All module-level execution from `parse_npcs.py` is refactored into named
#  and callable functions
# ---------------------------------------------------------------------------
def split_pages(full_text: str) -> dict[int, str]:
    """Split into per-page sections"""
    page_sections = re.split(r'\n={60}\nPAGE (\d+)\n={60}\n', full_text)    # [pre, page_num, content, page_num, content, ...]
    
    pages = {}
    for i in range(1, len(page_sections) -1, 2):
        pg_num = int(page_sections[i])
        content = page_sections[i+1] if i+1 < len(page_sections) else ""
        
        # strip the repeated ====\n line that appears inside some pages
        content = re.sub(r'={60}\n', '', content)
        pages[pg_num] = content.strip()
        
    return pages


def extract_stats(text: str) -> dict:
    """
    Extract the 9 core stats from a stat block.
    
    Stats may have parenthetical armor-modified values like: 5 8(6) 6(4) 3 3 6 6(4) 7 4    
    """
    stat_line_re = re.compile(
        r'(\d+(?:\(\d+\))?)\s+'  # INT
        r'(\d+(?:\(\d+\))?)\s+'  # REF
        r'(\d+(?:\(\d+\))?)\s+'  # DEX
        r'(\d+(?:\(\d+\))?)\s+'  # TECH
        r'(\d+(?:\(\d+\))?)\s+'  # COOL
        r'(\d+(?:\(\d+\))?)\s+'  # WILL
        r'(\d+(?:\(\d+\))?)\s+'  # MOVE
        r'(\d+(?:\(\d+\))?)\s+'  # BODY
        r'(\d+(?:\(\d+\))?)'     # EMP
    )
    # Locate the stat labels line to anchor the search
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


def extract_section(text, start_keyword, end_keywords) -> str:
    """Extract text between start_keyword and the first of end_keywords."""
    start_re = re.compile(re.escape(start_keyword), re.IGNORECASE)
    m = start_re.search(text)
    if not m:
        return ""
    start = m.end()
    end = len(text)
    for keys in end_keywords:
        em = re.compile(re.escape(keys), re.IGNORECASE).search(text, start)
        if em and em.start() < end:
            end = em.start()
    return text[start:end].strip()


def parse_level_rep_hp(text: str) -> dict:
    """Parse level, rep, HP, death save from the NPC header block"""
    result = {}
    # Level pattern: 'level M ini -B oss rep 5 ... HP 40'
    # Normalized: 'level Hardened Boss rep 5 ... HP 40'
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


def parse_role(text: str) -> str:
    """Extract role(s) from stat block."""
    role_m = re.search(r'role\s+(.+?)(?=\n|STATS|stat)', text, re.IGNORECASE | re.DOTALL)
    if role_m:
        role_text = role_m.group(1).strip()
        role_text = re.sub(r'\s+', ' ', role_text)
        return role_text[:150]
    return ""


def parse_weapons(text) -> list:
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


def parse_skills(text) -> str:
    """Extract skills section."""
    skills_start = text.lower().find("skill bases")
    if skills_start == -1:
        return ""
    gear_start = text.lower().find("\ngear\n", skills_start)
    if gear_start == -1:
        gear_start = text.lower().find("gear\n", skills_start)
    cyber_start = text.lower().find("cyberware", skills_start)

    end = len(text)
    for pos in [gear_start, cyber_start]:
        if skills_start < pos < end:
            end = pos

    skills_text = text[skills_start + len("skill bases"):end].strip()
    skills_text = re.sub(r'\s+', ' ', skills_text)
    return skills_text

