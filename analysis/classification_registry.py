"""Maintained entity registries for deterministic transaction classification.

Aliases are normalized and matched on token boundaries by
``analysis.payee_matcher``. Keep generic financing words out of the named
registries; they are evidence signals, not lender identities.

The group tables between the GENERATED markers are rendered by
``tools/build_lender_registry.py`` from ``docs/lender-registry-ledger.json``,
the curated lender ledger (contract C10). The evidence for every entity is in
``docs/lender-registry-evidence.md``.
"""
from __future__ import annotations

from dataclasses import dataclass

from .description_text import normalize_transaction_description

# --- BEGIN GENERATED: tools/build_lender_registry.py ---
# Rendered by tools/build_lender_registry.py from docs/lender-registry-ledger.json (contract C10).
# Never edit by hand: change the ledger, then run python -m tools.build_lender_registry --write.

#: Lenders: MCA and revenue-based funders, equipment financing.
LENDER_ALIASES: dict[str, tuple[str, ...]] = {
    "1DC Funding LLC": ("1 DC FUNDING",),
    "1st Merchant Funding": ("1ST MERCHANT FUNDING",),
    "2M7 Financial Solutions": ("2M7 FINANCIAL", "2M7FINANCIALSOL", "2M7FINAN"),
    "8fig": ("8FIG",),
    "ACA Funding Group LLC": ("ACA FUNDING GROU", "ACA FUNDING GROUP"),
    "AmeriMerchant": ("AMERIMERCHANT",),
    "Amur Equipment Finance, Inc": ("AMUR EF", "AMUR EQUIPMENT FINANC", "AMUR EQUIPMENT"),
    "App Funding Beta LLC": ("APP FUNDING BETA",),
    "ARF Financial, LLC": ("ARF FINANCIAL LL", "ARF FINANCIAL", "ARF FUNDING", "ARF LOAN PAYOUT"),
    "Arundel Capital Corporation": ("ARUNDEL CAPITAL",),
    "Ascentium Capital": ("ASCENTIUMCAPITAL", "ASCENTIUM CAPITAL"),
    "Aspira Capital Group, LLC": ("ASPIRA CAPITAL",),
    "Aspire Funding Platform LLC": ("ASPIREFUNDING", "ASPIRE FUNDING PLATFORM"),
    "Aventus Fund LLC": ("AVENTUSFUNDLLC", "AVENTUS FUND LLC"),
    "Balboa Capital": ("BALBOA CAPITAL",),
    "Beckham Capital LLC": (
        "BECKHAMCAPITALLL",
        "BECKHAMCAPITL LL",
        "BECKHAMCAPIT LL",
        "BECKHAMCAPITL",
        "BECKHAMCAPIT",
    ),
    "BHG Financial": ("BHG FINANCIAL", "BANKERS HEALTHCARE GROUP", "BANKERS HEALTHCARE", "BANKERS HEALTHCA"),
    "BITTY ADVANCE": ("BITTY ADVANCE",),
    "Biz Capital Miami": ("BIZ CAPITAL MIAM", "BIZ CAPITAL MIAMI"),
    "Bizcap Canada": ("BIZCAP",),
    "BIZFUND": ("BIZFUND",),
    "BIZPOINT CAPITAL": ("BIZPOINT CAPITAL", "BIZPOINT CAP"),
    "Blue Bridge Financial": ("BLUE BRID", "BLUE BRIDG"),
    "Blue Chip Leasing Corporation": ("BLUE CHIP LEASING",),
    "BMO Transportation and Vendor Finance": ("BMO TRANSPORTATION FINANCE", "BMO VENDOR FINANCE"),
    "BREAKOUT CAPITAL": ("BREAKOUT CAPITAL", "BREAKOUT FINANCE"),
    "Breeze Capital LLC": ("BREEZE CAPITAL",),
    "Bretton Capital": ("BRETTON CAPITAL",),
    "BriteCap Financial": ("BRITECAP FINANCI", "BRITECAP"),
    "Business Credit & Capital": ("BCCFUND",),
    "ByzFunder": ("BYZFUNDER", "BYZFLEX", "BYZFUN DER FUNDIN", "BYZFUNDER NY"),
    "CAN Capital": ("CAN CAPITAL", "CAN CAPITAL PREAUTHPMT", "PREAUTHPMT CAN CAPITAL", "WEBBANK CANCAP"),
    "CanaCap": ("CANACAP", "CANA CAP", "CANAOAP", "CANAC4P"),
    "Canon Financial Services": ("CANON FINANCIAL",),
    "Capital Advance": ("BUSINESS PAD CAPITAL ADVANCE",),
    "Capybara Capital LLC": ("CAPYBARA",),
    "CashArc LLC": ("CASHARC LLC", "CASH ARC LLC"),
    "Caterpillar Financial Services Corporation": ("CATERPILLAR FINA", "CATERPILLAR FINANCIAL"),
    "CBSC Capital Inc": ("CBSC CAPITAL IN",),
    "Cedar Advance LLC": ("CEDAR ADVANCE",),
    "Centra Funding, LLC": ("CENTRA FUNDING",),
    "CFGMS": ("CFGMS", "CFG MERCHANT SOLUTIONS", "MC 844 662 3467", "CFG MERCHANT SOL", "CFG MERCHANT SO"),
    "Chance Capital, Inc": ("CHANCE CAPITAL", "CHANCE CAPITAL INC", "UTAH BIZ LOANS"),
    "CHANNEL PARTNERS": ("CHANNEL PARTNERS",),
    "Cityline Funding Group Inc": ("CITYLINE FUNDING",),
    "CLEARCO": ("CLEARCO",),
    "Clearfund Solutions LLC": ("CLEARFUND", "CLEARFUND SOLUT", "CLEARFUND SOLUTIONS"),
    "Clicklease LLC": ("CLICKLEASE",),
    "CMCA Finance": ("CMCA FINANCE", "CMCA FINANCE BUS", "CMCAFINANCE", "CMCA F1NANCE"),
    "Coconut Funding Corporation": ("COCONUTFUNDINGCO", "COCONUT FUNDING"),
    "CREDIBLY": ("CREDIBLY", "RETAIL CAPITAL"),
    "Cromwell Capital LLC": ("CROMWELL CAPITAL",),
    "Crossroads Equipment Lease & Finance, LLC": ("CROSSROADS EQUIP",),
    "Crown Credit Company": ("CROWN CREDIT CO", "CROWN CREDIT COMPANY"),
    "CWB Maxium Financial": ("CWB MAXIUM", "MAXIUM FINANCIAL"),
    "CWB National Leasing": ("CWB NATIONAL LEASING", "NATIONAL LEASING GROUP"),
    "Daimler Truck Financial Services": ("DAIMLERTRUCKFIN", "DAIMLER TRUCK FINANCIAL"),
    "Dakota Financial, LLC": ("DAKOTA FINANCIAL LLC",),
    "De Lage Landen": ("DE LAGE LANDEN", "DELAGELANDEN", "DLL FINANCE", "LEASEDIRECT"),
    "Delta Bridge Funding": ("DELTA BRIDGE FUNDING", "CLOUDFUND"),
    "Dext Capital LLC": ("DEXT CAPITAL",),
    "Diamond Advance": ("DIAMOND ADVANCE", "DIAMOND ADVANCES"),
    "Direct Capital Corporation": ("DIRECT CAPITAL",),
    "DLP Funding LLC": ("DLP FUND", "DLP FUNDING", "DLPBUS FUND"),
    "DMS Equities LLC": ("DMS EQUITIES LLC", "DMS EQUITIES"),
    "Driven Financial Technologies Corporation": ("DRIVEN FINANCIA",),
    "East Shore Equities LLC": ("ESENOW", "EAST SHORE EQUITIES", "EAST SHORE EQU"),
    "Econolease": ("VLFC ECONOLEASE", "VLFC ECONO LEASE", "ECONOLEASE"),
    "Edge Capital": ("CRC EDGE",),
    "Elect Capital": ("ELECT CAPITAL", "ELECT CANADA"),
    "Elevate Funding": ("ELEVATE FUNDING",),
    "EMINENT FUNDING": ("EMINENT FUNDING",),
    "Emmy Capital Group": ("EMMYCAPITALGROUP", "EMMY CAPITAL GROUP", "EMMY CAPITAL"),
    "EN OD Capital, LLC": ("EN OD CAPITAL",),
    "Entegra Capital LLC": ("ENTEGRA CAPITAL",),
    "Equirex Leasing": ("EQUIREX",),
    "Essentia Funding": ("ESSENTIA FUNDING",),
    "EVEREST BUSINESS FUNDING": (
        "EVEREST BUSINESS FUNDING",
        "EBFUNDING",
        "EBFH TEXAS",
        "EBF HOLDINGS",
        "EBF DEBIT",
        "HOLDINGS EBF",
    ),
    "EXPANSION CAPITAL": (
        "EXPANSION CAPITAL",
        "EXPANSION CAPITA",
        "EXPANSION CAPITAL FUNDING",
        "EXPANSION CAPITA FUNDING",
        "EXP CAPITAL",
        "EXPANSIONCAP",
        "EXPANSIONCAPPMTS",
        "EXPANSIONCAPFEE",
    ),
    "Express Capital Funding, Inc.": ("EXPRESSCAPITAL",),
    "Express Tech-Financing, LLC d/b/a Currency": ("EXPRESS TECH FIN",),
    "FairFigure": ("FAIRFIGURE CARD", "FAIRFIGURE LIFT"),
    "Family Funding Group": ("FAMILY FUNDING G", "FAMILY FUNDING GROUP"),
    "Fast Business Cash Funding Group, LLC": ("FAST BUSINESS CA",),
    "FC Advance": ("FCADVANCE",),
    "FC Capital Holdings, LLC dba FundCanna": ("FC CAPITAL HOLDI",),
    "FC Marketplace, LLC": ("FC MARKETPLACE",),
    "Fenix Capital Funding, LLC": ("FENIX CAPITAL",),
    "Financial Pacific Leasing, Inc": ("FINANCIAL PACIFI", "FINANCIAL PACIFIC"),
    "Finova Capital LLC": ("FINOVA CAPITAL",),
    "Fintegra, LLC": ("FINTEGRA",),
    "FinWise Bank Equipment Leasing": ("FINWISE LEASE",),
    "Firstline Advance LLC": ("FIRSTLINE ADVANC", "FIRSTLINE ADVANCE"),
    "Flash Advance": ("FLASH ADVANCE", "DIRCT MER COL", "DIRECT MERCHANTS FUNDING", "DIRECT MERCHANTS"),
    "Fleet Financial": ("FLEET FINANCIAL",),
    "Flex Capital": ("FLEX CAPITAL",),
    "Flexibility Capital, Inc.": ("FLEXIBILITY CAPI", "FLEXIBILITY CAPITAL"),
    "FORA FINANCIAL": ("FORA FINANCIAL", "FORAFINANCIAL"),
    "Foretrust Funding": ("FORETRUSTFUNDING",),
    "Forward Financing": (
        "FORWARD FINANCING",
        "FORWARD FINANCIN",
        "FORWARDFINANCIN",
        "FORWARD FINANCINFF",
        "FORWARDFINANCING",
        "FORWARD FIN",
        "FORWARDFINUSA",
        "FORWARD FIN USA",
        "FORWARD FINANCING USA",
    ),
    "Forward Funding": ("FORWARD FUNDING",),
    "Fox Funding Group, LLC": ("FOX FUNDING GRP", "FOX FUNDING GROUP", "FOXFUNDINGGROUPL"),
    "Fuji Funding LLC": ("FUJI FUND",),
    "Fulton Leasing Company": ("FULTON BANK LEASING", "LEASE PMTS FULTON LEASING"),
    "Fund Me Fast LLC": ("FUND ME FAST LLC",),
    "FUNDATION": ("FUNDATION", "FUNDATION GROUP"),
    "FundEx": ("FUNDEX NYC", "FUNDEX NYC INC"),
    "Fundible": ("FUNDIBLE",),
    "FUNDIFI": ("FUNDIFI", "FUNDFI", "FUNDFI CANADA", "FUNDFICANADA"),
    "Funding Futures LLC": ("FUNDING FUTURES",),
    "FundLink USA": ("FUNDLINKUSA", "FUNDLINK USA"),
    "Fundo": ("FUNDO",),
    "Fundry LLC": ("FUNDRY",),
    "FUNDWORKS": (
        "THE FUNDWORKS LLC",
        "THE FUND WORKS LLC",
        "FUNDWORKS LLC",
        "THE FUND WORKS",
        "THE FUNDWORKS",
        "FUND WORKS",
        "FUNDWORKS",
        "FUNDOWRKS",
        "FUNDOWRK",
        "FUND WRKS",
        "FUNDWK",
    ),
    "Garden Funding LLC": ("GARDEN FUNDING",),
    "GFE": ("UFCE", "GLOBAL FUNDING EXPERTS", "UNITED FIRST CAPITAL EXPERTS", "UNITED FIRST LLC"),
    "Giggle Finance": ("GIGGLE FINANCE",),
    "GOAT ADVANCE LLC": ("GOAT ADVANCE",),
    "Good Funding, LLC": ("GOOD FUNDING LLC",),
    "Goose Funding": ("GOOSE FUNDING",),
    "GreatAmerica Financial Services Corporation": ("GREATAMERICA FI", "GREATAMERICA FINANCIAL"),
    "GREENBOX CAPITAL": ("GREENBOX CAPITAL", "GREENBOX CAPITA"),
    "Greyhaven Partners, LLC": ("GREYHAVEN PARTNE", "GREYHAVEN PARTNERS"),
    "H.E.C. Leasing, LLC": ("HEC LEASING",),
    "Highland Hill Capital": ("HIGHLAND HILL CA", "HIGHLAND HILL CAPITAL"),
    "Hill Run Capital": ("HILLRUNCAPITAL", "HILLRUN CAPITAL"),
    "Honest Funding LLC": ("HONESTFUNDINGLLC", "HONEST FUNDING"),
    "Hop Capital": ("HOP CAPITAL LLC",),
    "Hunter Caroline": ("HUNTER CAROLINE",),
    "iCapital Financial Services Ltd": ("ICAPITAL FINANC",),
    "IDEA FINANCIAL": ("IDEA FINANCIAL", "IDEAFINANCIAL", "IDEALOAN", "IDEA 247 INC"),
    "IOU FINANCIAL": ("IOU FINANCIAL", "IOU CENTRAL"),
    "Iruka Capital Group LLC": ("IRUKA CAPITAL",),
    "Isuzu Finance of America": ("ISUZU FINANCE",),
    "Itria Ventures LLC": ("ITRIA VEN", "ITRIA VENTURES"),
    "John Deere Financial": ("JOHN DEERE FINANCIAL", "JOHN DEERE FINA", "DEERE CREDIT SER", "DEERE CREDIT"),
    "Journey Capital": ("JOURNEY CAPITAL ONDECK", "JOURNEY ONDECK", "JOURNEY CAPITAL"),
    "Kalamata Capital Group": ("KALAMATACAPITAL", "KALAMATA CAPITAL"),
    "KAPITUS": ("KAPITUS", "STRATEGIC FUNDING", "SERVICING BY KAP"),
    "Katan Capital LLC": ("KATAN CAPITAL",),
    "Key Equipment Finance": ("KEY EQUIPMENT FINANCE", "KEY EQUIP FINANCE", "KEY EQUIP FIN"),
    "Keystone Equipment Finance Corp": ("KEYSTONEEFC",),
    "Kinetic Leasing, Inc": ("KINETIC LEASING",),
    "KM Capital Corp": ("KM CAPITAL CORP", "KM CAPITAL C"),
    "Komatsu Financial Limited Partnership": ("KOMATSU FINANCIA", "KOMATSU FINANCIAL"),
    "Kubota Canada Ltd.": ("EQUIPMT LEASE LOAN PYMT KUBOTA",),
    "Kubota Credit Corporation U.S.A.": ("KUBOTA CREDIT", "KUBOTA CREDIT CO"),
    "Lease Corporation of America": ("LEASE CORPORATION OF AMERICA", "LEASE CORP OF AMERICA"),
    "Lease Services (PEAC Solutions)": (
        "LEASE SERVICES ACH PYMTS",
        "LEASE SERVICES DES ACH PYMTS",
        "LEASE SERVICES BILLPAY",
        "LEASE SERVICES LEASE PYMT",
        "LEASE SERVICES TYPE ACH PYMTS",
        "LEASE SERVICES TYPE WEB PAY",
        "LEASESVCS",
        "LEASE SERVICES WEB PAY",
    ),
    "Legend Advance Funding II, LLC dba Legend Funding": ("LEGENDADVFUNDING", "LEGEND ADVANCE FUNDING"),
    "Lendero LLC": ("LENDERO", "LENDERO LLC"),
    "LENDINI": ("LENDINI", "FUNDING METRICS", "FDM001", "FNDGMTRCS"),
    "Lendr": ("LENDR",),
    "LG FUNDING": ("LG FUNDING", "LG FUNDING LLC", "LGFUNDINGLLC"),
    "LIBERTAS FUNDING": ("LIBERTAS FUNDING",),
    "Likety Capital LLC": ("LIKETY CAP",),
    "Lily Advance": ("LILY ADVANCE",),
    "Limelight Advance LLC": ("LIMELIGHT ADVANCE", "LIMELIGHT TYPE"),
    "LiteFund Solutions LLC": ("LITEFUND", "LITEFUND SOLUTIO", "LITEFUND SOLUTIONS"),
    "Loot Financial Services": ("LOOT", "LOOT LOOT"),
    "Mack Financial Services": ("MACK FINANCIAL", "MACK FINANCIAL BUS"),
    "Madison Advance LLC": ("MADISON ADVANCE",),
    "Magical Business": ("MAGICAL BUSINESS",),
    "Mahindra Finance USA LLC": ("MAHINDRA FINANCE", "MAHINDRA FINANCE PORTAL"),
    "Mako Funding LLC": ("MAKO FUNDING",),
    "Mantis Funding LLC": ("MANTISFUND", "MANTIS FUNDING"),
    "MCK Business Loans": ("MCKBUSINESSLOANS",),
    "McKenzie Capital LLC": ("MCKENZIE CAPITAL",),
    "Meged Funding Group": ("MEGED1", "MEGED FUNDING"),
    "Merchant Growth Ltd": ("MERCHANT GROWTH", "INVESTMENT MERCHANT GROWTH FUND"),
    "Merit Business Funding": ("MERIT BUSINESS FUNDING",),
    "MHB Financial": ("MHB FINANCIAL",),
    "MicroAdvance": ("MICROADVANCEFUND",),
    "Millstone Funding, Inc": ("MILLSTONE FUNDIN",),
    "Milvado Capital LLC": ("MILVADO CAPITAL",),
    "Mint Funding Inc": ("MINT FUNDING",),
    "Mission Financial Services Corporation": ("MISSION FINANCIAL ANAHEIM",),
    "Mitsubishi HC Capital America, Inc.": ("MITSUBISHI HCC",),
    "Mitsubishi HC Capital Canada Leasing, Inc": ("MHCCL", "MHCCL RLS LOY"),
    "Mitsubishi HC Capital Canada, Inc": ("MHCCA", "MHCCA RLS LOY"),
    "ML Factors Funding LLC": ("ML FACTORS",),
    "MNY Capital LLC": ("MNY CAPITAL", "MNY CAPITAL LLC"),
    "Montium Advance": ("MONTIUM ADVANCE",),
    "Mount Valor Capital": ("MOUNT VALOR CAPI", "MOUNT VALOR CAPITAL"),
    "Mr. Advance LLC": ("MR ADVANCE",),
    "Mulligan Funding, LLC": ("MULLIGAN FUNDING",),
    "NATIONAL FUNDING": ("NATIONAL FUNDING", "NFAS3", "NFSPV1 COLLECTION"),
    "Navitas Credit Corp": ("NAVITAS CREDIT CORP", "NAVITAS CREDIT C", "NAVITAS CREDIT"),
    "NEC Financial Services, LLC": ("NEC FINANCIAL",),
    "New York Tribeca Group": ("NEW YORK TRIBECA", "NEW YORK TRIBECA GROUP"),
    "NewCo Capital Group": ("NEWCO CAPITAL G", "NEWCO CAPITAL GROUP"),
    "NewLane Finance": ("NEWLANE",),
    "Newport Business Capital, Inc": ("NEWPORT BUSINESS NEWPORT BC",),
    "Nexi": ("NEXI", "NEXI FUNDAMENTAL", "FUNDAMENTAL CAPITAL SPE"),
    "Nexus Finance": ("NEXUS FINANCE",),
    "Nitro Advance Inc": ("NITRO ADVANCE",),
    "NMEF": ("NMEF", "NMEF FUNDING", "NMEF 2023 A", "NMEF FUNDING LLC"),
    "North Funding": ("NORTH FUNDING",),
    "North Star Leasing": ("PB NORTHSTAR LEA", "NORTHSTAR LEA"),
    "Northland Capital Financial Services, LLC": ("NORTHLAND CAP",),
    "Novus Capital Funding II LLC": ("NOVUSCAPITAL II", "NOVUS CAPITAL FU", "NOVUS CAPITAL FUNDING"),
    "Oak Capital Inc": ("OAK CAPITAL ONLINE",),
    "Olympus Business Capital": ("OLYMPUS BUSINESS", "OLYMPUSBUS", "OLYMPUS LENDING"),
    "ONDECK": ("ONDECK",),
    "One River Group Inc": ("ONE RIVER FUND", "ONE RIVER GROUP", "ONE RIVER SERVICES", "ONE RIVER FUNDING"),
    "OneView Finance": ("ONEVIEW FINANCE",),
    "Overton Funding LLC": ("OVERTONFUNDING", "OVERTON FUNDING"),
    "PACCAR Financial Corp.": ("PACCAR FINANCIAL",),
    "Paladin Funding Group": ("PALADIN FUNDING",),
    "Panthers Capital LLC": ("PANTHERS C",),
    "PAR FUNDING": ("PAR FUNDING",),
    "Parkside Funding Group LLC": ("PARKSIDE FUNDING",),
    "PAYABILITY": ("PAYABILITY",),
    "Pipe Technologies Inc": (
        "PIPE TECHNOLOGIES IN",
        "PIPE TECHNOLOGIES INC",
        "PIPE ADVANCE",
        "PIPE CAPITAL",
        "PIPE TECHNOLOGIE",
    ),
    "Pitney Bowes Global Financial Services, LLC": ("PBLEASING",),
    "Pitney Bowes of Canada Ltd": ("PITNEYBOWES LEA",),
    "PNC Equipment Finance": ("PNC EQUIPMENT FINANCE", "PNC EQUIPMENT"),
    "Powercap Funding, Inc": ("POWERCAPFUNDINGI",),
    "Premium Merchant Funding": ("PREMIUMMERCHANTF", "PREMIUM MERCHANT FUNDING"),
    "Prosperity Funding Group LLC": ("PROSPERITY FUNDING GROUP",),
    "Purple Tree Funding LLC": ("PURPLE TREE FUND", "PURPLE TREE FUNDING"),
    "QM Advance": ("QMADVANCE",),
    "Quadient Leasing USA, Inc": ("QUADIENT LEASING", "NEOPOST LEASING"),
    "QUARTERSPOT": ("QUARTERSPOT", "QUARTER SPOT"),
    "Queen Funding, LLC": ("QUEEN FUNDING",),
    "RAPID FINANCE": ("RAPID FINANCE", "RAPIDFINANCE", "SBFS LLC", "SBFS BASEPOINT", "SBFS FLEX"),
    "Raymond Leasing Corporation": ("RAYMOND LEASING",),
    "Regium Funding": ("REGIUM FUNDING",),
    "RELIANT FUNDING": ("RELIANT FUNDING",),
    "RETRO ADVANCE": ("RETRO ADVANCE INC", "RETROADVANCEINC", "RETRO ADVANCE", "RETROADVANCE"),
    "Revenued LLC": ("REVENUED",),
    "Rockstone Funding Group Inc": (
        "ROCKSTONE FUNDIN",
        "ROCKSTONE FUNDING",
        "ROCKSTONE FUNDING GROUP",
        "CREDORA CAPITAL",
    ),
    "Rook Bristol Financial LLC": ("ROOK BRISTOL FINANCIAL", "ROOK BRISTOL FI"),
    "Royal Funding Group": ("ROYAL FUNDING GR",),
    "SBG Funding": ("SBG FUNDING",),
    "Seamless Capital Group, Inc": ("SEAMLESS CAPITAL",),
    "Secure Funding Source LLC": ("SECURE FUNDING SOURCE",),
    "Sheaves Capital": ("SHEAVES CAPITAL",),
    "Sheffield Financial": ("SHEFFIELD FIN", "SHEFFIELD FI"),
    "Shield Funding": ("SHIELD FUNDING",),
    "Simply Capital": ("SIMPLY CAPITAL",),
    "Simply Funding LLC": ("SIMPLY FUNDING", "SIMPLY2"),
    "Slate Advance LLC": ("SLATE ADVANCE",),
    "Slim Business Funding LLC": ("SLIM BUSINESS FU", "SLIM BUSINESS FUNDING"),
    "Small Business Advance LLC": ("SMALL BUSINESS ADVANCE LLC",),
    "Snap-on Credit": ("SNAP ON CREDIT",),
    "Sound Advance LLC": ("SOUND ADVANCE L", "SOUND ADVANCE LLC"),
    "Spartan Capital Group": ("SPARTAN CAPITAL", "SPARTAN BUSINESS SOLUTION", "SPARTAN CAP SPV1"),
    "Specialty Capital, LLC": ("SPECIALTY CAP", "SPECIALTY CAPITA", "SPECIALTY CAPIT"),
    "Stearns Bank N.A. equipment leasing": ("STEARNS LEASING", "AUTH PAYME STEARNS LEASING"),
    "Stride Capital Corp": ("STRIDE CAPITAL",),
    "Swift Funding Source, Inc": ("SWIFT FUNDING",),
    "Tandem Finance, Inc": ("TANDEM FINANCE",),
    "Targeted Lending Co., LLC": ("TARGETED LENDING",),
    "TFG Financial Corporation": ("TFG FINANCIAL CORPORATION",),
    "The LCF Group, Inc": ("LCF", "LCFGROUPIN", "LCFGROUPINC"),
    "THORO CORP": ("THORO CORP",),
    "Thriveway Funding Group, LLC": ("THRIVEWAYFUNDING", "THRIVEWAY FUNDING"),
    "TIAA Commercial Finance, Inc.": ("TIAA COMM FINANC",),
    "Timeless Funding LLC": ("TIMELESS FUNDING",),
    "TimePayment Corp": ("TIMEPAYMENT", "TIMEPAYMENTCORP"),
    "Top Choice Financial, LLC": ("ORIG CO NAME TOP CHOICE", "TOP CHOICE FINANCIAL"),
    "Torro Funding LLC": ("GOTORRO", "TORRO HOLDINGS", "TORRO FUNDING"),
    "Toyota Commercial Finance": ("TOYOTA COMMERCIA",),
    "Travelers Finance Ltd": ("TRAVELERS FINANCE", "TRAVELERS LEASING"),
    "True Advance Funding, Inc": ("TRUEADVANCE", "TRUE ADVANCE FUNDING"),
    "U.S. Bank Equipment Finance": ("USBEQUIPFINANCE", "US BANK EQUIPMEN"),
    "Uncapped": ("UNCAPPED LTD", "WEAREUNCAPPED", "UNCAPPED TECHNOLOGIES"),
    "Unique Funding Solutions LLC": ("UNIQUE FUNDING S", "UNIQUE FUNDING SOLUTIONS"),
    "Univest Capital, Inc": ("UNIVEST CAPITAL",),
    "Uplyft Capital": ("UPLYFT CAPITAL",),
    "Urus Funding LLC": ("URUS FUNDING", "URUS FUNDING RENEWAL"),
    "Vader Servicing, LLC d/b/a Vader Mountain Capital": ("VADER",),
    "Vehicle Lenders Group LLC d/b/a TruckLenders USA": ("VECHICLE LENDERS",),
    "VELOCITY CAPITAL": ("VELOCITY CAPITAL",),
    "VitalCap Fund": ("VITALCAP FUND",),
    "Volvo Financial Services": ("VOLVO FINANCIAL", "VOLVO FINANCIAL BUS ENT"),
    "VOX Funding": ("VOX FUNDING",),
    "Wayflyer": ("WAYFLYER",),
    "Wells Fargo Equipment Finance": (
        "WELLS FARGO EQU",
        "WELLS FARGO EQUI",
        "WELLS FARGO FINANCIAL LEASING",
        "WELLS FARGO EQUIPMENT FINANCE",
    ),
    "Wide Merchant Investment, Inc": ("WIDE MERCHANT",),
    "Woodmere Capital LLC": ("WOODMERE CAPITAL",),
    "World Global Capital LLC": ("WORLD GLOBAL CAPITAL", "WORLD GLOBAL CAP"),
    "X Capital Group Corp": ("X CAPITAL",),
    "Xerox Financial Services LLC": ("XEROX FINANCIAL",),
    "Xpedite Leasing Inc.": ("XPEDITE LEASING",),
    "Yellow Iron Lending, LLC": ("YELLOW IRON LEND", "YELLOW IRON LENDING"),
    "YELLOWSTONE CAPITAL": ("YELLOWSTONE CAPITAL",),
    "Zlur Funding LLC": ("ZLUR FUNDING",),
    "Zuccala Capital": ("ZUCCALA CAPITAL",),
}

