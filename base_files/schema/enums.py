"""
Python Enum classes mirroring base_files/schema/enums.yml.

Members are StrEnum so they compare/serialize as plain strings, which keeps
the YAML round-trip simple: a YAML string value such as "EncounterNPC" is
equal to NPCType.EncounterNPC and dumps back to the same string.

Only enums currently used by Base_NPC + Base_Grunt are defined here.
Add others as new prototypes are converted.
"""

from enum import StrEnum
from enum import IntEnum


# =============================================================================
# WEAPONS
# =============================================================================

class RangedWeapons(StrEnum):
    MPistol = "Medium Pistol"
    HPistol = "Heavy Pistol"
    VHPistol = "Very Heavy Pistol"
    SMG = "Submachine Gun"
    HSMG = "Heavy Submachine Gun"
    VHSMG = "Very Heavy Submachine Gun"
    Shotgun = "Shotgun"
    AssaultRifle = "Assault Rifle"
    SniperRifle = "Sniper Rifle"
    Bow = "Bow"
    Xbow = "Cross Bow"
    GLauncher = "Grenade Launcher"
    RLauncher = "Rocket Launcher"

class MeleeWeapons(StrEnum):
    LWeapon = "Light Melee Weapon"
    MWeapon = "Medium Melee Weapon"
    HWeapon = "Heavy Melee Weapon"
    VHWeapon = "Very Heavy Melee Weapon"

class WeaponCategory(StrEnum):
    Std = "Standard"
    Mil = "Military"
    Exo = "Exotic"

class DamageTypes(StrEnum):
    Phys = "Physical"
    Burn = "Burning"
    Chem = "Chemical"   # Poison/acid
    Elec = "Electrical" # Stun/Shock
    EMP = "Electro-magnetic Pulse"  # Shuts down cybernetics unless they have resistance

# =============================================================================
# RARITY / QUALITY
# =============================================================================

class Rarity(StrEnum):
    Poor = "Poor"
    Std = "Standard"
    Excl = "Excellent"
    Icon = "Iconic"

class NPCType(StrEnum):
    EncounterNPC = "EncounterNPC"
    RecurringNPC = "RecurringNPC"
    Vendor = "Vendor"
    QuestGiver = "QuestGiver"
    ContactFixer = "ContactFixer"


class NPCRole(StrEnum):
    Grunt = "Grunt"
    Tough = "Tough"
    Elite = "Elite"
    Mini_Boss = "MiniBoss"
    Boss = "Boss"
    Sniper = "Sniper"
    Assassin = "Assassin"
    Rockerboy_NPC = "Rockerboy_NPC"
    Solo_NPC = "Solo_NPC"
    Netrunner_NPC = "Netrunner_NPC"
    Tech_NPC = "Tech_NPC"
    Medtech_NPC = "Medtech_NPC"
    Media_NPC = "Media_NPC"
    Lawman_NPC = "Lawman_NPC"
    Exec_NPC = "Exec_NPC"
    Fixer_NPC = "Fixer_NPC"
    Nomad_NPC = "Nomad_NPC"
    NamedNPC = "NamedNPC"
    Bodyguard = "Bodyguard"
    Driver = "Driver"


class NPCRarity(StrEnum):
    Mook = "Mook"
    Normal = "Normal"
    Tough = "Tough"
    Elite = "Elite"
    Boss = "Boss"
    HardenedMook = "HardenedMook"
    HardenedLieutenant = "HardenedLieutenant"
    HardenedMiniBoss = "HardenedMiniBoss"
    HardenedBoss = "HardenedBoss"