#: Alternative positions.
ALTERNATIVE_POSITION_ALIASES: dict[str, tuple[str, ...]] = {
    "Accion Opportunity Fund Community Development": ("ACCION OPPORTUNITY FUND",),
    "AFFIRM": ("AFFIRM", "AFFIRMCOM", "AFFIRM COM", "AFFIRM PAY", "AFFIRM CANADA", "AFFIRMCARD", "SP AFF"),
    "Afterpay": ("AFTERPAY",),
    "AgSouth Farm Credit, ACA": ("AGSOUTH AUTODRAFT",),
    "Amazon Capital Services, Inc": ("AMAZON CAPITAL SERVICES",),
    "American Express Loans": (
        "AMERICAN EXPRESS LOAN",
        "AMERICAN EXPRESS BUSINESS LOAN",
        "AMERICAN EXPRESS DES LOAN",
    ),
    "American First Finance, LLC": ("AMERICAN FIRST FINANCE", "AMERICAN FIRST FINANC"),
    "Aqua Finance, Inc": ("AQUA FINANCE",),
    "BDC": ("BDC", "BUSINESS DEVELOPMENT BANK OF CANADA", "BANQUE DEVELOPPEMENT DU"),
    "BILL Invoice Financing": ("BILL INVOICE FIN", "BILL FINANCING"),
    "BREAD DISB DB (Bread Financial)": ("BREAD DISB DB",),
    "CAPITAL INFUSION": ("CAPITAL INFUSION", "CAP INFUSION"),
    "CBDC Central PEI": ("CBDC CENTRAL PEI",),
    "CBDC Northumberland Inc": ("CBDC NORTHUMBERLAND", "CBDC NORTHUMBER"),
    "CDC SMALL BUSINESS": ("CDC SMALL BUSINESS", "CDC SMALL BUS"),
    "Cherry Technologies, Inc.": ("CHERRY TECHNOLOGIES", "CHERRY TECHNOLOG", "CHERRY TECHNOL", "CHERRYPAY"),
    "Credit Key": ("CREDIT KEY",),
    "DoorDash Capital": ("DOORDASH CAPITAL",),
    "Fairstone Retail Financing": ("FAIRSTONE RETAIL FINANCING",),
    "Farm Credit East, ACA": ("FARM CREDIT EAST",),
    "Finance PEI": ("FINANCE PEI",),
    "Financeit Canada Inc.": ("FINANCEIT",),
    "Flexible Finance, Inc. (Flex)": ("FLEXIBLE FINANCE", "GETFLEX"),
    "GreenSky": ("GREENSKY",),
    "HASCAP loan": ("BDC HASCAP",),
    "INTUIT FINANCING": ("INTUIT FINANCING", "WEBBANK INTUIT"),
    "Jobber Capital": ("JOBBER CAPITAL",),
    "Klarna Inc": ("KLARNA", "TRUEACCORD KLARNA"),
    "LendCare Capital Inc": ("LENDCARE",),
    "Lendistry (B.S.D. Capital, Inc.)": ("LENDISTRY",),
    "Liberis US Inc": ("LIBERIS", "LIBERIS US INC"),
    "LiftFund, Inc.": ("LIFTFUND",),
    "Lightspeed Capital": ("LSPD CAPITAL",),
    "Medallion Bank": ("MEDALLION BANK",),
    "Mepco Finance Corporation": ("MEPCO",),
    "Mindbody Capital": ("MINDBODY CAPITAL",),
    "Mountain BizCapital, Inc": ("MOUNTAIN BIZCAPI",),
    "Newtek Small Business Finance, LLC": ("NEWTEK S BUS", "NEWTEK SMALL BUSINESS FINANCE"),
    "Northeast Bank": ("NORTHEAST BANK DES SBA PYMT", "SBA PYMT NORTHEAST BANK"),
    "Parafin, Inc.": ("PARAFIN", "PARAFIN INC"),
    "PAYPAL WORKING CAPITAL": ("PAYPAL WORKING CAPITAL", "PAYPAL CAPITAL", "WEBBANK PAYPAL"),
    "PayTomorrow LLC": ("PAYTOMORROW",),
    "Preferred Credit, Inc": ("PREFERRED CREDIT",),
    "ReadyCap Lending, LLC": ("READYCAP LENDING",),
    "Sezzle Inc": ("SEZZLE",),
    "Shift4 Capital": ("SHIFT4 CAPITAL", "SHIFT4 CAP"),
    "SHOPIFY CAPITAL": ("SHOPIFY CAPITAL",),
    "SpotOn Capital": ("SPOTON CAPITAL",),
    "SQUARE CAPITAL": ("SQUARE CAPITAL", "SQUARE LOAN"),
    "Stripe Capital": ("STRIPE CAPITAL", "STRIPE CAP"),
    "SumUp Cash Advance": ("SUMUP CASH ADVANCE",),
    "Sunbit": ("SUNBIT",),
    "Synchrony Pay Later": ("SYF PAYLTR",),
    "Synchrony Secured Installment Loans": ("SYNCHRONY SECURE",),
    "Toast Capital": ("TOAST CAPITAL", "WEBBANK TOAST"),
    "U.S. Small Business Administration": (
        "SBA EIDL",
        "SBA EIDL LOAN",
        "SBA EID LOAN",
        "SBAEIDL",
        "SBA LOAN",
        "SBALOAN",
        "SMALL BUSINESS ADMINISTRATION",
    ),
    "Uplift, Inc": ("UPLIFT INC",),
    "Women's Enterprise Organizations of Canada": ("WOMENS ENTERPRISE ORG CANADA",),
    "Xplor Capital": ("XPLOR CAPITAL",),
    "Zip Co US Inc": (
        "ZIP APP PAY",
        "ZIP APP PAYLATER",
        "ZIP INSTALLMENT",
        "ZIP INSTALLMEN",
        "ZIP CO US",
        "ZIP BEST BUY",
        "ZIP SHEIN",
    ),
}

#: Lines of credit.
LINE_OF_CREDIT_ALIASES: dict[str, tuple[str, ...]] = {
    "Account bank's line of credit (MCR)": ("REMB MCR", "INTERETS MCR", "DEBOURSE MCR"),
    "Aven Financial, Inc.": ("AVEN HOME FINANC",),
    "BLUEVINE": ("BLUEVINE CAPITAL", "BLUEVINE LOAN"),
    "Celtic Bank (Bluevine line of credit)": ("CELTIC BANK DES BV LOAN",),
    "FUNDBOX": ("FUNDBOX",),
    "HEADWAY CAPITAL": ("HEADWAY CAPITAL", "HWCRCVBLS23"),
    "KABBAGE": ("KABBAGE",),
    "National Bank of Canada line of credit": ("NBC LINE OF CR",),
    "Pitney Bowes Purchase Power": ("PBPURCHASPWR", "PITNEY PURCHASE"),
    "PitneyWorks": ("PITNEY WORKS",),
    "Scotiabank ScotiaLine lines of credit": ("SCOTIALINE", "SCOTIABANK SCOTIALINE"),
    "Slope": ("SLOPE PAY",),
    "TD Canada Trust line of credit": ("TDCT LOC",),
}

#: Credit cards: aliases that carry card-payment wording.
CARD_ISSUER_ALIASES: dict[str, tuple[str, ...]] = {
    "Amazon Store Card": ("AMZ STORECRD PMT",),
    "American Express [credit card payment]": (
        "AMEX EPAYMENT",
        "AMEX EPAYMENT ACH PMT",
        "AMERICAN EXPRESS ACH PMT",
        "AMERICAN EXPRESS DES ACH PMT",
        "AMERICAN EXPR ACH PMT",
        "AMERICAN EXPRESS RETRY PYMT",
        "AMERICAN EXPRESS DES RETRY PYMT",
        "AMERICAN EXPRESS ONLINE PMT",
        "AMEX BILL PYMT",
    ),
    "Apple Card issued by Goldman Sachs Bank USA": (
        "APPLECARD GSBANK PAYMENT",
        "APPLECARD GSBANK DES PAYMENT",
    ),
    "Aspire Mastercard": ("ASPIRE MC PMT", "ASPIREMC PAYMENT"),
    "Atlas Mastercard (Exto Inc.)": ("PAYMENT ATLASFINANCIAL", "ATLASFINANCIAL PAYMENT"),
    "Bank of America, National Association": (
        "BANK OF AMERICA CREDIT CARD",
        "BANK OF AMERICA BUSINESS CARD BILL PAYMENT",
        "BK OF AMER VI MC ONLINE PMT",
        "BK OF AMER VISA ONLINE PMT",
        "BKOFAM CRD",
    ),
    "Blaze Mastercard (First Savings Bank)": ("FSB BLAZE PAYMENT",),
    "Brex Inc": ("BREX CARD PAYMENT", "BREX CARD PA", "BREX PAYMENT"),
    "Capital One": (
        "CAPITAL ONE ONLINE PMT",
        "CAPITAL ONE MOBILE PMT",
        "CAPITAL ONE CARD PYMT",
        "CAPITAL ONE PHONE PYMT",
        "CAPITAL ONE N PAYMENT",
        "ONLINE PMT CAPITAL ONE",
        "CAPITAL ONE DES MOBILE PMT",
        "CAPITAL ONE DES ONLINE PMT",
        "CAPITAL ONE TYPE ONLINE PMT",
    ),
    "Card Assets (credit card issuer and servicer)": ("CARD ASSETS",),
    "Cardless, Inc": ("CARDLESS PAYMENT",),
    "Cardmember Service": ("CARDMEMBER SERV", "CARDMEMBER SVC"),
    "CIBC Card Products Division (Canadian Imperial Bank of Commerce)": ("CIBC CARD PRODUCTS",),
    "Citibank credit card": (
        "CITI CARD ONLINE",
        "CITI CARDS ONLINE PMT",
        "CITIBANK CRDT CD ONLINE PMT",
        "CITI AUTOPAY",
    ),
    "Coast fleet card (Coast Pay, issued by Celtic Bank)": ("COAST PAYMENT",),
    "Concora Credit Inc": (
        "CONCORA CREDIT PAYMENT",
        "CONCORA CREDIT DES PAYMENT",
        "CONCORA CREDIT RETRY PYMT",
        "CONCORA CREDIT TELECHK PAYMENT",
    ),
    "Credit First National Association": ("CFNA PYMT", "CREDIT FIRST NA ONLINE PMT"),
    "Credit One Bank, N.A": (
        "CREDIT ONE BANK PAYMENT",
        "CREDIT ONE BANK DES PAYMENT",
        "PAYMENT CREDIT ONE BANK",
    ),
    "Discover credit card": (
        "DISCOVER CARD",
        "DISCOVER E PAYMENT",
        "DISCOVER PAYMENT",
        "DISCOVER TYPE E PAYMENT",
        "DISCOVER DES E PAYMENT",
        "DISCOVER RETRY PYMT",
        "DISCOVER DES RETRY PYMT",
        "DISCOVER CAP ONE ONLINE PMT",
        "DISCOVER DC PYMNTS DCIINTNET E PAYMENT",
    ),
    "First PREMIER Bank": ("FPB CR CARD", "PREMIER BANKCARD DES AUTOPAY"),
    "Fortiva Mastercard": ("FORTIVA MC PMT", "AUTOFORTIVA PMT"),
    "Imagine Visa": ("IMAGINE VISA PMT",),
    "Intuit [credit card payment]": ("INTUIT CREDIT CRD",),
    "JPMorgan Chase Bank, N.A": (
        "CHASE CREDIT CRD",
        "CHASE CREDIT CRD EPAY",
        "CHASE CARD ENDING",
        "CHASE CARD SERVICES",
        "CHASE CARD SERV",
        "CHASE BUSINESS CREDIT CARD",
    ),
    "Legacy Visa credit card": ("LEGACY VISA PYMT",),
    "Mercury Financial LLC": ("MERCURY CARD FBT", "MERCURY FBT PAYMENT"),
    "Mercury IO card": ("MERCURY CREDIT CREDIT ACCOUNT PAYMENT",),
    "Merrick Bank": ("MERRICK BANK PHONE PMT", "PHONE PMT MERRICK BANK"),
    "Motive Card (Motive Technologies, Inc.)": ("MOTIVE CARD",),
    "Nordstrom Credit Card": ("NORDSTROM PYMT", "NORDSTROM DES PAYMENT"),
    "Scotiabank Gold American Express Card (Bank of Nova Scotia)": ("SCOTIABANK GOLD AMEX CARD",),
    "Self Financial, Inc [credit card payment]": (
        "LEADBANKSELFLEND CC PMT",
        "SELF LENDER SCC TX CARD",
        "PYMT SELF LENDER SCC",
    ),
    "Shell-branded card account": ("SHELL AUTO PYMT", "SHELL ONLINE PMT"),
    "Shopify Credit": ("SHOPIFY CREDIT PAYMENT",),
    "Synchrony Bank [credit card payment]": (
        "SYNCHRONY BANK PAYMENT",
        "SYNCHRONY BANK DES PAYMENT",
        "SYNCHRONY BANK CC PYMT",
        "SYNCHRONY BANK TYPE CC PYMT",
        "SYNCHRONY BANK RETRY PYMT",
        "SYNCHRONY BANK TYPE RETRY PYMT",
        "CC PYMT SYNCHRONY BANK",
        "SYNCHRONYBANK PAYMENT",
        "SYNCB PAYMENT",
        "SYNCB PHONE PAYMENT",
        "SYNCHRONY AMAZON ONLINE PMT",
        "SAMS CLUB DUAL CARD",
    ),
    "Target Card Services": ("TARGET CARD SRVC",),
    "TD Bank, N.A. (TD Card Services)": ("TD BANK CARD SERVICES",),
    "The Home Depot Consumer Credit Card": (
        "HOME DEPOT AUTO PYMT",
        "HOME DEPOT ONLINE PMT",
        "HOME DEPOT PAYMENT",
        "HOME DEPOT DES AUTO PYMT",
        "HOME DEPOT DES ONLINE PMT",
    ),
    "Truist credit card": ("TRUIST ONLINE CREDIT CARD PMT",),
    "Wayfair Credit Card / Wayfair Mastercard": (
        "WAYFAIR AUTO PYMT",
        "WAYFAIR PAYMENT",
        "WAYFAIR DES PAYMENT",
    ),
    "Wells Fargo credit card payment": ("WELLS FARGO CARD", "WF CREDIT CARD"),
}

#: Card issuers: bare names, used only with card-payment wording.
CARD_ISSUER_CONTEXT_ALIASES: dict[str, tuple[str, ...]] = {
    "1st Bankcard Center": ("BANKCARD CTR",),
    "Ally Credit Card": ("ALLY CC",),
    "American Express [card issuer context]": ("AMEX CARDS",),
    "Amex Bank of Canada": ("AMEX BANK OF CANADA",),
    "Apple Card issued by Goldman Sachs Bank USA [card issuer context]": ("APPLECARD GSBANK",),
    "ATB Financial Mastercard": ("ATB MASTERCARD",),
    "AtoB (CElegans Labs, Inc.)": ("ATOB FUEL", "ATOB FLEET"),
    "Bank of America, National Association [card issuer context]": (
        "BK OF AMER VI MC",
        "BK OF AMER VISA",
        "BK OF AMER MC",
    ),
    "Barclays Bank Delaware [credit card payment]": (
        "BARCLAYCARD US",
        "BARCLAY BANK DELAWARE",
        "AARP BARCLAY",
    ),
    "BHG credit card (Bankers Healthcare Group, issued by Blue Ridge Bank)": ("BHG BLURIGBNK",),
    "BMO Mastercard": ("BMO MASTERCARD",),
    "Canadian Tire Mastercard": ("CDN TIRE MC", "TRIANGLE MC", "TRIANGLE MASTERCARD"),
    "Capital on Tap business credit card": ("CAPITAL ON TAP", "CAPITALONTAP"),
    "Capital One [card issuer context]": (
        "CAPITAL ONE MC",
        "CAPITAL ONE M C",
        "CAPITAL ONE MASTERCARD",
        "CAPTL ONE MC",
        "BJS CAPITAL ONE",
        "CAPITAL ONE CRCARDPMT",
        "CRCARDPMT CAPITAL ONE",
    ),
    "CIBC Visa and Mastercard (Canadian Imperial Bank of Commerce)": ("CIBC VISA", "CIBC MC", "M C CIBC"),
    "Citibank credit card [card issuer context]": ("CITIBANK CRDT CD", "CITI CARDS"),
    "Comdata Inc. (Corpay)": ("COMDATA NETWORK",),
    "Comenity Bank / Comenity Capital Bank": ("COMENITY PAY", "COMENITY CAPITAL B"),
    "Concora Credit Inc [card issuer context]": ("CONCORA CREDIT",),
    "Continental Finance Company, LLC": ("CONT FINANCE",),
    "Credit One Bank, N.A [card issuer context]": ("CREDIT ONE BANK",),
    "Desjardins Visa credit card": ("VISA DESJARD", "VISA DESJARDINS"),
    "Discover credit card [card issuer context]": ("DISCOVER DC PYMNTS", "DISCOVER CAP ONE"),
    "Divvy Pay, LLC (BILL Divvy Card)": ("DIVVYP DIVVY CRED",),
    "DSRM National Bank": ("DSRM NATL BANK",),
    "Elan Financial Services": ("ELAN FINANCIAL SERVICES", "ELAN WEB PYMT"),
    "First National Bank of Omaha": ("1ST NATL BK OMAH",),
    "FLEETCOR fleet cards (Corpay, Inc.)": ("FLEETCOR FUNDING", "FLEETCOR"),
    "Fortiva Mastercard [card issuer context]": ("FORTIVA MC",),
    "HOME DEPOT COMM": ("HOME DEPOT COMM",),
    "Home Depot Credit Card Services": ("HOMEDEPOTCCS",),
    "JPMorgan Chase Bank, N.A [card issuer context]": ("CHASE MC AND VISA", "CHASE CREDIT"),
    "Lowe's business credit account": ("LOWES BRC",),
    "Lowe's credit card": ("LOWES SYF PAYMNT",),
    "MBNA Canada Mastercard (Toronto-Dominion Bank)": ("MBNA M C", "MBNA CANADA MASTERCARD"),
    "Mission Lane LLC": ("MISSION LANE",),
    "Neo Financial Technologies Inc.": ("NEO FINANCIAL",),
    "OpenSky (Capital Bank, N.A.)": ("OPENSKY PHONE PMT", "OPENSKY MOBILE PAY", "OPENSKYCC COM"),
    "OTR Solutions fuel card (OTR Capital LLC)": ("OTR SOLUTIONS FUEL", "OTR SOLUTIONS FUE"),
    "PC Financial Mastercard": ("PC FINANCIAL MASTERCARD", "PC FINANCIAL"),
    "Petro-Canada SuperPass fleet fuel card (Suncor Energy Inc.)": ("PC SUPERPASS",),
    "Ramp Business Corporation": ("RAMP STATEMENT",),
    "Rogers Bank Mastercard": ("ROGERS BK MC",),
    "Royal Bank of Canada [credit card payment]": (
        "RBC VISA",
        "RBC MASTERCARD",
        "RBC MC",
        "VISA ROYAL BNK",
        "ROYAL BANK VISA",
    ),
    "Scotiabank [credit card payment]": ("SCOTIABANK VISA", "SCOTIABANK AMEX", "SCOTIA MOMENTUM FB"),
    "SHOW Mastercard": ("SHOW MASTERCARD",),
    "Simplii Financial Cash Back Visa (CIBC)": ("VISA SIMPLII FINANCIAL",),
    "SoFi credit card payment": ("SOFI CC PAY",),
    "Synchrony Bank [card issuer context]": ("SYNCHRONY BANK", "SYNCHRONY MC", "SYNCB PHONE", "SYF"),
    "TD Visa and GM Visa credit cards (BMO bill payee)": ("TD VISA GM",),
    "TD Visa credit card": ("TD VISA", "VISA TD"),
    "The Home Depot Consumer Credit Card [card issuer context]": (
        "HM DEP CON",
        "HOME DEPOT CCCI",
        "HOME DEPOT CITI",
    ),
    "USAA Federal Savings Bank [credit card payment]": ("USAA FSB CC",),
    "Verizon Visa Card (Synchrony Bank)": ("VERIZON CREDIT SYF",),
    "Walmart Rewards Mastercard (Fairstone Bank of Canada)": ("WALMART M C", "WALMART MASTERCARD"),
    "Wells Fargo business credit autopay": ("WF BUS CREDIT",),
    "Wells Fargo credit card [card issuer context]": (
        "WELLS FARGO ACTIVE CASH VISA",
        "WELLS FARGO AUTOGRAPH VISA",
        "WELLS FARGO SIGNIFY BUSINESS CASH",
    ),
    "WEX Inc": ("WEX INC", "WRIGHT EXPRESS", "WEX BANK SECUREFUND", "WEX BANK", "WEX CANADA"),
}

#: Vehicle loans & leases.
VEHICLE_FINANCE_ALIASES: dict[str, tuple[str, ...]] = {
    "Ally Financial Inc": (
        "ALLY FINANCIAL",
        "ALLY PAYMENT",
        "ALLY RETRY PYMT",
        "ALLY DES RETRY PYMT",
        "ACI ALLY BANK",
    ),
    "American Credit Acceptance, LLC": (
        "SPI AMERICAN CREDIT ACC",
        "AMERICAN CREDIT ACC",
        "AMERICAN CREDIT ACCEPTANCE",
    ),
    "American Honda Finance Corporation": ("HONDA PMT", "HONDA FINANCIAL", "AMERICAN HONDA FINANCE"),
    "Audi Financial Services": ("AUDI FINCL", "AUDI FINCL INC", "AUDI FINCL TEL"),
    "Bank of America Vehicle Loans": ("BANK OF AMERICA VEHICLE LOAN", "AMERICA VEHICLE LOAN"),
    "BMW Financial Services NA, LLC": ("BMW BANK", "BMWFINANCIAL", "BMWFS"),
    "Bridgecrest Acceptance Corporation": ("BRIDGECREST", "PYBRIDGECREST"),
    "Capital One Auto Finance": ("CAPITAL ONE AUTO", "CFP CAP ONE AUTO"),
    "CarMax Auto Finance": ("CARMAX AUTO FINANCE", "CARMAX AUTO DES FINANCE"),
    "Chase Auto Finance": ("CHASE AUTO FINANCE",),
    "CheckFreePay auto-loan payments": ("CHECKFREEPAY AUTO LOA",),
    "CNAC (CarNow Acceptance Company)": ("CNAC OF GREENVILLE",),
    "Consumer Portfolio Services, Inc": (
        "CONSUMER PORTFOL",
        "CONSUMER PORTFOL BILLPAY",
        "CONSUMER PORTFOLIO",
        "PNM CONSUMER PORTFOLIO",
    ),
    "Credit Acceptance Corporation": ("CREDITACCEPTA", "CREDITACCEPTANCE", "CREDITACCEPTANCEC"),
    "Enterprise FM Trust": ("ENTERPRISE FM TR",),
    "Exeter Finance LLC": ("EXETERFINA", "EXETERFINANCELLC", "EXETER FINANC"),
    "Finance CreditFix": ("FINANCE CREDITFIX",),
    "Flagship Credit Acceptance": ("FLAGSHIP CREDIT",),
    "Ford Credit Canada": ("FORD CREDIT CA", "FORD CREDIT CANADA"),
    "Ford Motor Credit Company LLC": (
        "FORD CREDIT",
        "FORDCREDIT",
        "FORD MOTOR CR",
        "FORD MOTOR CREDI",
        "LINCOLN AFS",
        "LINCOLN AFS FORDCREDIT",
        "LINCOLN AFS DES FORDCREDIT",
        "LINCOLN AFS RETRY PYMT",
    ),
    "Global Lending Services LLC (GLS Auto)": ("GLOBAL LENDING SERVICES",),
    "GM Financial": ("GM FINANCIAL",),
    "Harley-Davidson Financial Services": ("ACI HDFS PAYMENT", "ACI HDFS"),
    "Holand Leasing": ("HOLAND LEASING",),
    "Holman Fleet Leasing LLC": ("HOLMAN FLEET LEASING",),
    "Hyundai Capital America": ("ACI HYNDAI KIA", "HYNDAI KIA"),
    "Hyundai Motor Finance": ("HYUNDAI PMNT", "HYUNDAI PMNT CT", "HMF HMFUSA COM", "HMFUSA COM", "HMFUSA"),
    "Kia Motors Finance": ("KMFUSA COM", "KMFUSA", "KMF KMFUSA COM"),
    "Lendbuzz Funding, LLC": ("LENDBUZZ", "LENDBUZZ FUNDING"),
    "LENTEGRITY": ("LENTEGRITY", "LENTEGRITY BILLPAY"),
    "Lexus Financial Services": ("PY LFS LEXUS", "PY LFS LEXUS PLANO", "LFS LEXUS"),
    "Lucid Loan and Lease": ("LUCID LOAN AND",),
    "Mazda Financial Services": ("MAZDA FINANCIAL",),
    "Mercedes-Benz Financial Services": ("MBFS", "MBFS COM", "MBFS COM DES AUTO PAY", "MBFS WEB PAY"),
    "Merrick Bank Recreation Lending": ("MERRICK BANK RECREAT",),
    "Nicholas Financial, Inc.": ("NICHOLAS FINANCIAL",),
    "Nissan Motor Acceptance Company LLC": (
        "NISSAN AUTO LEASE",
        "NISSAN MOTOR ACC",
        "NISSANMOTORACC",
        "NISSANMOTORACC BILLPAY NISSAN MOTOR AC",
        "NMAC LOANS",
        "NMAC LOANS ONLINE PMT",
        "NISSAN RETRY PYMT",
        "NISSAN MOTOR ACCEPTANCE",
    ),
    "Porsche Financial Services": ("PORSCHE FINANCIA", "PORSCHE FINANCIA PAYMENTS"),
    "Professional Financial Services Corp. (PFS)": ("PROF FIN SER PFS",),
    "Regional Acceptance Corporation": ("REGIONAL ACCEPTAN", "REGIONAL ACCEPTANCE"),
    "Roadrunner Financial (Octane)": ("ROADRUNNER ACCOU",),
    "Santander Consumer USA Inc": (
        "PNM SANTANDER",
        "CHRYSLER CAPITAL",
        "CHRYSLER CAPITAL BILLPAY",
        "BILLPAY CHRYSLER CAPITAL",
        "CHRYSLER CAPITAL ONLINE PMT",
        "PNM CHRYSLER CA",
        "SANTANDER CONSUMER",
    ),
    "Southeast Toyota Finance": ("SETOYOTA FIN", "SETOYOTA FIN EZP", "SETOYOTA FIN EZP AUTO FINAN"),
    "Stellantis Financial Services": (
        "STELLANTIS LEASE",
        "STELLANTIS LEASE LEASE PMT",
        "STELLANTIS FUNDI",
        "STELLANTIS FUND",
    ),
    "Strike Acceptance, Inc.": ("STRIKE ACCEPTANCE", "STRIKEACCEPTANCE"),
    "TD Auto Finance": ("TD AUTO FINANCE",),
    "Titanium Funds": ("TITANIUM FUNDS",),
    "Toyota Financial Services": ("TOYOTA ACH RTL", "TOYOTA FINANCIAL"),
    "Toyota Financial Services Canada": (
        "TOYOTA FINANCE LOAN",
        "TOYOTA FINANCE",
        "AUTOMOBILE RENT TOYOTA FINANCE",
        "TOYOTA CREDIT CANADA",
        "TOYOTA CREDIT CANADA INC",
    ),
    "Tricor Lease & Finance Corp": ("TRICOR LEASE",),
    "United Auto Credit Corporation": ("UNITED AUTO CREDIT", "UNITED AUTO CRED"),
    "Volvo Car Financial Services U.S., LLC": ("VOLVO CAR FIN", "VOLVO CAR FIN AUTO FINAN"),
    "Wells Fargo Auto": ("WELLS FARGO AUTO", "WELLS FARGO AUTO DRAFT", "WELLS FARGO AUTO FEE AND PMTS"),
    "Westlake Services, LLC (Westlake Financial)": (
        "WESTLAKE FINANCIAL",
        "WESTLAKE FINANCI",
        "WESTLAKE PORTFOLIO",
        "WESTLAKE PORTFOL",
    ),
    "Wilshire Commercial Capital LLC": ("WILSHIRE COMMERCIAL CAPITAL",),
}

#: Mortgages.
MORTGAGE_SERVICER_ALIASES: dict[str, tuple[str, ...]] = {
    "AmWest Funding Corp": ("AMWEST FUNDING", "AMWEST FUNDING C"),
    "Antrim Balanced Mortgage Fund Ltd": ("MORTGAGE ANTRIM BALANCED", "ANTRIM BALANCED"),
    "Bank of America Home Loans": ("BANK OF AMERICA HOME LOANS",),
    "Bell Rock Income Fund 1 LLC": ("BELL ROCK IN FD",),
    "BSI Financial Services": ("BSI FINANCIAL", "BSI FINANC"),
    "Builders Capital": ("BUILDERS CAPITAL",),
    "Carrington Mortgage Services, LLC": ("CARRINGTON MORTGAGE",),
    "Cenlar FSB": ("CENTRAL LOAN ADM",),
    "CIBC Mortgage Corporation": ("CIBC MTGE CORP",),
    "CIBC Mortgages Inc": ("MORTGAGE CIBCMORTGAGES", "CIBCMORTGAGES"),
    "Disney Vacation Club financing": ("DVC LOAN", "DVC LOANS"),
    "Dovenmuehle Mortgage, Inc": ("DOVENMUEHLE ONLINE", "DOVENMUEHLE"),
    "Fay Servicing, LLC": ("FAY SERVICING",),
    "FCI Lender Services, Inc": ("FCI LENDER SVCS", "FCI LOAN SVC"),
    "Figure Lending LLC": ("FIGURE LENDING",),
    "Flash Raise Funding, LLC": ("FLASH RAISE FUND",),
    "FM Home Loans, LLC": ("FM HOME LOANS",),
    "Freedom Mortgage Corporation": ("FREEDOM MORTGAGE CORPORATION", "FREEDOM MORTGAGE"),
    "Lakeview Loan Servicing, LLC": ("LAKEVIEW LOAN SRV",),
    "LendingHome": ("LENDINGHOME",),
    "Lima One Capital, LLC": ("LIMA ONE CAPITAL",),
    "LoanCare, LLC": ("LOANCARE SERV", "LOANCARE"),
    "Marriott Vacation Club": ("MARRIOTT MVC MTG", "MARRIOTT MVC MTG PYMT"),
    "Nations Lending Corporation": ("NATIONS LENDING",),
    "Nationstar Mortgage LLC d/b/a Mr. Cooper": ("NSM DBAMR COOPER", "NSM DBAMR"),
    "Newrez LLC d/b/a Shellpoint Mortgage Servicing": ("NEWREZ SHELLPOIN",),
    "PennyMac Loan Services": ("PENNYMAC",),
    "Planet Home Lending, LLC": ("PLANET HOME ACH PMTS",),
    "Rocket Mortgage, LLC": ("ROCKET MORTGAGE",),
    "Select Portfolio Servicing, Inc": ("SELECT PORTFOLIO",),
    "Selene Finance LP": ("SELENE FINANCE",),
    "The Bank of Nova Scotia": ("MORTGAGE BNS MTGE DEPT", "BNS MTGE DEPT"),
    "United Wholesale Mortgage": ("UNITEDWHOLESALE",),
    "Valon Mortgage, Inc": ("VALON MORTGAGE", "VALON MORTGAGE INC"),
    "Velocity Commercial Capital, LLC dba Velocity Mortgage Capital": ("VELOCITY COMMERCIAL CAPITAL",),
}