class Faction(StrEnum):
    # Unaffiliated
    Neutral = "Neutral"
    NCPD = "NCPD"
    Netwatch = "Netwatch"
    Trauma_Team = "Trauma_Team"
    # Mega-corporations
    Arasaka = "Arasaka"
    Militech = "Militech"
    Kang_Tao = "Kang_Tao"
    Biotechnica = "Biotechnica"
    PetraChemical = "PetraChemical"
    SovOil = "SovOil"
    Orbital_Air = "Orbital_Air"
    EuroBank = "EuroBank"
    # Night City gangs
    # Member name renamed for Pythonic compliance; see enums.yml line 299.
    # YAML value normalized to "Sixth_Street" alongside this rename.
    Sixth_Street = "Sixth_Street"
    Animals = "Animals"
    Aldecaldos = "Aldecaldos"
    Barghest = "Barghest"
    Bozos = "Bozos"
    Generation_Red = "Generation_Red"
    Maelstrom = "Maelstrom"
    Moxes = "Moxes"
    Piranhas = "Piranhas"
    Sightseers = "Sightseers"
    Team_Monster = "Team_Monster"
    Tyger_Claws = "Tyger_Claws"
    Valentinos = "Valentinos"
    Voodoo_Boys = "Voodoo_Boys"
    Wraiths = "Wraiths"
    Scavengers = "Scavengers"
    Zoners = "Zoners"
    # Independent
    Solo_Merc = "Solo_Merc"
    Fixer_Independent = "Fixer_Independent"
    Nomad_Clan = "Nomad_Clan"
    Danger_Gal = "Danger_Gal"
    Digital_Divas = "Digital_Divas"
    Network_54 = "Network_54"
    Edgerunner = "Edgerunner"


class AttitudeGroup(StrEnum):
    Friendly = "Friendly"
    Neutral = "Neutral"
    Suspicious = "Suspicious"
    Hostile = "Hostile"
    Fearful = "Fearful"
    Berserk = "Berserk"


class EquipHand(StrEnum):
    Primary = "Primary"
    Offhand = "Offhand"
    TwoHanded = "TwoHanded"
    Holstered = "Holstered"


class Skill(StrEnum):
    # INT-based
    Accounting = "Accounting"
    AnimalHandling = "AnimalHandling"
    Bureaucracy = "Bureaucracy"
    Business = "Business"
    Composition = "Composition"
    Criminology = "Criminology"
    Cryptography = "Cryptography"
    Deduction = "Deduction"
    Education = "Education"
    Gamble = "Gamble"
    LibrarySearch = "LibrarySearch"
    LipReading = "LipReading"
    LocalExpert = "LocalExpert"
    LinguisticsBase = "LinguisticsBase"
    MakeFist = "MakeFist"
    Paramedic = "Paramedic"
    PerceptionINT = "PerceptionINT"
    Science = "Science"
    Tactics = "Tactics"
    TechBase = "TechBase"
    WildernessSurvival = "WildernessSurvival"
    # REF-based
    Athletics = "Athletics"
    Brawling = "Brawling"
    Contortionist = "Contortionist"
    DriveLandVehicle = "DriveLandVehicle"
    EducationREF = "EducationREF"
    Evasion = "Evasion"
    Initiative = "Initiative"
    MartialArts = "MartialArts"
    MeleeCombat = "MeleeCombat"
    Perception = "Perception"
    Pilot_AerialVehicle = "Pilot_AerialVehicle"
    Pilot_SeaVehicle = "Pilot_SeaVehicle"
    RidingHorse = "RidingHorse"
    Stealth = "Stealth"
    Tracking = "Tracking"
    # DEX-based
    Acrobatics = "Acrobatics"
    Archery = "Archery"
    ConcealRevealObject = "ConcealRevealObject"
    Handgun = "Handgun"
    HeavyWeapons = "HeavyWeapons"
    ShoulderArms = "ShoulderArms"
    Autofire = "Autofire"
    Dodge = "Dodge"
    SleightOfHand = "SleightOfHand"
    # TECH-based
    AirVehicleTech = "AirVehicleTech"
    BasicTech = "BasicTech"
    Cybertech = "Cybertech"
    Demolitions = "Demolitions"
    Electronics_SecurityTech = "Electronics_SecurityTech"
    FirstAid = "FirstAid"
    LandVehicleTech = "LandVehicleTech"
    MedicalTech = "MedicalTech"
    PaintDraw = "PaintDraw"
    Photography_Film = "Photography_Film"
    PickLock = "PickLock"
    PickPocket = "PickPocket"
    SeaVehicleTech = "SeaVehicleTech"
    Surgery = "Surgery"
    Weaponstech = "Weaponstech"
    # COOL-based
    Bribery = "Bribery"
    ConversationCool = "ConversationCool"
    HumanPerception = "HumanPerception"
    Interrogation = "Interrogation"
    Intimidation = "Intimidation"
    Persuasion = "Persuasion"
    PersonalGrooming = "PersonalGrooming"
    Streetwise = "Streetwise"
    Trading = "Trading"
    WardrobeStyle = "WardrobeStyle"
    # WILL-based
    Concentration = "Concentration"
    ConversationWILL = "ConversationWILL"
    ResistTortureDrugs = "ResistTortureDrugs"
    # BODY-based
    Athletics_BODY = "Athletics_BODY"
    EnduranceSTR = "EnduranceSTR"
    # EMP-based
    Acting = "Acting"
    Dancing = "Dancing"
    Forgery = "Forgery"
    LibrarySearchEMP = "LibrarySearchEMP"
    Performance = "Performance"
    PlayInstrument = "PlayInstrument"
    SeductionEMP = "SeductionEMP"
    SocialEMP = "SocialEMP"
    Wardrobe_EMP = "Wardrobe_EMP"