#: Leases & rentals.
LEASE_RENTAL_ALIASES: dict[str, tuple[str, ...]] = {
    "Aaron's, LLC": ("AARONS COM",),
    "Acima": ("ACIMA", "ACIMA DIGITAL"),
    "BrandsMart Leasing (BrandsMart USA lease-to-own program)": ("BRANDSMART LEASING",),
    "Cresco Capital, Inc": ("CRESCO CAPITAL",),
    "Cresco Equipment Rentals": ("CRESCO EQUIPMENT RENTAL",),
    "Enercare Home Services": ("ENERCARE HOME S", "ENERCARE HOME SER", "ENERCARE HS"),
    "Finova Capital LLC [lease or rental]": ("FINOVA CAPITAL LEASE",),
    "First Data Global Leasing": (
        "EQUIPMT LEASE FIRST DATA CORP",
        "EQUIPMENT RENT FIRST DATA CORP",
        "FIRST DATA CORP BAIL",
        "FIRST DATA CORP RLS LOY",
    ),
    "FlexShopper": ("FLEXSHOPPER",),
    "GCI Equipment Rental": ("GCI EQUIPMENT RENT", "GCI EQUIPMENT RENTAL"),
    "HEC Trailer Leasing, LLC": ("HEC TRAILER LEAS", "HEC TRAILER LEASI"),
    "Herc Rentals": ("HERC RENTALS",),
    "Katapult": ("KATAPULT",),
    "Koalafi": ("KOALAFI",),
    "LADCO Leasing": ("LADCO LEASING", "LADCO GLOBAL LEASING"),
    "Location Pinard": ("LOCATION PINARD",),
    "LogicaLease LLC": ("LOGICALEASE",),
    "Milestone Equipment Holdings, LLC": ("MILESTONE EQUIP",),
    "Okinus, Inc": ("OKINUS", "OKINUS INC"),
    "Penske Truck Leasing": ("PENSKE TRK LSG",),
    "Progressive Leasing": (
        "PROGRESSIVE LEASING",
        "PROGRESSIVELEASE",
        "PROGRESSIVE LEASIN",
        "PROGRESSIVE LE DRAPER",
    ),
    "Rent-A-Center": ("RENT A CENTER",),
    "RTO Finance LLC": ("RTO FINANCE", "RTO FINANCE LLC"),
    "Ryder Truck Rental, Inc": (
        "RYDER TRUCK RENT",
        "RYDER TRUCK",
        "RYDER MILWAUKEE",
        "RYDER RACINE",
        "RYDER MADISON",
        "RYDER GREENBAY",
        "RYDER LAFAYETTE",
        "RYDER BATON ROUGE",
    ),
    "SmartPay": ("SMARTPAY LEASING",),
    "SNAP Finance": ("SNAP FINANCE",),
    "Sunbelt Rentals": ("SUNBELT RENTALS", "SUNBELTRENTALS"),
    "U-Haul": (
        "U HAUL",
        "U HAULMIDGARD SENE",
        "U HAULCLOCKWORK AU",
        "U HAULCOMMUNITY T",
        "U HAULECONOMY TIRE",
        "U HAULMCNAMARA",
        "U HAULSUNDANCE REN",
        "U HAULWOODRUFF ROAD",
        "UHI U HAULTIGER",
        "U HAULSTUFF N STOR",
    ),
    "United Rentals, Inc.": ("UNITED RENTALS", "UNITED RENTALS CORP"),
    "Uown Leasing": ("UOWN LEASING",),
    "Vista Services": ("VISTA SERVICES",),
    "Zia Equipment Rentals": ("ZIAEQUIPMENTRENTALS", "ZIAEQUIPMENTR"),
}

#: Personal loans.
PERSONAL_LOAN_ALIASES: dict[str, tuple[str, ...]] = {
    "1st Franklin Financial Corporation": ("1ST FRANKLIN FIN", "FRANKLIN FIN TRANS"),
    "Achieve Personal Loans": ("ACHIEVEPL",),
    "Advance America": ("ADVANCE AMERICA",),
    "Advance Financial": ("AF247",),
    "Aidvantage": ("ADVS ED SERV",),
    "Albert Corporation": (
        "ALBERT GENIUS",
        "ALBERT COM",
        "ALBERT CORPORATION",
        "ALBERT CULVER CITY",
        "ALBERT AUTHENTICATION",
    ),
    "American Education Services (AES)": ("AES STDNT LOAN", "ORIG CO NAME AES ORIG"),
    "Ava Finance, Inc": ("AVA FINANCE",),
    "Avant, LLC": ("AVANT LLC", "OPC AVANT", "AVANT COM"),
    "Barclays Bank Delaware (personal loans)": ("BARCLAY PERSONAL LOAN",),
    "Basic Finance, Inc": ("BASIC FINANCE",),
    "Best Egg": ("BEST EGG",),
    "Birch Lending": ("BIRCH LENDING",),
    "Borrowell": ("BORROWELL PAY",),
    "Bright Lending": ("BRIGHTLENDING", "BRGHT LENDING"),
    "Bright Money": ("BRIGHT MONEY",),
    "Brigit": ("BRIGIT COM", "BRIGIT NEW YORK", "INSTPMNTIN BRIGIT", "RTP CREDIT BRIGIT"),
    "Cash 4 You Corp": ("CASH 4 YOU",),
    "Cashli": ("CASHLI",),
    "Cleo AI": (
        "CLEO AI",
        "MEETCLEO",
        "CLEO SALARY ADVANCE",
        "CLEO ADVANCE WILMINGTON",
        "CLEO ADVANCE REPAY",
        "CLEO ADVANCE EXPRESS",
        "CLEO AI ADVNCEXPRS",
        "CLEO EXPRESS FEE",
    ),
    "CreditNinja": ("CREDITNINJA",),
    "Dave, Inc": ("DAVE INC", "DAVESUBFEE", "DAVE COM", "DAVE MEMBERSHI", "PULL DAVE"),
    "Earnest": ("EARNEST SPDPY",),
    "EarnIn": ("EARNIN",),
    "Fairstone": ("FAIRSTONE LOANS",),
    "FloatMe Corp": ("FLOATME", "FLOAT ME CORP"),
    "Grant Money, LLC": (
        "GRANT CASH ADVANCE",
        "GRANT MONEY LLC",
        "GRANT REPAYMENT SAN FRANCISCO",
        "OASISCRE",
        "GRANT SUBSCRIPTION SAN FRANCISCO",
    ),
    "Jewish Free Loan Toronto": ("JFLT",),
    "Kikoff Inc": ("KIKOFF", "KIKOFFINC", "KIKOFF LENDING"),
    "Klover": ("KLOVER",),
    "Kovo Inc": ("KOVOCREDIT",),
    "Launch Servicing, LLC": ("LAUNCH SERVICING",),
    "Laurel Road (KeyBank, N.A student loans)": ("LAUREL ROAD",),
    "LenCo Finance of Crowley, Inc": ("LENCO FINANCE OF CROWL",),
    "LendingClub": ("LENDINGCLUB", "LENDING CLUB", "HAPPENBANK"),
    "LendingPoint LLC": ("LENDINGPOINT",),
    "Lendmark Financial Services LLC": ("LENDMARK",),
    "LightStream": ("LIGHTSTREAM",),
    "Little Lake Lending": ("LITTLE LAKE LENDING",),
    "LoanMart": ("LOANMART",),
    "LOANME": ("LOANME",),
    "Mariner Finance, LLC": ("MARINER FINANCE",),
    "MaxLend": ("MAXLEND",),
    "MoneyLion": ("MONEYLION", "ML PLUS LLC"),
    "NETCREDIT": ("NETCREDIT", "CCBANK NTC"),
    "New Southern Loans, Inc": ("NEW SOUTHERN LOANS",),
    "New York Life Insurance Company": ("NYLIC LOAN BAL",),
    "OneMain Financial": ("ONEMAIN",),
    "Pay2Day Inc": ("PAY2DAY",),
    "Possible Finance": ("POSSIBLE FINANCE", "POSSIBLEFI"),
    "Prosper Marketplace, Inc": ("PROSPER MARKETPL",),
    "Regional Finance": ("REGFINANCE", "SPI REG FINANCE"),
    "Reprise Financial": ("REPRISE FINANCIA",),
    "Republic Finance, LLC": ("REPUBLIC FINANCE",),
    "Rise Up Lending": ("RISE UP LENDING",),
    "River Valley Loans": ("RIVERVALLEYL",),
    "RushApprove": ("RUSHAPPROVE",),
    "Sallie Mae Bank": ("SLMLOANPMT", "AUTOPAY SALLIE MAE BANK"),
    "Self Financial, Inc (credit builder)": ("SELF LENDER", "SELF FINANCIAL", "LEADBANKSELFLEND PAYMENTS"),
    "SoFi Bank, N.A.": ("SOFI BANK PL", "SOFI PL DISB"),
    "SoLo Funds": ("SOLOFUND",),
    "Speedy Cash": ("SPEEDY CASH",),
    "Spotloan": ("SPOTLOAN",),
    "Spring Financial": ("SPRINGFINANCIAL",),
    "Sun Loan Company": ("SUN LOAN COMPANY", "SUNLOANCO"),
    "Tennessee Title Loans, Inc": ("TENNESSEE TITLE LOANS",),
    "Tilt (formerly Empower Finance)": (
        "TILT FKA EMPOWER",
        "TILT ADVANCE",
        "TILT FINANCE",
        "TILT CASH ADVANCE",
        "EMPOWER TILT",
        "TILTFIN",
        "PAID TO TILT",
        "PULL TILT",
        "TILT CASH",
        "INSTPMNTIN EMPOWER",
        "RTP CREDIT EMPOWER",
    ),
    "Time Financing Service": ("TIME FINANCING",),
    "TitleMax": ("TITLEMAX",),
    "Together Loans": ("TOGETHER LOANS",),
    "Tower Loan": ("TOWER LOAN",),
    "U.S. Department of Education": ("DEPT EDUCATION", "DEPT EDUCATIONSTUDENT"),
    "Upgrade, Inc": ("UPGRADE INC", "UPGRADE SAN FRANCISCO"),
    "Uprova Credit, LLC": ("UPROVA CREDIT",),
    "Upstart Network, Inc": ("UPSTART NETWORK", "UPSTLOANTR"),
    "Varo Bank, N.A (Varo Advance)": ("VARO ADVANCE",),
    "Willow Lake Lending": ("WILLOWLAKELEND",),
    "World Finance": ("WORLD FINANCE", "WORLD ACCEPTANCE"),
}

#: Floor plan.
FLOOR_PLAN_ALIASES: dict[str, tuple[str, ...]] = {
    "ACV Capital LLC": ("ACV CAPITAL", "ACV CAPITAL FUNDING", "ACV CAPITAL PAYMENT"),
    "AFC FUNDING CORP": ("AFC FUNDING CORP", "AFC FUNDING"),
    "Axle Funding": ("AXLE FUNDING", "AXLE FUNDING FLOORPLAN"),
    "Floorplan Xpress": ("FLOORPLAN XPRESS", "FPX D CENT", "FPX D WEST"),
    "Kinetic Advantage": ("KINETICADVANTAGE", "KINETIC ADVANTAGE"),
    "NextGear Capital, Inc": ("NEXTGEAR", "NEXTGEAR CAPITAL"),
    "Wells Fargo Commercial Distribution Finance": ("WELLS FARGO CDF",),
    "Westlake Flooring Company LLC": ("WESTLAKE FLOORING", "WESTLAKE FLOORIN", "WESTLAKE FLOORIN PAYABLES"),
}

#: Factoring.
FACTORING_ALIASES: dict[str, tuple[str, ...]] = {
    "Alterna Capital Solutions, LLC": ("ALTERNACAPITALSOLUTIONSLLC", "ALTERNA CAPITAL SOLUTIONS"),
    "AmeriFactors Financial Group, LLC": ("AMERIFACTORS FIN", "AMERIFACTORS FINANCIAL"),
    "Apex Capital Corp": ("APEX CAPITAL", "HW APEX CAPITA", "APEX CAP"),
    "BC Factoring LLC": ("BC FACTORING",),
    "Capital Now Ventures Inc": ("CAPITAL NOW VENTURES", "CAPITAL NOW CAP"),
    "Carter Funding Corporation": ("CARTER FUNDING",),
    "Coeur Capital, Inc": ("COEUR CAPITAL",),
    "eCapital Corp.": (
        "ECAPITAL",
        "ECAPITAL CORP",
        "ECAPITAL FREIGHT FACTORING",
        "ECAPITAL COMMERCIAL FINANCE",
        "ECAPITAL HEALTHCARE",
    ),
    "Grimley Financial Corporation": ("GRIMLEY FINANCIAL",),
    "Liquid Capital Corp": ("LIQUID CAPITAL",),
    "OTR Capital LLC": ("OTR CAPITAL", "OTRSCHDPAY", "OTR SOLUTIONS SPV"),
    "RTS Financial Service, Inc": ("RTS FINANCIAL", "RTS FINANCIAL SERVICE"),
    "Scale Funding": ("SCALE FUNDING",),
    "Stenn Assets UK Ltd (Stenn)": ("STENN ASSETS", "STENN INTERNATIONAL"),
    "Treadstone US Capital, LLC": ("TREADSTONE US CAPITAL", "TREADSTONE OPER"),
}

#: Debt relief: debt-settlement account processors and debt-relief firms (flagged, never lender math).
DEBT_RELIEF_ALIASES: dict[str, tuple[str, ...]] = {
    "Americor Funding LLC (Americor Financial)": ("AMERICOR FINANCIAL", "AMERICOR FUNDING"),
    "Beyond Finance LLC (Accredited Debt Relief)": ("BEYOND FINANCE", "ACCREDITED DEBT RELIEF"),
    "Cambridge Credit Counseling Corp": ("CAMBRIDGE CREDIT COUNSELING",),
    "ClearOne Advantage LLC": ("CLEARONE ADVANTAGE", "CLEAR ONE ADVANTAGE"),
    "Coastal Debt Resolve (ABSM LLC)": ("COASTAL DEBT RESOLVE",),
    "Consolidated Credit Counseling Services Inc": ("CONSOLIDATED CREDIT COUNSELING",),
    "Cordoba Legal Group PLLC": ("CORDOBA LEGAL",),
    "Credit Canada Debt Solutions": ("CREDIT CANADA DEBT SOLUTIONS",),
    "Credit Counselling Society": ("CREDIT COUNSELLING SOCIETY",),
    "Crossroads Financial Technologies (CFTPay)": ("CFTPAY", "CROSSROADS FINANCIAL TECHNOLOGIES"),
    "CuraDebt Systems LLC": ("CURADEBT",),
    "Delancey Street Debt Relief Inc": ("DELANCEY STREET DEBT RELIEF",),
    "Freedom Debt Relief LLC": ("FREEDOM DEBT RELIEF",),
    "Global Holdings LLC": ("GHLLC", "GLOBAL CLIENT SOLUTIONS"),
    "GreenPath Inc (GreenPath Financial Wellness)": ("GREENPATH FINANCIAL WELLNESS", "GREENPATH INC"),
    "InCharge Debt Solutions": ("INCHARGE DEBT SOLUTIONS", "INCHARGE DEBT"),
    "Money Management International Inc": ("MONEY MANAGEMENT INTERNATIONAL", "MONEY MANAGEMENT INTL"),
    "National Debt Relief LLC": ("NATIONAL DEBT RELIEF",),
    "New Leaf Debt Solutions Inc": ("NEW LEAF DEBT",),
    "RAM Payment LLC (Reliant)": (
        "RAM PAYMENTS",
        "RAM PAYMENT",
        "RAM PMT",
        "ORIG CO NAME RAM ORIG",
        "RELIANT ACCOUNT MANAGEMENT",
    ),
    "Second Wind Consultants Inc (Rise Alliance)": ("RISE ALLIANCE", "SECOND WIND CONSULTANTS"),
    "Set Forth LLC (Forth Pay)": ("FORTH PAY", "FORTH CORDOBA"),
    "Tayne Law Group": ("TAYNE LAW GROUP", "TAYNE LAW"),
}

#: Premium financing: premium-finance payees, read only by the insurance rule.
PREMIUM_FINANCE_ALIASES: dict[str, tuple[str, ...]] = {
    "AFCO Credit Corporation": ("AFCO DIRECT", "AFCO CREDIT"),
    "Capital Premium": ("CAPITAL PREMIUM",),
    "ClassicPlan Premium Financing, Inc": ("CLASSICPLAN PREM",),
    "FIRST Insurance Funding": (
        "FIRST INSURANCE FUNDING",
        "FIRST INSURANCE FUNDIN",
        "FIRST INSURANCE",
        "FIRST INSURANCE PBS",
        "FIRST INSURANCE INSURANCE",
    ),
    "FIRST Insurance Funding of Canada": (
        "FIRST INSURANCE LNS",
        "FIRST INSURANCE LOAN",
        "INSURANCE LOAN FIRST INSURANCE",
        "FIRST INS FUND",
    ),
    "First Solution Financial Services, Inc": ("FIRST SOLUTION FIN",),
    "General Agents Acceptance Corporation": ("GENERAL AGENTS A", "GENERAL AGENTS A INS PMNT"),
    "gotoPremiumFinance": ("GOTO PREMFIN",),
    "HMS Financial Inc": ("HMS FINANCIAL INC",),
    "Honor Capital": ("HONOR CAPITAL ET", "HONOR CAPITAL CORP"),
    "IFS Financial Services Inc": ("IFS PREMIUM FIN", "IFS PREMIUM FINANCE"),
    "IPFS Corporation": (
        "IPFS",
        "IPFS CORPORATION",
        "IMPERIAL PFS",
        "HUBIPFS",
        "IPFSPMTFLP",
        "IPFSPMTFLS",
        "IPFSPMTFLT",
        "IPFSPMTILC",
        "IPFSPMTMOK",
        "IPFSPMTSCC",
        "IPFSPMTTXH",
        "IPFSPMTWAS",
        "IPFSFNDFLP",
        "IPFSFLP",
    ),
    "IPFS of New York, LLC": ("IPFS OF NEW YORK",),
    "Johnson & Johnson Preferred Financing, Inc": ("JJPF PAYMENTS",),
    "National Partners PFco, LLC": ("INSPREMFIN NATIONAL PARTNER", "NATIONAL PARTNER DES INSPREMFIN"),
    "Premco Financial Corporation": ("PREMCO FINANCIAL", "INSPREMIUM PREMCO FINANCIAL"),
    "Primaco": ("ASSURANCE PRIMACO", "PRIMACO"),
    "Reliable Premium Finance Company, Inc": ("RELIABLE PREMIUM",),
    "Standard Premium Finance Management Corporation": ("STANDARD PREM CNTRCT",),
    "The Premins Company": ("INSFINANCE",),
    "US Premium Finance": ("EPY US PREMIUM", "EPY US PREMIUM F"),
}

#: Bank names: bank loans (D5).
BANK_NAME_ALIASES: dict[str, tuple[str, ...]] = {
    "Axos Bank": ("AXOS BANK",),
    "BCU Financial": ("BCU FINANCIAL",),
    "Beacon Bank": ("BEACON BANK",),
    "Citizens Bank": ("CITIZENS LOAN PYMT",),
    "City National Bank": ("CITY NATIONAL BK",),
    "CreditStrong": ("CREDITSTRONG", "CREDITSTRONG AUSCABANK"),
    "EverBank, N.A.": ("EVERBANK",),
    "FHB LOANS": ("FHB LOANS",),
    "Fifth Third Bank": ("FIFTH THIRD",),
    "First Citizens Bank": ("FCB LOAN PROCEEDS",),
    "Greenwood Credit Union": ("GREENWOOD CU",),
    "Knoxville TVA Employees Credit Union": ("KTVAECU", "KNOXVILLE TVA E"),
    "Lendeavor (Provide, Fifth Third Bank)": ("LENDEAVOR",),
    "MUTUAL SAVINGS A": ("MUTUAL SAVINGS A",),
    "Navy Federal Credit Union": ("NFCU ACH",),
    "PNC Bank, N.A.": ("PNC LENDING", "PNC MAKE A PMT", "PNC BANK IL DEL"),
    "PSECU (Pennsylvania State Employees Credit Union)": ("PSECU",),
    "Regions Bank": ("REGIONS BANK",),
    "Royal Bank of Canada [bank name]": ("RBC LOAN", "PRET RBC"),
    "Roynat Inc": ("ROYNAT",),
    "Scotiabank [bank name]": ("SCOTIABANK", "PRET PERSONNEL SPL"),
    "Scott Credit Union": ("SCOTTCU", "SCOTT CREDIT UNION"),
    "Sound Credit Union": ("SOUND CU OP", "SOUND CU"),
    "TD Bank": ("TD LOAN PAYMNT", "TD BANK N A"),
    "TD Canada Trust": ("TD ON LINE LOANS SYSTEM", "PRET TD"),
    "Texell Credit Union": ("TEXELL CREDIT UN",),
    "The Huntington National Bank": ("HUNTINGTON NATIO", "HUNTINGTON NA", "HUNTINGTON BANKS"),
    "Truist Bank": ("TRUIST LOAN", "TRUIST LOAN MBW PYMT", "TRUIST LOAN OLB PYMT"),
    "Truity Credit Union": ("TRUITY CU", "TRUITYCU"),
    "U.S. Bank National Association": ("USBANK",),
    "USAA Federal Savings Bank [bank name]": ("USAA FSB", "USAA COM PAYMNT"),
    "Veridian Credit Union": ("VERIDIANLOAN",),
    "Wells Fargo Bank, N.A": ("WELLS FARGO BANK", "WF LOAN"),
    "WSFS Bank": ("WSFS BANK",),
}

#: Potential lenders: review, never counted.
POTENTIAL_LENDER_ALIASES: dict[str, tuple[str, ...]] = {
    "ACC LP IV": ("ACC LP IV LOAN",),
    "ADVANCE CONSOLID (unidentified ACH originator)": ("ADVANCE CONSOLID",),
    "Advisco Capital Corp": ("ADVISCO CAPITAL CORP",),
    "AI MY ADVANCE (unidentified debit)": ("AI MY ADVANCE",),
    "Altus Receivables Management": ("ALTUS RECEIVABLE",),
    "APPROVED FUNDING (unidentified ACH originator)": ("APPROVED FUNDING",),
    "Atlas Advance LLC": ("ATLAS ADVANCE LL",),
    "Atlas Recovery LLC": ("ATLAS RECOVERY L",),
    "AVEN AUTO FINANC (probably Aven Auto Inc)": ("AVEN AUTO FINANC",),
    "Avon Capital (unidentified)": ("AVON CAPITAL",),
    "BLACKBULL": ("BLACKBULL ENTERP",),
    "BRDCAP (unidentified ACH originator)": ("BRDCAP",),
    "CAF DIRECT CHECK (probably CarMax Auto Finance)": ("CAF DIRECT CHECK",),
    "Caine & Weiner Company, Inc": ("CAINE AND WEINER",),
    "CAPITAL FUNDI (unidentified Capital Funding originator)": ("CAPITAL FUNDI",),
    "Cat Financial (Speedpay phone payments)": ("SPI CAT CATERPILLAR",),
    "Chestnut Street Funding": ("CHESTNUT STR FUNDING",),
    "ChoiceHealth Finance": ("CHOICEHEALTH FINANCE",),
    "Classic Leasing": ("CLASSIC LEASING",),
    "CLEARCAPITAL (unidentified funder)": ("ORIG CO NAME CLEARCAPITAL ORIG",),
    "CLF (probably Cityline Funding Group)": ("BUSINESS TO BUSINESS ACH DEBIT CLF",),
    "Clover Capital": ("CLOVER CAPITAL",),
    "Clover Equipment": ("CLOVER EQUIPMENT RENT", "CLOVER EQUIPMENT RENTAL", "CLOVER EQUIPMENT LEASE"),
    "CMI (Canadian mortgage lender, unresolved)": ("MORTGAGE CMI", "MORTGAGE REPRESENTED DR CMI"),
    "Commercial Asset Recovery, LLC": ("COMMASSETRECOV",),
    "CONSTRULOANS": ("CONSTRULOANS",),
    "Cooper Equipment Rentals Ltd (probable)": ("COOPER EQUIPMEN",),
    "CRB UPL LOAN (Cross River Bank personal loan)": ("CRB UPL LOAN",),
    "DAILY FUNDING": ("DAILY FUNDING", "DAILYFUNDING"),
    "DAIMLER (probably Daimler Truck Financial)": ("ORIG CO NAME DAIMLER ORIG",),
    "DW Rentals (unidentified rental payee)": ("DW RENTALS",),
    "EAGLE CAPITAL (unconfirmed factoring payer)": ("EAGLE CAPITAL DES EAGLE CAP",),
    "Eagle Finance Holding LLC": ("EAGLE FINANCE HOLDING",),
    "ELEVATED FUNDING": ("ELEVATED FUNDING",),
    "Empire Recovery Solutions, LLC": ("EMPIRE RECOVERY SOLUTIONS",),
    "Envision Capital Group LLC": ("ENVISION CAPITAL",),
    "EPAYMYLOAN": ("EPAYMYLOAN",),
    "EQUIP FINANCING (unnamed equipment financier)": ("EQUIP FINANCING",),
    "EQUIPMENT FINANC ONLINEINV (unnamed equipment financier)": ("EQUIPMENT FINANC ONLINEINV",),
    "ERO LOANS (unidentified ACH originator)": ("ERO LOANS",),
    "FIRST BUSINESS B (probably First Business Bank equipment finance)": ("FIRST BUSINESS B LEASE RENT",),
    "First Pro Financial LLC": ("FIRST PRO FINANCIAL",),
    "First Sterling": ("FIRST STERLING LOAN",),
    "FleetLogic (probably Fleet Logic, LLC dba Velocity Truck Rental and Leasing)": ("FLEETLOGIC CONS COLL",),
    "FUTURE FUNDING (legal entity not identified)": ("FUTURE FUNDING DES",),
    "Geneva Capital": ("GENEVA CAPITAL",),
    "Georgia Venture Holdings (GEORGIAVENTUREHO)": ("GEORGIAVENTUREHO",),
    "GLOBAL FUNDING (Zelle payee)": ("ZELLE PAYMENT TO GLOBAL FUNDING",),
    "GLOBAL MER (probably Global Merchant Cash)": ("GLOBAL MER EDI PYMNTS",),
    "Goldman Financial": ("GOLDMAN FINANCIA UNDERWRITI",),
    "Heartland Capital": ("HEARTLAND CAPITAL", "HEARTLAND CAPITA"),
    "Hillcrest Acceptance, LLC": ("HILLCREST ACCEPTANCE",),
    "HMF (probably Hyundai Motor Finance)": ("ORIG CO NAME HMF ORIG",),
    "IA AUTO CAB (possibly iA Auto Finance)": ("IA AUTO CAB",),
    "ILA (unidentified Wells Fargo originator)": ("ILA DLY",),
    "Immediate Advance": ("IMMEDIATE ADVANC",),
    "Input 1 Payments": ("INPUT 1 PAYMENTS INSURANCE",),
    "Invictus (FRPA originator)": ("INVICTUS TYPE FRPA",),
    "JRW CAPITAL": ("JRW CAPITAL",),
    "KAPITALE": ("KAPITALE",),
    "LEGENDARY (unidentified TD Bank originator)": ("ACH LEGENDARY",),
    "LENDINGSERVICES": ("LENDINGSERVICES",),
    "LOANS FC": ("LOANS FC",),
    "LS Capital LLC": ("LS CAPITAL",),
    "LYL Funding, LLC": ("LYL FUNDING",),
    "MAXIM (probably Maxim Commercial Capital)": ("ORIG CO NAME MAXIM ORIG",),
    "Mazal Funders": ("MAZAL FUNDERS",),
    "MB FINANCIAL CA (probably Mercedes-Benz Financial Services Canada)": ("MB FINANCIAL CA",),
    "MERADV (unidentified ACH originator)": ("MERADV",),
    "MERCH PAD (probably Merchant Growth)": (
        "INVESTMENT MERCH PAD",
        "PLACEMENT MERCH PAD",
        "MERCH PAD INV",
        "MERCH PAD PLAC",
    ),
    "Meridian (RLS rent/lease PAD; probably Meridian OneCap Credit Corp)": (
        "MERIDIAN RLS",
        "MERIDIAN RLS LOY",
    ),
    "Merit Business (probably Merit Business Funding)": ("MERIT BUSINESS",),
    "Money Man 4 Cash Advance": ("MONEY MAN 4 CASH",),
    "MORTGAGE IVR PYMNT (probably 21st Mortgage Corporation)": (
        "MORTGAGE IVR PYMNT",
        "MORTGAGE CO MORTG PMT",
    ),
    "MORTGAGE SERV CT (unidentified mortgage servicer)": ("MORTGAGE SERV CT",),
    "NATIONAL MONEY (probably Money Mart)": ("NATIONAL MONEY",),
    "Nationwide Credit (debt collector; creditor not printed)": ("NATIONWIDECREDIT",),
    "Nomas Recovery LLC": ("NOMAS RECOVERY",),
    "Oakmont Capital (probably Oakmont Capital Services)": ("OAKMONT CAPITAL",),
    "OCEAN FUND (probably an Ocean Funding MCA company)": ("OCEAN FUND",),
    "PACCAR (PACCAR Financial or PacLease, unconfirmed)": ("ORIG CO NAME PACCAR ORIG",),
    "PayNearMe": ("PNM LOAN PAYMEN",),
    "PFG FUND (probably Prosperity Funding Group)": ("PFG FUND CA",),
    "Primary Capital Solutions": ("PRIMARY CAPITAL SOLUTIONS", "PRIMARY CAPITAL SOLU"),
    "Quality Leasing Co., Inc": ("QUALITY LEASING",),
    "QUANTUM CAPITAL": ("QUANTUM CAPITAL",),
    "Quantum SPV I LLC": ("QUANTUM SPV I",),
    "RecoverX Corp": ("RECOVERX CORP", "RECOVERX"),
    "Resolve (probably Resolve Pay)": ("RESOLVE PAYMENT",),
    "Resolve Capital (probably Resolve Capital Partners, MCA debt relief)": ("RESOLVE CAPITAL",),
    "Rewards Network": ("REWARDS NETWORK",),
    "Samson Servicing (probably Samson MCA / Samson Funding)": ("SAMSONSERVICING", "SAMSON SERVICING"),
    "Sigma Financial": ("SIGMA FINANCIAL",),
    "States Resources Corp": ("STATES RESOURCES",),
    "STELLANTIS SFA (probably Stellantis Financial Services)": ("STELLANTIS SFA",),
    "Systems & Services Technologies (SST)": ("SST LOAN PMT",),
    "Table Rock Investments LLC": ("TABLE ROCK INVST",),
    "Tarry Hill Funding, LLC": ("TARRY HILL FUNDING",),
    "Texoma Capital LLC": ("TEXOMA CAPITAL LLC", "TEXOMA CAPITAL L"),
    "TFG (Quebec pre-authorized debit)": ("PRELEVEMENT AUTOMATIQUE TFG",),
    "Transparency Advance": ("TRANSPARENCY ADVANCE",),
    "Triton Recovery LLC": ("TRITON RECOVERY",),
    "UAS (probably University Accounting Service)": ("UAS DES EPAYMENT",),
    "Unidentified account servicer (ACCOUNT SERVICIN[G])": ("ACCOUNT SERVICIN",),
    "Unidentified PAD originator BUSINESS CR EFT (Commercial Loans)": (
        "COMMERCIAL LOANS BUSINESS CR EFT",
        "BUSINESS CR EFT CLN",
    ),
    "Unidentified payee FREEDOM": ("FREEDOM DES MTG PYMTS",),
    "Unidentified payee SMARTCAP": ("APT PAY INC SMARTCAP", "COMPTE A PAYER SMARTCAP"),
    "Unnamed merchant cash advance (Found repayment line)": ("MERCHANT CASH ADVANCE REPAYMENT",),
    "Vanguard Cap": ("VANGUARD CAP OPE",),
    "VAULT (Canadian PAD originator)": ("VAULT MSP DIV", "MISC PAYMENT VAULT", "MISC PAYMENTS VAULT"),
    "Vellum Capital LLC": ("VELLUM CAPITAL L",),
    "WESTLAKE (Chase CCD form; possibly Westlake commercial vehicle financing)": (
        "ORIG CO NAME WESTLAKE ORIG",
    ),
    "WESTLAKE (probably Westlake Financial Services)": ("WESTLAKE PAYMENT",),
    "WOW FACTOR (unidentified Canadian PAD originator)": ("WOW FACTOR RLS",),
}

#: 5.3 (owner ruling 2026-09-27): review entities whose debits take their flag, unconfirmed.
REVIEW_FLAG_ENTITIES: dict[str, str] = {
    "AVEN AUTO FINANC (probably Aven Auto Inc)": "vehicle_financing",
    "CAF DIRECT CHECK (probably CarMax Auto Finance)": "vehicle_financing",
    "Classic Leasing": "vehicle_financing",
    "Clover Equipment": "lease_or_rental",
    "CMI (Canadian mortgage lender, unresolved)": "mortgage",
    "Cooper Equipment Rentals Ltd (probable)": "lease_or_rental",
    "CRB UPL LOAN (Cross River Bank personal loan)": "personal_loan",
    "Hillcrest Acceptance, LLC": "vehicle_financing",
    "HMF (probably Hyundai Motor Finance)": "vehicle_financing",
    "IA AUTO CAB (possibly iA Auto Finance)": "vehicle_financing",
    "MB FINANCIAL CA (probably Mercedes-Benz Financial Services Canada)": "vehicle_financing",
    "MORTGAGE IVR PYMNT (probably 21st Mortgage Corporation)": "mortgage",
    "MORTGAGE SERV CT (unidentified mortgage servicer)": "mortgage",
    "NATIONAL MONEY (probably Money Mart)": "personal_loan",
    "Resolve Capital (probably Resolve Capital Partners, MCA debt relief)": "debt_relief",
    "STELLANTIS SFA (probably Stellantis Financial Services)": "vehicle_financing",
    "UAS (probably University Accounting Service)": "personal_loan",
    "Unidentified payee FREEDOM": "mortgage",
    "WESTLAKE (probably Westlake Financial Services)": "vehicle_financing",
}

#: Audit B6 (I10): factoring review entities, their credits a factoring payout, unconfirmed.
FACTORING_REVIEW_ENTITIES: tuple[str, ...] = (
    "EAGLE CAPITAL (unconfirmed factoring payer)",
    "Primary Capital Solutions",
    "Texoma Capital LLC",
)

# --- END GENERATED: tools/build_lender_registry.py ---

#: Compatibility name (spec section 5): the lender table under its old name.
CONFIRMED_LENDER_ALIASES = LENDER_ALIASES

#: The known-payee matcher's registries (contract C2), keyed by classification
#: state. The order is the tie-break order of ``analysis.payee_matcher``.
#: PREMIUM_FINANCE_ALIASES is not here: only the insurance rule reads it.
PAYEE_GROUP_REGISTRIES: dict[str, dict[str, tuple[str, ...]]] = {
    "confirmed_lender": LENDER_ALIASES,
    "alternative_position": ALTERNATIVE_POSITION_ALIASES,
    "line_of_credit": LINE_OF_CREDIT_ALIASES,
    "vehicle_financing": VEHICLE_FINANCE_ALIASES,
    "mortgage": MORTGAGE_SERVICER_ALIASES,
    "personal_loan": PERSONAL_LOAN_ALIASES,
    "floor_plan_financing": FLOOR_PLAN_ALIASES,
    "factoring": FACTORING_ALIASES,
    "lease_or_rental": LEASE_RENTAL_ALIASES,
    "credit_card_payment": CARD_ISSUER_ALIASES,
}

#: Audit B6 (I49; lender detection spec §4.6): known-payee aliases the matcher reads only where a reference code (a
#: token with a digit) or nothing follows them, in their spaced and run-together forms. Tilt's cash advance printed on
#: the RTP network as 'RTP CREDIT EMPOWER <reference>', or as PNC's instant payment 'INSTPMNTIN EMPOWER <mm> <dd>
#: <reference>', is the app's; a company named Empower... paying by RTP or instant payment prints its name after the
#: word ('RTP CREDIT EMPOWER SOLUTIONS ...') and is no advance. B6 review round 1: Brigit's two rail forms and Tilt's
#: card-network push 'TILT CASH <reference>' are tied the same way: BRIGIT is a given name (a person or company named
#: Brigit... paid by RTP or instant payment prints a name after it) and TILT CASH two ordinary words (a company named
#: TILT CASH ... paying by ACH). Each is a ledger alias.
REFERENCE_TIED_ALIASES: frozenset[str] = frozenset({
    "RTP CREDIT EMPOWER", "INSTPMNTIN EMPOWER", "TILT CASH", "RTP CREDIT BRIGIT", "INSTPMNTIN BRIGIT",
})

#: Audit B6 (I22; lender detection spec §4.6): ledger aliases the known-payee matcher reads on credits only
#: (analysis.payee_matcher's credit index). The LCF Group's run-together name is printed on its funding credits; on a
#: debit it is also the receiver id of a PayPal eCheck to the funder, a lender debit the G7 allowlist has not signed
#: off, so debits keep today's reading until the owner rules.
CREDIT_ONLY_ALIASES: frozenset[str] = frozenset({"LCFGROUPINC"})


# --- Hand-kept inputs of the ledger validator (tools/lender_ledger.py) ---

#: Spec section 2 (the owner's rulings of 2026-09-24 and the amendment): every payee the owner named, by
#: ledger group, with one public spelling of it. ``python -m tools.build_lender_registry --check`` refuses
#: a ledger that does not admit each one in its group (contract C10). Change it only on an owner ruling.
#: The owner ruling of 2026-09-25 respelled BlueVine and SmartPay (see their entries).
OWNER_NAMED_PAYEES: dict[str, tuple[tuple[str, str], ...]] = {
    "confirmed_lender": (
        ("OnDeck", "ONDECK"),
        ("Bitty", "BITTY ADVANCE"),
        ("Legend", "LEGEND ADVANCE FUNDING"),
        ("LG Funding", "LG FUNDING"),
        ("Hunter Caroline", "HUNTER CAROLINE"),
        ("CAN Capital", "CAN CAPITAL"),
        ("CanaCap", "CANACAP"),
        ("NMEF", "NMEF FUNDING"),
        ("Balboa", "BALBOA CAPITAL"),
        ("Navitas", "NAVITAS CREDIT CORP"),
        ("Deere", "JOHN DEERE FINANCIAL"),
        # Owner ruling 2026-09-27 (classification 5.3): the funders the false-positive hunt found missing.
        ("Flexibility Capital", "FLEXIBILITY CAPITAL"),
        ("Merit Business Funding", "MERIT BUSINESS FUNDING"),
        ("Essentia Funding", "ESSENTIA FUNDING"),
        # Owner ruling 2026-09-28: Idea Financial (Idea 247, Inc.) is a counted lender, no longer a line of credit.
        ("Idea Financial", "IDEA FINANCIAL"),
    ),
    "alternative_position": (
        ("SBA/EIDL", "SBA EIDL"),
        ("BDC", "BDC"),
        ("Affirm", "AFFIRM"),
        ("Amex loans", "AMERICAN EXPRESS BUSINESS LOAN"),
        ("Intuit", "INTUIT FINANCING"),
        ("Square", "SQUARE CAPITAL"),
        ("Shopify", "SHOPIFY CAPITAL"),
        ("PayPal", "PAYPAL WORKING CAPITAL"),
        ("Stripe", "STRIPE CAPITAL"),
        ("Amazon financing", "AMAZON CAPITAL SERVICES"),
    ),
    "line_of_credit": (
        ("Fundbox", "FUNDBOX"),
        # Owner ruling 2026-09-25: bare BLUEVINE takes Bluevine Bill Pay and checking rows.
        ("BlueVine", "BLUEVINE CAPITAL"),
        ("Kabbage", "KABBAGE"),
    ),
    "credit_card_payment": (
        ("American Express", "AMEX EPAYMENT ACH PMT"),
        ("Capital One", "CAPITAL ONE ONLINE PMT"),
        ("Chase", "CHASE CREDIT CRD EPAY"),
        ("Credit One", "CREDIT ONE BANK PAYMENT"),
        ("Concora", "CONCORA CREDIT PAYMENT"),
    ),
    "vehicle_financing": (
        ("GM Financial", "GM FINANCIAL"),
        ("Ford Credit", "FORD CREDIT"),
        ("Toyota Financial", "TOYOTA FINANCIAL"),
        ("Ally", "ALLY FINANCIAL"),
    ),
    "bank_name": (
        ("Truist", "TRUIST LN PYMT"),
    ),
    "lease_or_rental": (
        ("Progressive", "PROGRESSIVE LEASING"),
        # Owner ruling 2026-09-25: SMARTPAY SOL is SmartPay Solutions premium billing.
        ("SmartPay", "SMARTPAY LEASING"),
        ("Snap", "SNAP FINANCE"),
    ),
    "floor_plan_financing": (
        ("NextGear Capital", "NEXTGEAR CAPITAL"),
        ("Westlake Flooring", "WESTLAKE FLOORING"),
    ),
    "factoring": (
        ("RTS Financial", "RTS FINANCIAL"),
        ("OTR Capital", "OTR CAPITAL"),
        ("Apex Capital", "APEX CAPITAL"),
        ("BC Factoring", "BC FACTORING"),
    ),
    "premium_financing": (
        ("IPFS", "IPFS"),
        ("First Insurance Funding", "FIRST INSURANCE FUNDING"),
    ),
    # Owner ruling 2026-09-27 (classification 5.3): the Debt relief group. Resolve Capital, also named, is under
    # review (its printed originator is not tied to the negotiator), so it is not listed here.
    "debt_relief": (
        ("RAM Payments / Reliant", "RAM PAYMENTS"),
        ("Global Holdings", "GHLLC"),
        ("Tayne Law Group", "TAYNE LAW GROUP"),
    ),
}

#: Spec section 5: bare platform names appear only in OPERATING_REVENUE_SOURCE_ALIASES.
BARE_PLATFORM_NAMES: tuple[str, ...] = ("SQUARE", "SHOPIFY", "PAYPAL", "STRIPE", "INTUIT", "AMAZON", "AMZN")

#: Spec section 5: brands that also sell goods, and bare issuer and bank names. Alone, each may be an alias
#: only of CARD_ISSUER_CONTEXT_ALIASES or BANK_NAME_ALIASES, which the classifier reads only with payment or
#: loan wording. A known-payee or potential alias must name the financing business ("TOYOTA FINANCIAL").
BARE_BRAND_NAMES: tuple[str, ...] = (
    "ALLY", "AMERICAN EXPRESS", "AMEX", "APPLE", "BANK OF AMERICA", "BARCLAYS", "CAPITAL ONE", "CHASE", "CITI",
    "CITIBANK", "DEERE", "DISCOVER", "FORD", "GM", "HONDA", "HYUNDAI", "JOHN DEERE", "KIA", "NISSAN",
    "SYNCHRONY", "TOYOTA", "WELLS FARGO",
)

#: Owner ruling 2026-09-25: premium-finance spellings that may equal an alias of the hand-kept
#: INSURANCE_PROVIDER_ALIASES. The bare FIRST INSURANCE originator is FIRST Insurance Funding: its rows stay
#: insurance and are also flagged premium financing. The validator exempts exactly these spellings from its
#: hand-kept-alias rule, and only on a premium_financing entity.
PREMIUM_FINANCE_INSURER_ALIASES: tuple[str, ...] = ("FIRST INSURANCE",)