# =============================================================================
# CULTURAL ORIGIN
# =============================================================================

class CulturalOrigins(StrEnum):
    NA =    "North American"
    SCA =   "South Central American"
    WEUR =  "Western European"
    EEUR =  "Eastern European"
    MENA =  "Middle Eastern North African"
    SAFR =  "SubSaharan African"
    SASN =  "South Asian"
    SEASN = "South East Asian"
    EASN =  "East Asian"
    OCN =   "Oceanian"
    NOMA =  "Nomad American"
    NOMEUR = "Nomad European"
    NOMASN = "Nomad Asian"

# =============================================================================
# CYBERWARE
# =============================================================================

class CyberwareSlots(StrEnum):
    Neural = "Neural ware"
    Optics = "Cyber optics"
    Audio = "Cyber audio"
    RArm = "Right Arm"
    LArm = "Left Arm"
    RLeg = "Right Leg"
    LLeg = "Left Leg"
    SubDermal = "Subdermal"
    Internal = "Internal Organs"

class CyberwareTypes(StrEnum):
    Passive = "Passive"
    Active = "Active"
    NeuralOS = "Neural OS"
    Weapon = "Cyber Weapon"
    Fashion = "Fashion ware"

# =============================================================================
# ARMOR
# =============================================================================

class ArmorTypes(IntEnum):
    """The integers refer to the specific Stopping Power (SP) value for each
        type of armor.
    """
    Leathers = 4
    KevlarVest = 7
    LightArmorJack = 11
    BodySuit = 11
    MedArmorJack = 15
    HeavyArmorJack = 18
    FlakVest = 15
    MetalGearHeavy = 12
    LinedCoat = 12
    Shield = 10

# =============================================================================
# STATUS EFFECTS
# =============================================================================

class StatusEffectTypes(StrEnum):
    Stun =      "Stunned"       # lose next action
    Burn =      "Burning"       # Thermal tick damage/round
    Poison =    "Poisoned"      # Chemical tick damage/round
    EMP =       "EMPed"         # Cyberware disabled for duration
    Suppress =  "Suppressed"    # Pinned, must spend action to move
    Blind =     "Blinded"       # -4 to all attack and perception rolls
    Bleed =     "Bleeding"      # Lose HP at the end of each round, First Aid or Trauma Pack removes