#: Owner ruling 2026-09-25: an entity of today's registry (the validator's BASELINE_REVISION) that a ledger
#: entity absorbs, mapped to that ledger entity. The validator reads the merged entity as held by its target:
#: it keeps no name of its own, and the aliases it loses need a "Move:" sentence in the target's notes.
MERGED_REGISTRY_ENTITIES: dict[str, str] = {"EBF HOLDINGS": "EVEREST BUSINESS FUNDING"}

#: Owner ruling 2026-09-25: an alias of today's registry (the validator's BASELINE_REVISION) that names a company
#: other than today's entity, mapped to the ledger entity of that company, which holds it. SMARTPAY SOL is
#: SmartPay Solutions premium billing, not the lease-to-own SmartPay. The validator leaves the alias out of today's
#: entity (it is neither lost nor that entity's first alias) and refuses a registry that reads it as any other
#: entity.
REATTRIBUTED_REGISTRY_ALIASES: dict[str, str] = {"SMARTPAY SOL": "SmartPay Solutions, LLC"}

#: Owner ruling 2026-09-25: ledger entities whose credits are the account holder's own sales, settled by the
#: platform: revenue, not financing proceeds. A D1 exception that S2 reads; their debits keep their group. The
#: validator refuses a name that is not an admitted ledger entity of a group whose credits D1 treats as
#: financing proceeds (analysis.flag_groups.FINANCING_STATES).
PAYOUT_CREDIT_ENTITIES: tuple[str, ...] = (
    "Sezzle Inc", "American First Finance, LLC", "PAYABILITY",
    # Owner ruling 2026-09-28 (true revenue spec, OQ2): a buy-now-pay-later provider's settlement to the merchant is
    # the merchant's own sale, so it is revenue, not financing proceeds.
    "AFFIRM", "Afterpay", "GreenSky", "Klarna Inc", "Sunbit",
    # Owner ruling 2026-10-02 (Q8): Cherry's payout to a practice for a patient-financed treatment is the practice's
    # own sale (CUSTOMER_FINANCING_PAYERS), under OQ2's consumer-side veto (the classifier's _OQ2_BNPL_ENTITIES).
    "Cherry Technologies, Inc.",
)

#: Owner ruling 2026-09-27 (classification 5.3): the printed forms, in the bank's field order, of admitted payees whose
#: bank prints the originator and the entry description apart, so no contiguous alias can match them (Chase's
#: 'ORIG CO NAME ... CO ENTRY DESCR' fields; Truist's entry description first). Keyed by ledger entity; each value is
#: a regular expression read on the normalized row, on DEBITS ONLY, when no alias matched. The Chase forms refuse a
#: row that holds two originator blocks (a merged row stays in review). tools/lender_ledger.py refuses an entity
#: that is not admitted in a known-payee group.
FIELD_ORDER_PAYEE_FORMS: dict[str, tuple[str, ...]] = {
    "American Express Loans": (
        r"^(?!.*\bORIG CO NAME\b.*\bORIG CO NAME\b).*\bORIG CO NAME AMERICAN EXPRESS ORIG ID [A-Z0-9]+ DESC DATE"
        r"(?: [A-Z0-9]+)? CO ENTRY DESCR LOAN(?: (?:PMT|PYMT|PAYMENT))?(?:SEC)?\b",
        r"^(?:ACH CORP (?:DEBIT|CREDIT) )?LOAN(?: (?:PMT|PYMT|PAYMENT))? AMERICAN EXPRESS\b",
    ),
    "American Express [credit card payment]": (
        r"^(?!.*\bORIG CO NAME\b.*\bORIG CO NAME\b).*\bORIG CO NAME AMERICAN EXPRESS ORIG ID\b"
        r"(?:(?!\bCO ENTRY\b).)*?\bCO ENTRY (?:[0-9]+ )?DESCR (?:ACH |RETRY )?(?:PAYMENT|PMT|PYMT|EPAYMENT)(?:SEC)?\b",
    ),
}


OPERATING_REVENUE_SOURCE_ALIASES: dict[str, tuple[str, ...]] = {
    "11-101 Signal R": ("11 101 SIGNAL R", "SIGNAL R"),
    "Adyen": ("ADYEN", "ADYEN PAYMENTS"),
    "Amazon Marketplace": (
        "AMAZON MARKETPLACE",
        "AMAZON SELLER",
        "AMZN MARKETPLACE",
        # 5.5 (true revenue spec §7.2): Amazon's real-time-rail payout, verified by recurrence only.
        "RTP CREDIT AMAZON COM",
    ),
    "Authorize.Net": ("AUTHORIZE NET", "AUTHORIZENET"),
    "Bambora": ("BAMBORA", "BAMB0RA"),
    "Chase Paymentech": ("CHASE PAYMENTECH", "PAYMENTECH"),
    "Clover": ("CLOVER", "CLOVER NETWORK", "CL0VER"),
    "DoorDash": ("DOORDASH", "DOOR DASH", "D00RDASH"),
    "Elavon": ("ELAVON", "ELAV0N"),
    "Etsy": ("ETSY", "ETSY PAYMENTS"),
    "Fiserv": ("FISERV", "FIRST DATA MERCHANT", "FIRST DATA CANADA"),
    "FreshBooks Payments": ("FRESHBOOKS PAYMENTS", "FRESH BOOKS PAYMENTS"),
    "Global Payments": ("GLOBAL PAYMENTS", "GL0BAL PAYMENTS", "GLOBALPAY", "GLOBAL PAIEMENTS"),
    "GoDaddy Payments": ("GODADDY PAYMENTS", "GO DADDY PAYMENTS"),
    "Grubhub": ("GRUBHUB", "GRUB HUB"),
    "Helcim": ("HELCIM", "HELC1M"),
    "Instacart": ("INSTACART", "INSTA CART"),
    "Lightspeed": ("LIGHTSPEED", "L1GHTSPEED"),
    "Moneris": ("MONERIS", "M0NERIS"),
    "Nuvei": ("NUVEI",),
    "PayPal": ("PAYPAL", "PAY PAL", "PAYPAI"),
    "QuickBooks Payments": (
        "QUICKBOOKS PAYMENTS",
        "QUICK BOOKS PAYMENTS",
        "INTUIT PAYMENTS",
    ),
    "Shopify Payments": ("SHOPIFY", "SHOPIFY PAYMENTS", "SH0PIFY"),
    "SkipTheDishes": (
        "SKIPTHEDISHES",
        "SKIP THE DISHES",
        "SKIPTHED1SHES",
    ),
    "Square": ("SQUARE", "SQUARE INC", "SQUARF", "SQ SETTLEMENT"),
    # 5.5 (§7.0, §7.2): Stripe-Treasury payouts of a connected platform (STP FBO) and Stripe Connect's
    # '<platform> - By Stri' cut read as Stripe.
    "Stripe": ("STRIPE", "STR1PE", "STP FBO", "BY STRI", "BY STRIPE"),
    "Toast": ("TOAST", "TOASTTAB", "T0AST"),
    "Uber Eats": ("UBER EATS", "UBEREATS", "UBFR EATS"),
    "Uber": (
        "UBER HOLDINGS C",
        "UBER HOLDINGS",
        "UBER H0LDINGS",
        "UBFR HOLDINGS",
        "UBER CANADA",
        "UBER BV",
        "UBER",
    ),
    "Wave Payments": ("WAVE PAYMENTS", "WAVEAPPS PAYMENTS"),
    "Worldpay": ("WORLDPAY", "WORLD PAY"),
    # 5.5 (true revenue spec §7.1): card processors, in the spellings the corpus prints. A processor's bare name
    # (SHIFT4, SUMUP, CLEARENT, SMARTTAB, BRAINTREE) and Jobber's cut joins only after its advance product is in
    # the lender ledger (PROCESSOR_ADVANCE_PRODUCTS). Task S1.5 (ledger55.json r2) cleared Shift4, SumUp, Clearent
    # and Jobber Payments; SmartTab and Braintree wait.
    "Heartland Payment Systems": (
        "HRTLAND PMT SYS TXNS", "HEARTLAND PMT SYS TXNS", "HEARTLAND PAYMENT SYSTEMS", "HEARTLAND PAYMEN",
    ),
    "SpotOn": ("SPOTON", "SPOTON VIA ASTRA"),
    "Clearent": ("CLEARENT", "CLEARENT LLC", "XPLOR PAY"),
    "Shift4": ("SHIFT4", "SHIFT4 PAYMENTS", "SHIFT4 PYMT PROC"),
    "SumUp": ("SUMUP",),
    "Jobber Payments": ("JOBBER BY STRI", "JOBBER BY STR", "JOBBER BY STRIPE"),
    "SmartTab": ("SMARTTAB PAY",),
    "TapGoods Payments": ("TGPAYMENTS",),
    "Cents": ("TRYCENTS", "TRYCENTS COM"),
    "Esquire Payment Solutions": ("ESQUIRE EPS DAILY DEP", "ESQUIRE EPS HELD DEP"),
    # 5.5 (§7.2, structural S43): vertical software that settles cards, in the spellings the corpus prints.
    # Squarespace Payments and Seamless print no corpus spelling and wait.
    "Vagaro": ("VAGARO",),
    "Mindbody": ("MINDBODY",),
    "Housecall Pro": ("HOUSECALL PRO",),
    "Wix Payments": ("WIX COM",),
    # 5.5 (§7.2): marketplaces and platforms.
    "Whatnot": ("WHATNOT INC", "FBO WHATNOT"),
    "Faire": ("FAIRE WHOLESALE",),
    "TikTok Shop": ("TIKTOK SHOP", "TIKTOK INC", "TIKTOK USA"),
    "eBay": ("EBAY COMMERCE INC",),
    "RepeatMD": ("REPEATMD", "REPEATMD MARKETP"),
    "Snackpass": ("SNACKPASS",),
    "ezCater": ("EZCATER",),
    "Menufy": ("MENUFY", "MENUFY COM"),
    "Groupon": ("GRPN MERCH SVCS",),
    "ClassPass": ("CLASSPASS", "CLASSPASS INC"),
    "Outdoorsy": ("OUTDOORSY",),
    "Brightwheel": ("BRIGHTWHEEL", "BRIGHTWHEE"),
    "Buildertrend": ("BUILDERTREND", "BUILDERTREND SOL"),
    "FieldPulse": ("FIELDPULSE",),
    # 5.5 (§7.3): vehicle-transport marketplaces paying carriers.
    "Super Dispatch": ("SUPER DISPATCH", "SUPERDISPATCH"),
    "Autosled": ("AUTOSLED",),
    # 5.5 (§7.8): dealer-only wholesale auto auctions, read on the originator segment only.
    "Manheim": ("MANHEIM US",),
    "ACV Auctions": ("ACV AUCTIONS",),
    "OPENLANE": ("OPENLANE INC", "BACKLOTCARS"),
    # 5.5 (§7.10): property-management payment platforms, verified by recurrence of their ACH payout only.
    "Buildium": ("BUILDIUM",),
    "AppFolio": ("APPFOLIO",),
    "Landlord Studio": ("LANDLORD STUDIO",),
}


OPERATING_REVENUE_SOURCE_TYPES: dict[str, str] = {
    "11-101 Signal R": "known_operating_counterparty",
    "Adyen": "merchant_processor",
    "Amazon Marketplace": "ecommerce_marketplace",
    "Authorize.Net": "customer_payment_platform",
    "Bambora": "merchant_processor",
    "Chase Paymentech": "merchant_processor",
    "Clover": "merchant_processor",
    "DoorDash": "delivery_marketplace",
    "Elavon": "merchant_processor",
    "Etsy": "ecommerce_marketplace",
    "Fiserv": "merchant_processor",
    "FreshBooks Payments": "invoice_and_receivables",
    "Global Payments": "merchant_processor",
    "GoDaddy Payments": "merchant_processor",
    "Grubhub": "delivery_marketplace",
    "Helcim": "merchant_processor",
    "Instacart": "delivery_marketplace",
    "Lightspeed": "merchant_processor",
    "Moneris": "merchant_processor",
    "Nuvei": "merchant_processor",
    "PayPal": "customer_payment_platform",
    "QuickBooks Payments": "invoice_and_receivables",
    "Shopify Payments": "ecommerce_platform",
    "SkipTheDishes": "delivery_marketplace",
    "Square": "merchant_processor",
    "Stripe": "merchant_processor",
    "Toast": "merchant_processor",
    "Uber Eats": "delivery_marketplace",
    "Uber": "delivery_marketplace",
    "Wave Payments": "invoice_and_receivables",
    "Worldpay": "merchant_processor",
    "Heartland Payment Systems": "merchant_processor",
    "SpotOn": "merchant_processor",
    "Clearent": "merchant_processor",
    "Shift4": "merchant_processor",
    "SumUp": "merchant_processor",
    "Jobber Payments": "invoice_and_receivables",
    "SmartTab": "merchant_processor",
    "TapGoods Payments": "merchant_processor",
    "Cents": "merchant_processor",
    "Esquire Payment Solutions": "merchant_processor",
    "Vagaro": "merchant_processor",
    "Mindbody": "merchant_processor",
    "Housecall Pro": "merchant_processor",
    "Wix Payments": "merchant_processor",
    "Whatnot": "ecommerce_marketplace",
    "Faire": "ecommerce_marketplace",
    "TikTok Shop": "ecommerce_marketplace",
    "eBay": "ecommerce_marketplace",
    "RepeatMD": "ecommerce_marketplace",
    "Snackpass": "delivery_marketplace",
    "ezCater": "delivery_marketplace",
    "Menufy": "delivery_marketplace",
    "Groupon": "booking_marketplace",
    "ClassPass": "booking_marketplace",
    "Outdoorsy": "booking_marketplace",
    "Brightwheel": "customer_payment_platform",
    "Buildertrend": "invoice_and_receivables",
    "FieldPulse": "invoice_and_receivables",
    "Super Dispatch": "transport_marketplace",
    "Autosled": "transport_marketplace",
    "Manheim": "wholesale_auto_auction",
    "ACV Auctions": "wholesale_auto_auction",
    "OPENLANE": "wholesale_auto_auction",
    "Buildium": "property_management_payments",
    "AppFolio": "property_management_payments",
    "Landlord Studio": "property_management_payments",
}

#: 5.5 (§7.2, §7.3): the operating reads that carry the platform vetoes (pay, financing, reversal and
#: person-to-person words): every read of these entities, and these aliases of older entities. A payout form always
#: carries them.
OPERATING_SOURCES_READ_WITH_VETOES: frozenset[str] = frozenset({
    "Whatnot", "Faire", "TikTok Shop", "eBay", "RepeatMD", "Snackpass", "ezCater", "Menufy", "Groupon", "ClassPass",
    "Outdoorsy", "Brightwheel", "Buildertrend", "FieldPulse", "Vagaro", "Mindbody", "Housecall Pro", "Wix Payments",
    "Super Dispatch", "Autosled",
})
OPERATING_ALIASES_READ_WITH_VETOES: frozenset[str] = frozenset({"RTP CREDIT AMAZON COM", "STP FBO"})

#: 5.5 (§7.2, structural S43): extra words that count as payout context for one operating source (read like
#: _OPERATING_CREDIT_CONTEXT_PATTERNS, as whole words).
OPERATING_SOURCE_CONTEXT_WORDS: dict[str, tuple[str, ...]] = {
    "Vagaro": ("DEPOSIT", "PAYOUT"),
    "Mindbody": ("DEPOSIT", "PAYOUT"),
    "Housecall Pro": ("DEPOSIT", "PAYOUT"),
    "Wix Payments": ("DEPOSIT", "PAYOUT"),
}

#: 5.5 (§7.1): a processor whose bare name joins OPERATING_REVENUE_SOURCE_ALIASES only once the lender ledger
#: admits its own advance product (an alternative position) or records, through the ledger's process, that it has
#: none. Keyed by operating entity: (the bare aliases, the ledger entity of the advance product, or None while the
#: ledger holds neither). tools/operating_registry.py refuses a bare alias in OPERATING_REVENUE_SOURCE_ALIASES
#: whose entry here names no admitted ledger entity and is not marked none-recorded.
PROCESSOR_ADVANCE_PRODUCTS: dict[str, tuple[tuple[str, ...], str | None]] = {
    # Task S1.5 (research ledger55.json r2; signed off 2026-09-29 under the owner's delegation): the admitted products.
    "Shift4": (("SHIFT4",), "Shift4 Capital"),
    "SumUp": (("SUMUP",), "SumUp Cash Advance"),
    "Jobber Payments": (("JOBBER BY STRI", "JOBBER BY STR", "JOBBER BY STRIPE"), "Jobber Capital"),
    "Clearent": (("CLEARENT",), "Xplor Capital"),
    # SmartTab (its no-product record) and Braintree (PayPal Working Capital) are unresolved in ledger55.json r2: they
    # wait.
    "SmartTab": (("SMARTTAB",), None),
    "Braintree": (("BRAINTREE",), None),
}
#: 5.5 (§7.1): processors the ledger's process found to have no advance product of their own (research round and
#: verdicts recorded in the ledger notes of the entity named there). Empty: S1.5's research round (ledger55.json r2)
#: left SmartTab's no-product record unresolved.
PROCESSORS_WITHOUT_ADVANCE_PRODUCT: frozenset[str] = frozenset()
#: 5.5 (§7.1, the ledger gate): the bare aliases of the processors the ledger has not cleared yet, by processor.
#: Derived, never hand-edited. The operating reader refuses an alias read that lies inside one of them ('BY STRI'
#: inside 'JOBBER BY STRI'), so no other entity reads the row while the processor waits.
GATED_PROCESSOR_ALIASES: dict[str, tuple[str, ...]] = {
    processor: bare
    for processor, (bare, product) in PROCESSOR_ADVANCE_PRODUCTS.items()
    if not (
        (product is not None and any(product in group for group in PAYEE_GROUP_REGISTRIES.values()))
        or processor in PROCESSORS_WITHOUT_ADVANCE_PRODUCT
    )
}
#: 5.5 (§7.1, the structural lens): TSYS / TransFirst, Vantiv, EVO Payments, Paysafe, North American Bancard /
#: Payanywhere, Priority Payment Systems, Payroc, CardConnect, Stax / Fattmerchant, Repay, Paya, NMI, Finix, WePay,
#: TD Merchant Solutions, Desjardins Monetico and Chase QuickAccept print no credit spelling in the corpus cache or the
#: tryout host's credit dump (searched read-only, 2026-09-29): none is an alias, and each waits for a printed spelling.

#: 5.6 (audit B3: I11, §7.11, §20): the merchant processors whose instant payout a bank may print as a card credit
#: (Thread Bank's Relay layout: 'Debit Card Credit: Stripe'), with the names each prints on that card credit, on its
#: ACH payout and on its ACH pull, read as whole words by the true-revenue pass's processor card-payout release alone
#: (analysis/true_revenue.py _processor_card_payouts), which the owner keeps off (2026-10-02, spec §19.1). The bare
#: INTUIT and POCKETSUITE are no operating-registry aliases (a bare INTUIT also prints Intuit's financing and tax
#: products), so they are read here only, and only beside the statement's own ACH activity of that processor.
#: Evidence: each pushes a merchant's balance to its debit card on request (Stripe Instant Payouts; QuickBooks Payments
#: Instant Deposit; Square Instant Transfer; PocketSuite's instant payouts), so such a card credit is the merchant's own
#: sales, not a card refund.
CARD_PAYOUT_PROCESSOR_NAMES: dict[str, tuple[str, ...]] = {
    "Stripe": ("STRIPE",),
    "QuickBooks Payments": ("INTUIT", "QUICKBOOKS", "QUICK BOOKS", "QBOOKS"),
    "Square": ("SQUARE", "SQUARE INC"),
    "PocketSuite": ("POCKETSUITE", "POCKET SUITE"),
}

#: 5.5 (§7.0): the width of the bank field that cuts a long originator name. Every operating alias longer than this
#: is also read at its first sixteen characters when the cut keeps two words and its last word has three letters.
OPERATING_ALIAS_CUT = 16


def _operating_alias_cut(alias: str) -> str | None:
    """The sixteen-character cut of one operating alias, or None when it has none (§7.0)."""
    normalized = normalize_transaction_description(alias)
    if len(normalized) <= OPERATING_ALIAS_CUT:
        return None
    cut = normalized[:OPERATING_ALIAS_CUT].rstrip()
    words = cut.split(" ")
    if len(words) < 2 or len(words[-1]) < 3:
        return None
    return cut


#: 5.5 (§7.0): the sixteen-character cuts of the operating aliases, by entity. Derived, never hand-edited;
#: tools/operating_registry.py refuses a cut that equals any other registry or ledger alias.
OPERATING_REVENUE_TRUNCATIONS: dict[str, tuple[str, ...]] = {
    entity: cuts
    for entity, aliases in OPERATING_REVENUE_SOURCE_ALIASES.items()
    if (cuts := tuple(dict.fromkeys(
        cut for alias in aliases
        if (cut := _operating_alias_cut(alias)) is not None
        and cut not in {normalize_transaction_description(other) for other in aliases}
    )))
}

#: What the classifier reads for an operating source: every alias and its sixteen-character cut.
OPERATING_REVENUE_READ_ALIASES: dict[str, tuple[str, ...]] = {
    entity: aliases + OPERATING_REVENUE_TRUNCATIONS.get(entity, ())
    for entity, aliases in OPERATING_REVENUE_SOURCE_ALIASES.items()
}

#: 5.5 (§7.2): platform payout forms. Each (label, pattern) names the platform together with its payout rail or
#: field layout, read on the credit's revenue text and on its joined originator and entry fields. A match names
#: the entity AND counts as payout context, so one row verifies.
OPERATING_SOURCE_PAYOUT_FORMS: dict[str, tuple[tuple[str, str], ...]] = {
    "Whatnot": (
        ("whatnot_fbo_form", r"\bFBO WHATNOT\b"),
        ("whatnot_rtp_form", r"\bRTP CREDIT WHATNOT INC\b"),
    ),
    "Faire": (("faire_order_form", r"\bFAIRE WHOLESALE\b.*\bORDER\b"),),
    "eBay": (
        ("ebay_payments_form", r"^(?=.*\bPAYMENTS\b)(?!.*\bRETURN(?:ED)?\b).*\bEBAY COM[A-Z0-9]{8}\b"),
        ("ebay_rtp_form", r"\bRTP (?:CREDIT|RCVD) EBAY COMMERCE INC\b"),
    ),
    "Amazon Marketplace": (
        ("amazon_payments_form",
         r"^(?=.*\bPAYMENTS\b)(?!.*\bRETURN(?:ED)?\b).*\bAMAZON C(?!ORPORATE\b|OM|APITAL|REDIT|ASH\b)[A-Z0-9]{8}\b"),
    ),
    "ClassPass": (("classpass_edi_form", r"\bCLASSPASS INC\b.*\bEDI PYMNTS\b"),),
    "ezCater": (("ezcater_payoneer_form", r"\bPAYONEER\b.*\bEZCATER\b"),),
    "Groupon": (("groupon_merchant_form", r"\bGRPN MERCH SVCS\b"),),
}


@dataclass(frozen=True)
class CardSettlementForm:
    """5.5 (§7.1): one card-settlement form. `pattern` is read on the credit's row before its receiver fields and on
    its joined originator and entry fields; `refusal`, read the same way, refuses the form; `entity` is the
    processor the form names (None for a generic form); `bank` limits the form to one bank's statements."""

    label: str
    pattern: str
    entity: str | None = None
    refusal: str | None = None
    bank: str | None = None


#: 5.5 (§7.0, §7.1): the card-settlement forms, in reading order. Every left boundary inside a form (its leading
#: token, its inner and required words, its lookahead vetoes and its refusal) is (?<![A-Z]), never \b, so a date glued
#: on the left ('01 02BANKCARD DEPOSIT', '01 02ELAN BANKCARD SETTLEMENT') never changes how a row reads while a glued
#: letter still blocks the word (owner ruling 2026-09-29); \b stays on the right of a word. The row-start branch of
#: brand_dep and dep_brand lets a leading date through, glued or spaced; square_checking_sales keeps its bare ^.
CARD_SETTLEMENT_CREDIT_FORMS: tuple[CardSettlementForm, ...] = (
    CardSettlementForm(
        "bankcard",
        r"^(?!.*(?<![A-Z])(?:BANKCARD CTR|BANKCARD CENTER|PREMIER BANKCARD|FIRST BANKCARD|ELAN|CARDMEMBER"
        r"|CARD SERVICES|CARD SVCS|CREDIT CARD)\b)(?=.*(?<![A-Z])(?:BANKCARD|BANKCD|BNKCD|BKCD|BKCRD|BNKCRD)\b)"
        r"(?=.*(?<![A-Z])(?:DEP|DEPOSITS?|DEPST|SETTLEMENT|SETTLE|SETLMT|SETL|STLMT|BTOT|MTOT)(?:SEC)?\b)",
        # S2.2 review: CO is a company's legal form, never the CO of a field label (Chase's CO ENTRY DESCR after a
        # blank DESC DATE, Bank of America's CO ID, a CO NAME), so 'BANKCARD DESC DATE CO ENTRY DESCR DEPOSIT' reads.
        refusal=(
            r"(?<![A-Z])(?:BANKCARD|BANKCD|BNKCD|BKCD|BKCRD|BNKCRD)(?: [A-Z]+){0,2} (?:LLC|INC|CORP|LTD|GROUP"
            r"|HOLDINGS|FUNDING|CAPITAL|FINANCIAL|PARTNERS|SOLUTIONS|SERVICES|SVCS|CO\b(?! ENTRY\b| DESCR\b| ID\b| NAME\b))\b"
        ),
    ),
    CardSettlementForm(
        "merch_dep",
        r"(?<![A-Z])(?:MERCHANT )?MERCH(?: SVCS)? (?:DEP|DEPOSITS?|SETL|SETTLE|SETLMT|STLMT|SETTLEMENT)(?:SEC)?\b",
    ),
    CardSettlementForm("mrchntsrvs", r"(?<![A-Z])DESCR MRCHNTSRVS(?:SEC)?\b"),
    CardSettlementForm("merch_svcs_setl_code", r"(?<![A-Z])MERCH(?:ANT)? SVCS?(?: DES)? [A-Z0-9]*SETL\b"),
    CardSettlementForm(
        "merchant_services_mid",
        r"(?<![A-Z])MERCHANT SERVI(?:CES?)?\b.*(?<![A-Z])(?:MID ?\d{6,}|TRANS SLIP)\b",
    ),
    CardSettlementForm(
        "brand_dep",
        r"(?:^(?:\d{1,2} \d{1,2} ?)?|(?<![A-Z])(?:MISC PAYMENT|COMPTE DIVERS|DIRECT DEPOSIT) )(?:(?:VSA|VISA|VI|MC"
        r"|MCD|MCARD|AMX|AMEX|DSC|DCVR|IDP|DEBITCD) )+DEP ?\d|(?<![A-Z])(?:(?:VSA|VISA|VI|MC|MCD|MCARD|AMX|AMEX|DSC"
        r"|DCVR|IDP|DEBITCD) )+DEP(?:\d|\b.*(?<![A-Z])(?:MSP|DIV|MERCH SVC)\b)",
    ),
    CardSettlementForm(
        "dep_brand",
        r"(?:^(?:\d{1,2} \d{1,2} ?)?|(?<![A-Z])(?:MISC PAYMENT|COMPTE DIVERS|DIRECT DEPOSIT) )DEP (?:VSA|VISA|VI|MC"
        r"|MCD|MCARD|AMX|AMEX|DSC|DCVR|IDP|DEBITCD) ?\d|(?<![A-Z])DEP (?:VSA|VISA|VI|MC|MCD|MCARD|AMX|AMEX|DSC|DCVR"
        r"|IDP|DEBITCD)\d*\b.*(?<![A-Z])(?:MSP|DIV)\b",
    ),
    CardSettlementForm(
        "gbl_brand", r"(?<![A-Z])(?:(?:VISA|MC|AMEXO?|IDP|DISC|DCVR) )?GBL (?:VI|MC|AX|IDP|DS|DC)\d*\b",
        entity="Global Payments",
    ),
    CardSettlementForm(
        "net_settle", r"(?<![A-Z])(?:DES|DESCR) NET (?:SETTLE|SETLMT|STLMT|SETL)(?:SEC)?\b",
        refusal=r"(?<![A-Z])(?:LAW|ATTORNEYS?|ESQ|TRUST|ESCROW|TITLE|CLAIMS?)\b",
    ),
    CardSettlementForm("batch_total", r"(?<![A-Z])[BM]TOT DEP\b"),
    # Audit B5 (I15): PNC prints the entry before the payer ('CORPORATE ACH DEPOSIT <ref> INTUIT <ref>'), the same
    # QuickBooks Payments merchant deposit the other layouts print 'INTUIT <ref> DEPOSIT'.
    CardSettlementForm(
        "intuit_deposit",
        r"(?<![A-Z])INTUIT \d{6,}(?: DES)? DEPOSIT\b|(?<![A-Z])DEPOSIT FROM INTUIT \d{6,}\b"
        r"|(?<![A-Z])INTUIT PYMT SOLN\b|(?<![A-Z])QBOOKS\b"
        r"|(?<![A-Z])ORIG CO NAME INTUIT \d+\b.*(?<![A-Z])DESCR DEPOSIT\b"
        r"|(?<![A-Z])CORPORATE ACH DEPOSIT \d{6,} INTUIT \d{6,}\b",
        entity="QuickBooks Payments",
        refusal=r"(?<![A-Z])(?:TAX|RFND|REFUND|QBC|CAPITAL|LOAN)\b",
    ),
    CardSettlementForm(
        "square_checking_sales", r"^(?:\d+ ACTIVITIES|CARD PAYMENT) SALES$", entity="Square", bank="SQUARE",
    ),
    CardSettlementForm(
        "network_settlement",
        r"(?<![A-Z])(?:AMERICAN EXPRESS|DISCOVER NETWORK)\b.*(?<![A-Z])(?:SETTLEMENT|SETL)\b|(?<![A-Z])AMEXO GBL\b"
        r"|(?<![A-Z])MISC PAYMENT AMEX BANK OF CANADA\b",
    ),
    CardSettlementForm(
        "generic_card_sales",
        r"(?<![A-Z])(?:VISA ?MC|CARD PROCESSING) (?:DEPOSIT|DEP|SETTLEMENT|SETL|STLM|STLMT)\b"
        r"|^(?!.*(?<![A-Z])(?:BALANCE|REFUND|REWARDS?)\b).*(?<![A-Z])(?:CREDIT CARD|CR CD|CC) (?:DEPOSIT|DEP"
        r"|SETTLEMENT|SETL|STLMT)\b",
    ),
    CardSettlementForm(
        "french_card_settlement", r"(?<![A-Z])REGLEMENT (?:CARTE|MARCHAND|COMMERCANT)\b|(?<![A-Z])DEPOT MARCHAND\b",
    ),
)

#: 5.5 (§7.8): the observed payout forms of the dealer-only wholesale auctions; any other auction row stays
#: unverified. Keyed by operating entity.
WHOLESALE_AUCTION_PAYOUT_FORMS: dict[str, tuple[str, ...]] = {
    "Manheim": (r"\bMANHEIM US (?:DES )?(?:ACH PAYMNT|EDI PYMNTS)\b",),
    "ACV Auctions": (
        r"\bACV AUCTIONS INC PAYMENTS\b",
        r"\bORIG CO NAME ACV AUCTIONS INC\b.*\bCO ENTRY DESCR PAYMENTS SEC CCD\b",
    ),
    "OPENLANE": (
        r"\bORIG CO NAME OPENLANE INC\b.*\bCO ENTRY DESCR OPENLANE SEC CCD\b",
        r"^BACKLOTCARS PAYMENT\b",
    ),
}
#: 5.5 (§7.8): the broad auction names a refund pair is found by, on debits and wire BNF lines.
WHOLESALE_AUCTION_REFUND_NAMES: dict[str, str] = {
    "Manheim": r"\bMANHEIM\b",
    "ACV Auctions": r"\bACV AUCTIONS\b",
    "OPENLANE": r"\bOPENLANE\b|\bBACKLOT ?CARS\b",
}
#: 5.5 (§7.7, T18): Blue-plan spellings that escape INSURANCE_PROVIDER_ALIASES. Read only while
#: HCCLAIMPMT_CLAIM_FIRST is off, when their HCCLAIMPMT claim payments are held with the insurer's.
BLUE_PLAN_CLAIM_PAYERS: tuple[str, ...] = (
    r"\bBCBS[A-Z]*\b", r"\bBLUE CROSS\b", r"\bBLUE CARE NETWORK\b", r"\bANTHEM BLUE\b", r"\bCAREFIRST\w*\b",
)

#: 5.6 (§7.7): healthcare payers that are not in INSURANCE_PROVIDER_ALIASES: Medicare contractors, state Medicaid
#: programs, TRICARE and VA Community Care, US health plans, pharmacy-benefit managers and claim-payment
#: platforms. Read on the credit's payer region, on a row with an electronic-payment form (Q6).
HEALTHCARE_PAYER_ALIASES: dict[str, tuple[str, ...]] = {
    "Noridian": ("NORIDIAN",),
    "Palmetto GBA": ("PALMETTO GBA",),
    "Novitas Solutions": ("NOVITAS",),
    "WPS Health Solutions": ("WPS",),
    "National Government Services": ("NATIONAL GOVERNMENT SERV",),
    "CGS Administrators": ("CGS ADMINISTRATORS",),
    "First Coast Service Options": ("FIRST COAST SERVICE",),
    "State Medicaid program": ("MEDICAID", "MEDI CAL"),
    "Medicare": ("MEDICARE",),
    "TRICARE": ("TRICARE",),
    "VA Community Care": ("VA CCN",),
    "Aetna": ("AETNA",),
    "Cigna": ("CIGNA",),
    "Humana": ("HUMANA",),
    "UnitedHealthcare": ("UNITEDHEALTHCARE", "UNITED HEALTHCARE", "UHC"),
    "Optum": ("OPTUM", "OPTUMRX", "OPTUMHEALTH"),
    "Molina Healthcare": ("MOLINA HC", "MOLINA HEALTHCARE"),
    "WellCare": ("WELLCARE",),
    "Centene": ("CENTENE",),
    "Anthem": ("ANTHEM",),
    "Express Scripts": ("EXPRESS SCRIPTS",),
    "CVS Caremark": ("CAREMARK",),
    "Zelis": ("ZELIS",),
    "ECHO Health": ("ECHO HEALTH", "HNB ECHO", "PNC ECHO"),
    "InstaMed": ("INSTAMED",),
    "VPay": ("VPAY",),
    "PaySpan": ("PAYSPAN",),
}

#: 5.6 (§8.7, Q7): auto lenders that pay dealers, beside the vehicle_financing registry. A credit from one of them
#: that prints a dealer-funding word is the dealer's revenue. Until S1 admits one into the ledger's
#: vehicle-financing group, its other credits are held (financing_named_payer). Never Westlake Flooring. Never GLS's
#: trade name GLS AUTO (S1.5's verify round: body shops and a used-car dealer trade under it; the ledger dropped it too).
#: Never Suncoast Credit Union (S4.3 review): S1.5 did not admit it, and its statements print the holder's own funding
#: transfers as ACCT FUND; its dealer funding verifies through Q7's credit-union arm alone (two or more VHCL PURCH).
DEALER_FUNDING_PAYERS: dict[str, tuple[str, ...]] = {
    "Westlake Financial": ("WESTLAKE FINANCIAL", "WESTLAKE FINANCI", "WESTLAKE PORTFOL"),
    "United Auto Credit": ("UNITED AUTO CREDIT", "UNITED AUTO CRED"),
    "Strike Acceptance": ("STRIKE ACCEPTANCE", "STRIKEACCEPTANCE"),
    "Professional Financial Services (PFS)": ("PROF FIN SER PFS",),
    "CU Direct": ("CU DIRECT", "CUDL"),
    "Credit Acceptance": ("CREDIT ACCEPTANCE", "CREDITACCEPTANCE"),
    "Exeter Finance": ("EXETER FINANCE", "EXETERFINANCELLC"),
    "Flagship Credit Acceptance": ("FLAGSHIP CREDIT",),
    "GLS Auto": ("GLOBAL LENDING SERVICES",),
    "Santander Consumer": ("SANTANDER CONSUMER",),
    "Chrysler Capital": ("CHRYSLER CAPITAL",),
    "GM Financial": ("GM FINANCIAL",),
    "Toyota Financial": ("TOYOTA FINANCIAL",),
    "Honda Financial": ("HONDA FINANCIAL", "AMERICAN HONDA FINANCE"),
    "Nissan Motor Acceptance": ("NISSAN MOTOR ACC", "NISSAN MOTOR ACCEPTANCE"),
    "CarMax Auto Finance": ("CARMAX AUTO FINANCE",),
    "Ally": ("ALLY FINANCIAL",),
    "American Credit Acceptance": ("AMERICAN CREDIT ACC", "AMERICAN CREDIT ACCEPTANCE"),
    "Regional Acceptance": ("REGIONAL ACCEPTAN", "REGIONAL ACCEPTANCE"),
    "Nicholas Financial": ("NICHOLAS FINANCIAL",),
    "Lendbuzz": ("LENDBUZZ",),
}

#: 5.6 (A3-H, §8.9; lender-scope ruling 2026-09-24: factoring payouts are revenue, counted and flagged, never
#: verified): freight-factoring payers whose credits the true-revenue pass alone reads (analysis/true_revenue.py), in
#: the spelling the statements print. Not lender-ledger entities (the ledger's factoring group renders
#: FACTORING_ALIASES, whose payee group reads debits and flags too): a credit from one is counted and flagged as a
#: factoring payout (factoring_payout), never verified by any rule nor counted toward a repeat, and the alias is read
#: only as the whole payer name (the ACH originator or the wire sender, a company form after it). Evidence: Love's
#: Solutions, LLC does business as Love's Financial, the Love's travel-stop group's freight-factoring provider
#: (loves.com/en/financial-services/freight-factoring; the BBB lists it as a factoring service, Oklahoma City).
FACTORING_PAYOUT_PAYERS: dict[str, tuple[str, ...]] = {
    # A3-H review 2: the entity prints its apostrophe both ways, spaced and dropped.
    "Love's Solutions, LLC (Love's Financial)": ("LOVE S SOLUTIONS", "LOVES SOLUTIONS"),
}

#: Owner ruling 2026-10-02 (the underwriter's Q11 (b); audit I45): the equipment auctions and the consumer car buyers
#: that pay a seller for a vehicle or a piece of equipment, each public, read by the true-revenue pass alone
#: (analysis/true_revenue.py asset_sale_platform) and only as the whole payer name (the ACH originator or the wire
#: sender, read as FACTORING_PAYOUT_PAYERS is read: company forms, entry words, references, a DBA tail or a B/O address
#: after the alias, and a seller's word): Ritchie Bros. (RB Global, rbglobal.com) and its IronPlanet marketplace,
#: Purple Wave (purplewave.com), BigIron Auctions (bigiron.com; R2-B12's glued or AUCTION-spaced forms), GovDeals
#: (govdeals.com), Copart (copart.com), Insurance Auto Auctions (IAA, iaai.com), Carvana's and CarMax's and Peddle's
#: and Vroom's purchases of a car from its owner. Never CarMax Auto Finance (an auto lender paying dealers, §8.7) nor
#: CarMax Business Services (the entity that pays CarMax's vendors): a longer name is another payer. Never Proxibid: it
#: remits the buyers' money to the auction house that ran the sale, the auctioneer's own revenue, and stays on
#: SECTION_15_DEFERRED_PAYERS. On a statement that shows no dealer evidence, their seller payout is asset-sale proceeds
#: (non_revenue, asset_sale_proceeds). No debit, flag or lender reading.
ASSET_SALE_PAYERS: dict[str, tuple[str, ...]] = {
    "Ritchie Bros. (RB Global)": (
        "RITCHIE BROS", "RITCHIE BROS AUCTIONEERS", "RITCHIE BROS AUCTIONEERS AMERICA", "RITCHIE BROTHERS",
        "RITCHIE BROTHERS AUCTIONEERS", "RB GLOBAL",
    ),
    "IronPlanet": ("IRONPLANET", "IRON PLANET"),
    "Purple Wave": ("PURPLE WAVE", "PURPLEWAVE", "PURPLE WAVE AUCTION"),
    "BigIron Auctions": ("BIGIRON", "BIGIRON AUCTIONS", "BIG IRON AUCTION", "BIG IRON AUCTIONS"),
    "GovDeals": ("GOVDEALS", "GOV DEALS"),
    "Copart": ("COPART",),
    "Insurance Auto Auctions (IAA)": ("IAA", "INSURANCE AUTO AUCTIONS", "INSURANCE AUTO AUCTION"),
    "Carvana": ("CARVANA",),
    "CarMax": ("CARMAX", "CARMAX AUTO SUPERSTORES", "CARMAX AUTO SUPERSTORE"),
    "Peddle": ("PEDDLE",),
    "Vroom": ("VROOM", "VROOM AUTOMOTIVE"),
}
#: Owner ruling 2026-10-02 (Q11 (b)): the platforms that also pay their towing and transport vendors, whose payout is
#: read as a seller's only beside a seller's word (SELLER, CONSIGN..., PAYOUT, PROCEEDS).
ASSET_SALE_SELLER_WORD_ONLY: frozenset[str] = frozenset({"Copart", "Insurance Auto Auctions (IAA)"})

#: Owner ruling 2026-10-02 (Q8; I17): lease-to-own and patient financiers whose merchant payouts are the merchant's
#: sales, counted and flagged, never verified, like OQ2's BNPL settlements; a one-off lump sum is held until sourced;
#: read by the true-revenue pass alone (analysis/true_revenue.py _customer_financier), on the payer region; no debit,
#: flag or lender reading; each key is a ledger entity (tools/lender_ledger.customer_financing_problems). A bare CHERRY
#: is Cherry only when the whole region is CHERRY plus company or entry words ('CHERRY FUNDING', 'CHERRY INC'); a
#: longer name is another payer ('CHERRY HILL PLUMBING LLC'). KATAPULT ENGINEERING and KATAPULT PRO (KatapultPro,
#: pole-attachment software) are a namesake, never this lessor. SNAP LOAN FUNDING is read only in Snap's merchant form
#: (the pass's _SNAP_MERCHANT_FUNDING: 'SNAP LOAN FUNDING F<digits> <merchant>'); a loan to the holder stays a loan.
CUSTOMER_FINANCING_PAYERS: dict[str, str] = {
    "SNAP Finance": r"(?<![A-Z])SNAP (?:FINANCE|LOAN FUNDING)\b",
    "Koalafi": r"(?<![A-Z])KOALAFI\b",
    "Cherry Technologies, Inc.": (
        r"^CHERRY(?: (?:TECHNOLOGIES|TECHNOLOGI|TECHNOLOG|TECHNOL|TECH|INC|FUNDING|PAYMENTS?|PMT|PAYOUTS?|MERCHANT"
        r"|CCD|PPD))*$|(?<![A-Z])(?:CHERRY TECHNOL\w*|CHERRYPAY)\b"
    ),
    "Acima": r"(?<![A-Z])ACIMA\b",
    "Terrace Finance": r"(?<![A-Z])TERRACE FINANCE\b",
    "Wisetack": r"(?<![A-Z])WISETACK\b",
    "Katapult": r"(?<![A-Z])KATAPULT\b(?! (?:ENGINEERING|PRO)\b)",
    "Progressive Leasing": r"(?<![A-Z])(?:PROGRESSIVE LEASIN\w*|PROGRESSIVELEASE|PROG LEASING)\b",
}

#: Owner ruling 2026-10-02 (Q8): the names of CUSTOMER_FINANCING_PAYERS' financiers, read with the receiver field's
#: value removed (analysis/true_revenue.py compiles it): a row that names one of them is never verified by Q5 or Q6 and
#: never counts toward a Q5 or Q6 repeat, wherever the name prints (KATAPULT with the same namesake lookahead).
#: SECTION_15_DEFERRED_PAYERS' ACIMA|KATAPULT|KOALAFI line overlaps it and is left as it is.
CUSTOMER_FINANCING_NAMES: str = (
    r"(?<![A-Z])(?:SNAP FINANCE|SNAP LOAN FUNDING|KOALAFI|ACIMA|TERRACE FINANCE|WISETACK"
    r"|KATAPULT(?! (?:ENGINEERING|PRO)\b)|PROGRESSIVE LEASIN\w*|PROGRESSIVELEASE|PROG LEASING|CHERRY TECHNOL\w*"
    r"|CHERRYPAY)\b"
)

#: 5.6 (§7.5, the standing rule; S4.2 review I6b): brokerage, investing and crypto-exchange platforms, as a regular
#: expression read on the row before its receiver fields (analysis/true_revenue.py compiles it). A credit from one is
#: the owner's own money coming back (owner money never becomes revenue): held as non_sale_purpose. Audit B8 (I28;
#: standard G2): and the crypto exchanges and retail brokerages it did not name, each public: Kraken and its operator
#: Payward, Inc. (kraken.com/legal: 'Payward Interactive, Inc.', printed after FBO on its wires), Binance.US and its
#: operator BAM Trading Services Inc. (binance.us/terms), Bitstamp, Uphold, BlockFi, Bakkt, Paxos, Apex Clearing
#: (apexfintechsolutions.com, a retail brokerages' clearing firm), M1 Finance (m1.com); Coinbase's name split by a line
#: wrap ('COINBA SE'); and Fidelity's brokerage ACH form ('P FIDELITY'; a bare FIDELITY is a bank's or a title firm's
#: name too). Never a custodian or a private bank (BNY Mellon, Pershing, Northern Trust): a customer's tuition or
#: invoice paid from a brokerage account is still the customer's payment.
OWNER_MONEY_PLATFORMS: str = (
    r"(?<![A-Z])(?:SCHWAB|ROBINHOOD|COINBASE|WEBULL|AMERITRADE|E ?TRADE|INTERACTIVE BROKERS|MERRILL (?:EDGE|LYNCH)"
    r"|FIDELITY (?:BROKERAGE|INVESTMENTS?)|VANGUARD (?:MARKETING|GROUP|BROKERAGE|FIDUCIARY|INVESTMENTS?|FUNDS?)"
    r"|CRYPTO COM|GEMINI TRUST"
    r"|KRAKEN|PAYWARD|BINANCE|BAM TRADING|BITSTAMP|UPHOLD|BLOCKFI|BAKKT|PAXOS|APEX CLEARING|M1 FINANCE|COINBA SE"
    r"|P FIDELITY)\b"
)

#: Audit B6 (I23; §8.1 T4, Q6 "lenders never count", standard C2): banks that lend to small businesses on their own
#: account or as a fintech's lender of record, as a regular expression read on a credit's payer region
#: (analysis/true_revenue.py compiles it). Their credit is more often loan proceeds or the holder's own funds than a
#: customer's payment: held as financing_named_payer, which a person may review. Credits only: no debit alias (the
#: delegated decision of 2026-09-25 keeps a bare CELTIC BANK out of the debit tables). Celtic Bank (Salt Lake City, an
#: SBA lender and the issuing bank of OnDeck's loans and of Bluevine's line of credit, celticbank.com; the ledger's
#: 'Celtic Bank [bank name]' and 'Celtic Bank (Bluevine line of credit)' records); Newtek Bank, N.A. (Newtek One's
#: national bank, an SBA 7(a) lender, newtekone.com). Audit round 2, R2-B03 (R05): Northeast Bank (Portland ME, a
#: national SBA and USDA lender, northeastbank.com; the ledger's 'Northeast Bank' alternative position, whose aliases
#: are its SBA repayment spellings only), whose credit printing its bare name is held the same way.
LENDING_BANK_CREDIT_PAYERS: str = r"(?<![A-Z])(?:CELTIC BANK|NEWTEK BANK|NORTHEAST BANK)\b"

#: Audit B6 (I49; Q8, §8.1 payroll_or_salary): earned-wage access providers, whose push to an account is a worker's
#: wages from another company paid early, as a regular expression read on the row before its receiver fields
#: (analysis/true_revenue.py compiles it): held as payroll_or_salary. PayActiv (payactiv.com) and DailyPay
#: (dailypay.com) are employer-sponsored earned-wage access providers. Glued as they print; a spaced 'DAILY PAY' is
#: a payer's own words.
EARNED_WAGE_ACCESS_PAYERS: str = r"(?<![A-Z])(?:PAYACTIV|DAILYPAY)\b"

#: 5.6 (§15, §19 OQ4; S4.2 review I6a): the payers of the deferred family items, which stay counted and flagged until
#: the owner rules on each, as a regular expression read with the receiver field's value removed
#: (analysis/true_revenue.py compiles it): Q5 and Q6 never verify them, and they never count toward a Q5 or Q6 repeat.
#: The registry's own deferred sources (PayPal, TikTok creator payouts, Super Dispatch's quick-pay, Outdoorsy and
#: RepeatMD, AppFolio, the auctions' vendor payments) are left to the operating registry.
SECTION_15_DEFERRED_PAYERS: str = (
    # §7.3 (structural S15): individuals' gig income.
    r"(?<![A-Z])(?:LYFT|SHIPT|POSTMATES|ROADIE|AMAZON FLEX|WALMART SPARK|SPARK DRIVER)\b"
    # §7.2: fintech EFT, iink and GoodLeap; Payoneer's wallet withdrawals.
    r"|(?<![A-Z])(?:IINK|GOODLEAP|PAYONEER)\b"
    # §7.2, §15: tax-preparer fee disbursements and SBTPG.
    r"|(?<![A-Z])(?:SBTPG|SANTA BARBARA TAX|TAX PRODUCTS|TAX PROC\w*)\b"
    # §7.6 arm C, §15: EBT settlements and child-care subsidies.
    r"|\b(?:EBT|CCDF|CACFP)\b"
    # §7.7: Canadian benefit carriers, RBC's claim label, NEMT brokers and CLMEFT.
    r"|(?<![A-Z])(?:SUN LIFE|MANULIFE|CANADA LIFE|EQUITABLE LIFE|GREAT WEST LIFE|ALBERTA BLUE CROSS"
    r"|DESJARDINS (?:INSURANCE|ASSURANCE\w*|SECURITE)|HEALTH DENTAL CLAIM|CLMEFT|MODIVCARE|LOGISTICARE"
    r"|MEDICAL TRANSPORTATION MANAGEMENT|SOUTHEASTRANS|VERIDA)\b"
    # §7.12 (structural S58): payables platforms that also move the business's own funds.
    r"|(?<![A-Z])(?:TIPALTI|MELIO|NVOICEPAY|MINERALTREE|CORPAY)\b"
    # §7.1, §15: Applied Systems' agency-bill premium, lease-to-own payers, construction draws and progress billing,
    # eCommission's commission advances.
    r"|(?<![A-Z])(?:APPLIED SYSTEMS|ACIMA|KATAPULT|KOALAFI|PROGRESS BILLING|ECOMMISSION)\b"
    # Audit B8 (I45; §15 "auction vendor payments and non-dealer consignors", OQ4): the equipment auctions' and the
    # consumer car buyers' seller payouts, each public: Ritchie Bros. (RB Global) and its IronPlanet, Purple Wave,
    # BigIron, GovDeals and Proxibid, Carvana's payout to a car's seller, CarMax (never its auto-finance arm, CarMax
    # Auto Finance, an auto lender paying dealers, §8.7), Peddle and Vroom. Copart and IAA (Insurance Auto Auctions)
    # also pay their towing and transport vendors, so only their seller payments (a seller or consignor word) are read.
    # Audit round 2, R2-B12 (R37): BigIron as it prints its own name, glued (BIGIRON) or spaced before AUCTION or
    # AUCTIONS (bigiron.com, BigIron Auctions); a spaced 'BIG IRON <name>' is another business ('BIG IRON TRUCKING LLC').
    r"|(?<![A-Z])(?:RITCHIE BROS|RB GLOBAL|IRON ?PLANET|PURPLE WAVE|BIGIRON|BIG IRON AUCTIONS?|GOV ?DEALS|PROXIBID"
    r"|CARVANA PAYOUT|CARMAX(?! AUTO\b)|PEDDLE|VROOM)\b"
    r"|(?:(?<![A-Z])(?:COPART|INSURANCE AUTO AUCTIONS?)|\bIAA)\b(?=.*(?<![A-Z])(?:SELLER|CONSIGN\w*)\b)"
)

#: 5.6 (§5.2, Q4; S4.2 re-review fix 1b): the sending banks a person-to-person row may print beside or instead of the
#: sender ('ZELLE CREDIT BANK OF AMERICA'), normalized. A bank's name is never the sender's name. A single word is
#: listed only when no person or business is commonly named so (Desjardins is also a surname: its caisse is listed).
#: Audit round 2, R2-B03 (R05): MSPBNA (Morgan Stanley Private Bank, National Association, Morgan Stanley's national
#: bank, morganstanley.com) and ALLY BANK (Ally Financial's online bank, ally.com), which the same layouts print as a
#: transfer's or an ACH pull's only name.
P2P_SENDING_BANK_NAMES: tuple[str, ...] = (
    "BANK OF AMERICA", "BK OF AMERICA", "BOFA", "WELLS FARGO", "JPMORGAN CHASE", "JP MORGAN CHASE", "CHASE BANK",
    "CITIBANK", "US BANK", "U S BANK", "PNC BANK", "TD BANK", "TRUIST", "CAPITAL ONE", "NAVY FEDERAL", "FIFTH THIRD",
    "KEYBANK", "CITIZENS BANK", "REGIONS BANK", "HUNTINGTON BANK", "SANTANDER BANK", "USAA", "ROYAL BANK", "RBC",
    "SCOTIABANK", "BMO", "CIBC", "TD CANADA TRUST", "CAISSE DESJARDINS", "NATIONAL BANK", "BANQUE NATIONALE",
    "MSPBNA", "ALLY BANK",
)

#: 5.6 (§8.1, A3 review): the short forms a statement's bank prints for its own name. Each entry is (the words that
#: name the bank inside the statement's bank field, the forms it prints), all normalized; a bank field (Statement.bank)
#: that contains one of the first as whole words, in any case, reads the second ('Royal Bank of Canada', 'RBC Royal
#: Bank' and 'Banque Royale du Canada' all name RBC; A3 review round 2). A bare ROYAL BANK is no marker: it also names
#: the Royal Bank of Scotland and Royal Bank America (round 3). The bank's whole normalized name is read too, for every
#: bank. Before currency-conversion wording, the bank's own name names no payer ('ROYAL FOREIGN EXCHANGE DEPOSIT' on a
#: Royal Bank of Canada statement is the holder's own conversion).
STATEMENT_BANK_PRINTED_NAMES: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (
        ("ROYAL BANK OF CANADA", "RBC ROYAL BANK", "RBC", "BANQUE ROYALE"),
        ("ROYAL BANK OF CANADA", "RBC ROYAL BANK", "ROYAL BANK", "ROYAL", "RBC", "BANQUE ROYALE DU CANADA",
         "BANQUE ROYALE"),
    ),
)


# Compatibility import for extensions written against classification version 3.0.
VERIFIED_REVENUE_ALIASES = OPERATING_REVENUE_SOURCE_ALIASES


INSURANCE_PROVIDER_ALIASES: dict[str, tuple[str, ...]] = {
    "Co-operators": (
        "CO OPERATORS",
        "COOPERATORS",
        "THE CO OPERATORS",
        "C0 OPERATORS",
        "C0OPERATORS",
        "CO OPERAT0RS",
        "C0 OPERAT0RS",
    ),
    "Intact Insurance": ("INTACT INSURANCE", "INTACT"),
    "Aviva": ("AVIVA INSURANCE", "AVIVA"),
    "Wawanesa": ("WAWANESA INSURANCE", "WAWANESA"),
    "TD Insurance": ("TD INSURANCE", "TD GENERAL INSURANCE"),
    "RBC Insurance": ("RBC INSURANCE", "ROYAL BANK INSURANCE"),
    "Desjardins Insurance": ("DESJARDINS INSURANCE", "DESJARDINS ASSURANCES"),
    "Progressive": (
        "PROGRESSIVE INSURANCE",
        "PROGRESSIVE CASUALTY",
        "PROGRESSIVE INS",
        "ASI PROGRESSIVE",
    ),
    "State Farm": ("STATE FARM INSURANCE", "STATE FARM"),
    "Allstate": ("ALLSTATE INSURANCE", "ALLSTATE"),
    "GEICO": ("GEICO INSURANCE", "GEICO"),
    "Liberty Mutual": ("LIBERTY MUTUAL INSURANCE", "LIBERTY MUTUAL"),
    "Travelers": ("TRAVELERS INSURANCE", "TRAVELERS INDEMNITY"),
    "The Hartford": ("THE HARTFORD INSURANCE", "HARTFORD INSURANCE"),
    "Chubb": ("CHUBB INSURANCE", "CHUBB"),
    "Zurich": ("ZURICH INSURANCE",),
    "Blue Cross Blue Shield": ("BLUE CROSS BLUE SHIELD", "BCBSM", "BCBS"),
    "Certas Insurance": ("CERTAS H AND A INS", "CERTAS INSURANCE", "CERTAS"),
    "Erie Insurance": ("ERIE INSURANCE",),
    "First Insurance": ("FIRST INSURANCE",),
    "HUB International": ("HUBINTERNATIONAL INSURANCE", "HUB INTERNATIONAL INSURANCE"),
    "Kingstone Insurance": ("KINGSTONE INSURANCE",),
    "Thimble Insurance": ("THIMBLE INSURANCE",),
}


#: Audit I26 (by Q6 of 2026-09-28, "insurers never count", and the last sentence of the underwriter's Q2 (2026-10-02)
#: option the owner picked, "a one-off claim paid to a business on its own policy stays out"; R2-OW07): carriers whose
#: credits print no insurer word, each a public insurer, as regular expressions the true-revenue pass alone reads
#: (analysis/true_revenue.py insurer_credit_brand wraps each in (?<![A-Z])(?:...)(?![A-Z])) on a credit's payer region
#: without the holder's names. CREDIT-ONLY: classify_transaction's insurance rule never reads it, no debit reads it and
#: no record carries it, so INSURANCE_PROVIDER_ALIASES, detection.insurance_providers and the lender census (G7) are
#: untouched. A brand INSURANCE_PROVIDER_ALIASES also names is keyed by that entity's name, spelled identically
#: ('Travelers'), so the carrier is one key however it prints. Farmers Insurance Group (farmers.com; FARMERS NEW WORLD
#: LIFE, Farmers Insurance of Salem; a bare IN only as the cut at the name's end, never 'FARMERS IN BLOOM', and no EXCH
#: arm: 'FARMERS EXCHANGE BANK'); American Family Insurance (amfam.com; never AMERICAN FAMILY CARE, the urgent-care
#: chain, or a dental practice); Safeco Insurance (safeco.com, Liberty Mutual's); Hiscox (hiscox.com); Aflac
#: (aflac.com); GAINSCO (gainsco.com); AmTrust Financial (amtrustfinancial.com; never AMTRUST BANK, TITLE or REALTY);
#: National General (nationalgeneral.com, Allstate's; never NATIONAL GENERAL CONTRACTORS); Travelers (travelers.com;
#: its indemnity, casualty, property and commercial lines and its agents' PI COMM, never TRAVELERS CASH, PROPANE or
#: COMMUNITY). Left out on purpose: Sun Life, Manulife, Canada Life and Great-West, Equitable Life and Desjardins (the
#: Canadian benefit carriers SECTION_15_DEFERRED_PAYERS defers, whose bare rows are health-plan claims or commissions);
#: Green Shield (a health-benefit carrier); Beneva, SSQ and La Capitale (BENEVA BLVD is a street); Berkshire Hathaway
#: (also a real-estate brokerage); a bare PROGRESSIVE (Progressive Leasing, the underwriter's Q8); Nationwide
#: (NATIONWIDE SECUR is a broker-dealer).
#: R2-OW07 review round 1: a brand's INS is the insurer word or its cut (INS, INSU, INSUR...), never another word's
#: first letters (FARMERS INSTITUTE, FARMERS INSTANT, NATIONAL GENERAL INSTRUMENTS); Travelers' property line reads
#: only before an insurer word (CAS, CASUALT..., INS, INSUR...) or at the name's end, never a property manager
#: (TRAVELERS PROPERTY MANAGEMENT). National General's bare name stays read: a 16-letter field cuts the insurer and
#: NATIONAL GENERAL CONTRACTORS alike (an accepted over-hold, held and reviewable).
INSURER_CREDIT_BRANDS: dict[str, tuple[str, ...]] = {
    "Farmers": (r"FARMERS (?:INS(?:UR\w*|U)?|FARMERS|GROUP|NEW WORLD|OF SALEM)", r"FARMERS IN(?! ?[A-Z])"),
    "American Family": (
        r"AMERICAN FAMILY(?! ?[A-Z])", r"AMERICAN FAMILY (?:INS(?:UR\w*|U)?|MUT\w*|LIFE|DES|AGENTS?)(?![A-Z])",
        r"AMFAM",
    ),
    "Safeco": (r"SAFECO",),
    "Hiscox": (r"HISCOX",),
    "Aflac": (r"AFLAC",),
    "Gainsco": (r"GAINSCO",),
    "AmTrust": (r"AMTRUST(?! (?:BANK|TITLE|REALTY)(?![A-Z]))",),
    "National General": (
        r"NATIONAL GENERAL(?! ?[A-Z])",
        r"NATIONAL GENERAL (?:INS(?:UR\w*|U)?|ASSUR\w*|PAYMENT|PMT|HOLDINGS)(?![A-Z])",
    ),
    "Travelers": (
        r"TRAVELERS ?(?:INDEMN\w*|PI ?COMM|CASUALT\w*|CAS"
        r"|PROP(?:ERTY)?(?= (?:CAS|CASUALT\w*|INS|INSUR\w*)(?![A-Z])|(?! ?[A-Z]))|COMM(?:ERCIAL|L)?)",
    ),
}


# Reserved for transaction codes whose meaning is specific to an institution.
# A global alias is never added here: it is an entity of the curated ledger
# (docs/lender-registry-ledger.json), which tools/build_lender_registry.py renders
# into the GENERATED tables above.
BANK_SPECIFIC_LENDER_ALIASES: dict[str, dict[str, tuple[str, ...]]] = {}
