"""
build_plans_json.py
-------------------
Builds tt_all_plans.json: every plan, with a full price history.

HOW THE HISTORY WORKS (append-only, you never edit or delete old rows):
  * Each plan has a stable `id`.
  * Each price a plan has had is its own row, with an `effective_date`.
  * When a price changes, ADD a new row with the same `id`, the new price and
    the date it starts. Leave the old row alone.
  * The site shows, per `id`, the newest row whose effective_date is today or
    earlier. So a future-dated row stays hidden until that day arrives.

Dates from TATT schedules are "first date I saw this price" (31 Mar or 30 Jun),
not necessarily the day the operator changed it. Dates from operator notices
are the real start date.

Usage:  python build_plans_json.py
"""
import json
import re
from collections import Counter

MAR, JUN, SEP25, OCT19 = "2026-03-31", "2026-06-30", "2026-09-25", "2026-10-19"
SRC_MAR = "TATT price schedule, 31 Mar 2026"
SRC_JUN = "TATT price schedule, 30 Jun 2026"
SRC_BM_SEP = "bmobile customer notice, as reported by Trinidad Express 9 Oct 2026"
SRC_DIG_OCT = "Digicel TT prepaid plans page (prices effective 19 Oct 2026)"

RECORDS = []


def P(price, eff, src, verified, notes=None):
    """One price point in a plan's history."""
    d = {"price": price, "eff": eff, "src": src, "verified": verified}
    if notes is not None:
        d["notes"] = notes
    return d


def steady(price):
    """Price seen in March and still the same in June."""
    return [P(price, MAR, SRC_MAR, JUN)]


def add(pid, ptype, provider, name, points, *, validity=None, down=None, up=None,
        data=None, mins=None, unl_mins=False, roam=None, rollover=None,
        conn=None, notes=""):
    for p in points:
        RECORDS.append({
            "id": pid,
            "plan_type": ptype,
            "provider": provider,
            "plan_name": name,
            "price_ttd": p["price"],
            "validity_days": validity,
            "download_speed_mbps": down,
            "upload_speed_mbps": up,
            "data_gb": data,
            "anywhere_minutes": mins,
            "unlimited_anywhere_minutes": unl_mins,
            "roaming_gb": roam,
            "rollover_data": rollover,
            "connection_type": conn,
            "notes": p.get("notes", notes),
            "effective_date": p["eff"],
            "last_verified": p["verified"],
            "source": p["src"],
            "status": "active",
        })


# ═════════════════════════════════════════════════════════════════════════
# HOME BROADBAND
# connection_type is only filled in where the TATT document (or its own
# verification link) supports it. None = not stated. Fill in the None ones
# after checking each provider's site.
# ═════════════════════════════════════════════════════════════════════════
BB = "home_broadband"
CONN = {
    "Amplia": None,                      # not stated by TATT - check amplia.co.tt
    "bmobile": "LTE (fixed wireless)",   # TATT: "Unlimited 4GLTE Wireless Data"
    "Digicel": "Fibre",                  # TATT: "Digicel Fibre Internet Packages"
    "Flow": None,                        # not stated by TATT
    "Green Dot": None,                   # not stated by TATT
    "Lisa Communications": "Wireless",   # TATT verification link: /lisawireless/
    "Novo Communications": None,         # not stated by TATT
    "RVR Networks": None,                # not stated by TATT
    "Starlink": "Satellite",
}

for n, dl, ul, pr in [("Smart 300", 300, 300, 300.00), ("Smart 400", 400, 300, 400.00), ("Smart 500", 500, 350, 500.00)]:
    add(f"amplia-{n.lower().replace(' ', '-')}", BB, "Amplia", n, steady(pr), down=dl, up=ul, conn=CONN["Amplia"])

for mbps, old, new in [(6, 167.63, 201.38), (10, 201.38, 223.88), (20, 223.88, 280.13)]:
    add(f"bmobile-lte-{mbps}mbps", BB, "bmobile", f"Unlimited 4G LTE {mbps} Mbps",
        [P(old, MAR, SRC_MAR, JUN), P(new, SEP25, SRC_BM_SEP, "2026-10-09")],
        down=mbps, conn=CONN["bmobile"], notes="Upload speed not stated. Unlimited data.")

for mbps, pr in [(350, 350.00), (500, 500.00)]:
    add(f"digicel-home-fibre-{mbps}", BB, "Digicel", f"Home Fibre {mbps} Mbps", steady(pr),
        down=mbps, up=mbps, conn=CONN["Digicel"])

add("flow-link-up", BB, "Flow", "Link Up", steady(299.00), down=300, up=50, conn=CONN["Flow"])
add("flow-link-up-plus", BB, "Flow", "Link Up Plus", steady(345.00), down=400, up=50, conn=CONN["Flow"],
    notes="The March TATT listing noted 10% off ($310.50 for 3 months) for sign-ups before 31 Mar 2026. The June listing shows $345 only.")
add("flow-link-up-plus-boost-it", BB, "Flow", "Link Up Plus - Boost It", steady(397.00), down=500, up=75, conn=CONN["Flow"])

gd_note = "Speed not stated by TATT (not on the provider's webpage)."
add("greendot-basic", BB, "Green Dot", "Basic", [P(196.88, MAR, SRC_MAR, MAR), P(219.38, JUN, SRC_JUN, JUN)], conn=CONN["Green Dot"], notes=gd_note)
add("greendot-essential", BB, "Green Dot", "Essential", [P(253.13, MAR, SRC_MAR, MAR), P(275.63, JUN, SRC_JUN, JUN)], conn=CONN["Green Dot"], notes=gd_note)
add("greendot-abundant", BB, "Green Dot", "Abundant", steady(336.38), conn=CONN["Green Dot"], notes=gd_note)

for n, dl, ul, pr, note in [
    ("2MB Residential Circuit", 2, 0.768, 336.38, "Upload speed is 768 Kbps."),
    ("3MB Residential Circuit", 3, 1, 448.88, ""),
    ("5MB Residential Circuit", 5, 1.5, 561.38, ""),
    ("7MB Residential Circuit", 7, 2, 673.88, ""),
]:
    add(f"lisa-{n[:3].lower()}-circuit", BB, "Lisa Communications", n, steady(pr), down=dl, up=ul, conn=CONN["Lisa Communications"], notes=note)

for n, dl, ul, pr in [("Starter", 100, 50, 255.00), ("Advance", 200, 100, 350.00), ("Xtreme", 300, 150, 500.00)]:
    add(f"novo-{n.lower()}", BB, "Novo Communications", n, steady(pr), down=dl, up=ul, conn=CONN["Novo Communications"])

for n, dl, ul, pr in [("Evolution", 200, 100, 200.00), ("Ultra", 400, 200, 500.00), ("Sport", 700, 350, 650.00)]:
    add(f"rvr-{n.lower()}", BB, "RVR Networks", n, steady(pr), down=dl, up=ul, conn=CONN["RVR Networks"])

sl_jun = ("TATT lists the speed as 'up to {x} Mbps upload', which looks like a typo for download - verify. "
          "Speeds are maximums, not guaranteed, and slower during congestion.")
add("starlink-residential-lite", BB, "Starlink", "Residential LITE", [
    P(260.00, MAR, SRC_MAR, MAR, notes="Satellite. TATT March listing: 80-200 Mbps download, 15-35 Mbps upload."),
    P(275.00, JUN, SRC_JUN, JUN, notes="Satellite. " + sl_jun.format(x=250)),
], conn=CONN["Starlink"])
add("starlink-residential", BB, "Starlink", "Residential", [
    P(365.00, MAR, SRC_MAR, MAR, notes="Satellite. Speed not stated in the March TATT listing."),
    P(390.00, JUN, SRC_JUN, JUN, notes="Satellite. " + sl_jun.format(x=400)),
], conn=CONN["Starlink"])

# ═════════════════════════════════════════════════════════════════════════
# MOBILE PREPAID
# ═════════════════════════════════════════════════════════════════════════
PRE = "mobile_prepaid"
MOB = "Mobile (4G LTE)"
no_roll = " Rollover isn't stated for this plan in the June TATT listing (March said it had rollover benefits)."

# bmobile
add("bmobile-prepaid-30day-max", PRE, "bmobile", "My 30 Day Max", steady(415.00), validity=30, data=150, mins=450, roam=3, conn=MOB,
    notes="Double data and double Anywhere minutes with auto-renewal. Free bmobile calls, free local SMS, free weekend data." + no_roll)
add("bmobile-prepaid-30day-plus", PRE, "bmobile", "My 30 Day+", steady(280.00), validity=30, data=30, mins=400, roam=1, conn=MOB,
    notes="Double data and double Anywhere minutes with auto-renewal. Free bmobile calls, free local SMS, free weekend data." + no_roll)
add("bmobile-prepaid-30day", PRE, "bmobile", "My 30 Day", steady(170.00), validity=30, data=2, mins=200, roam=0, conn=MOB,
    notes="Free bmobile calls, free local SMS.")
add("bmobile-prepaid-14day", PRE, "bmobile", "My 14 Day", steady(180.00), validity=14, data=45, mins=200, roam=0, conn=MOB,
    notes="Double data with auto-renewal. Free bmobile calls, free local SMS, free weekend data." + no_roll)
add("bmobile-prepaid-7day", PRE, "bmobile", "My 7 Day", steady(120.00), validity=7, data=25, mins=120, roam=0, conn=MOB,
    notes="Double data with auto-renewal. Free bmobile calls, free local SMS." + no_roll)
add("bmobile-prepaid-3day", PRE, "bmobile", "My 3 Day", steady(60.00), validity=3, data=35, mins=100, roam=0, conn=MOB,
    notes="Double data with auto-renewal. Free bmobile calls, free local SMS." + no_roll)
add("bmobile-prepaid-1day-plus", PRE, "bmobile", "My 1 Day+", steady(38.00), validity=1, data=50, mins=100, roam=0, conn=MOB,
    notes="Free bmobile calls, free local SMS.")
add("bmobile-prepaid-1day", PRE, "bmobile", "My 1 Day", steady(30.00), validity=1, data=25, mins=60, roam=0, conn=MOB,
    notes="Free bmobile calls, free local SMS.")
add("bmobile-prepaid-3month", PRE, "bmobile", "3-month Plan", steady(450.00), validity=90, data=2, mins=200, roam=0, conn=MOB,
    notes="TATT lists $450 for a 3-month plan with 2GB data and 200 Anywhere minutes each month. Treated here as $450 for the full 3 months (about $150/month) - confirm with bmobile. Unlimited bmobile calls, rollover Anywhere minutes.")
add("bmobile-prepaid-shared", PRE, "bmobile", "Shared Plan", [
    P(168.19, MAR, SRC_MAR, MAR, notes="Share data, minutes and texts with up to 5 friends or family. Unlimited bmobile calls and global texts. The March listing did not say how many members the price covered."),
    P(336.38, JUN, SRC_JUN, JUN, notes="Price is for the first two members; each additional member (up to 5 total) is $112.50. Unlimited bmobile calls and global texts."),
], validity=30, data=12, mins=150, roam=0, conn=MOB)

# Digicel (names from Digicel's own page; matched to the TATT rows by price and data)
dig = [
    # id, name, validity, data, mins, roam, rollover, extra notes, [price points after March]
    ("d-1day", "D' 1 Day", 1, 25, 60, 0, None, "Free Digicel minutes, free local SMS.", None),
    ("d-1day-plus", "D' 1 Day+", 1, 50, 100, 0, None, "Free Digicel minutes, free local SMS.", None),
    ("d-weekend", "D' Weekend (3 Day)", 3, 35, 100, 0, True, "Free Digicel minutes, free local SMS.", None),
    ("d-weekly-flex", "D' Weekly Flex", 7, 12, 100, 0, True, "Free Digicel minutes, free local SMS.", 125.00),
    ("d-weekly-classic", "D' Weekly Classic", 7, 30, 150, 0, True, "Free Digicel minutes, free local SMS.", 150.00),
    ("d-fortnight", "D' Fortnight", 14, 45, 200, 0, True, "Free Digicel minutes, free local SMS, free data weekends.", 208.00),
    ("d-lite", "D' Lite", 30, 2, 75, 0, False, "1000 Digicel minutes, free local SMS.", 185.00),
    ("d-freedom", "D' Freedom", 30, 30, 400, 1, True, "Free Digicel minutes, free local SMS, free data weekends. 1GB Digicel Caribbean roaming data.", 325.00),
    ("d-all-in", "D' All In", 30, 200, 500, 3, True, "Free Digicel minutes, free local SMS, free data weekends. 3GB Digicel Caribbean roaming data.", 500.00),
]
march_prices = {"d-1day": 30.00, "d-1day-plus": 40.00, "d-weekend": 67.00, "d-weekly-flex": 120.00,
                "d-weekly-classic": 145.00, "d-fortnight": 200.00, "d-lite": 180.00, "d-freedom": 315.00, "d-all-in": 490.00}
for key, name, val, data, mins, roam, roll, notes, new_price in dig:
    pts = [P(march_prices[key], MAR, SRC_MAR, JUN)]
    if new_price is not None:
        pts.append(P(new_price, OCT19, SRC_DIG_OCT, "2026-10-11"))
    add(f"digicel-prepaid-{key[2:]}", PRE, "Digicel", name, pts, validity=val, data=data, mins=mins, roam=roam,
        rollover=roll, conn=MOB, notes=notes)

# ═════════════════════════════════════════════════════════════════════════
# MOBILE POSTPAID (all monthly; no price changes between March and June)
# ═════════════════════════════════════════════════════════════════════════
POST = "mobile_postpaid"
add("bmobile-postpaid-295", POST, "bmobile", "My Postpaid $295", steady(295.00), validity=30, data=40, mins=400, roam=1, rollover=True, conn=MOB,
    notes="Free bmobile calls, rollover data and Anywhere minutes, free local SMS, free weekend data.")
add("bmobile-postpaid-450", POST, "bmobile", "My Postpaid $450", steady(450.00), validity=30, data=450, unl_mins=True, roam=3, rollover=True, conn=MOB,
    notes="Free bmobile calls, free Anywhere minutes (unlimited), rollover data, free local SMS.")
add("bmobile-postpaid-625", POST, "bmobile", "My Postpaid $625", steady(625.00), validity=30, data=800, unl_mins=True, roam=10, rollover=True, conn=MOB,
    notes="Free bmobile calls, free Anywhere minutes (unlimited), rollover data, free local SMS.")
add("bmobile-postpaid-b-golden", POST, "bmobile", "b-Golden", steady(219.00), validity=30, data=3, mins=300, roam=0, conn=MOB,
    notes="2000 bmobile minutes plus 300 Anywhere minutes, free local SMS.")
add("bmobile-postpaid-premium-shared", POST, "bmobile", "Premium Shared Plan", steady(730.13), validity=30, data=80, roam=0, conn=MOB,
    notes="Owner plus 2 members included; up to 5 subscribers total, $168.75 for each additional member. Unlimited bmobile minutes, 1000 local minutes, unlimited global texts.")
add("digicel-postpaid-all-inclusive", POST, "Digicel", "My All Inclusive", steady(650.00), validity=30, data=800, unl_mins=True, roam=10, conn=MOB,
    notes="Free Anywhere minutes (unlimited), free Digicel-to-Digicel calls, free local SMS. Roaming is Digicel Caribbean.")
add("digicel-postpaid-value-max", POST, "Digicel", "My Value Max", steady(500.00), validity=30, data=450, unl_mins=True, roam=5, conn=MOB,
    notes="Free Anywhere minutes (unlimited), free Digicel-to-Digicel calls, free local SMS. Roaming is Digicel Caribbean.")
add("digicel-postpaid-choice", POST, "Digicel", "My Choice", steady(300.00), validity=30, data=40, mins=400, roam=1, conn=MOB,
    notes="Free Digicel-to-Digicel calls, free local SMS. Roaming is Digicel Caribbean.")
add("digicel-postpaid-connect", POST, "Digicel", "My Connect (60+ only)", steady(219.99), validity=30, data=3, mins=300, roam=0, conn=MOB,
    notes="Age-restricted: 60+ years only. Free Digicel minutes, free local SMS.")
add("digicel-postpaid-family", POST, "Digicel", "Family Plan", steady(500.00), validity=30, data=200, mins=1000, roam=0, conn=MOB,
    notes="Starts at $500 for two persons. Free Digicel minutes plus 1000 local Anywhere minutes.")


# ═════════════════════════════════════════════════════════════════════════
# CHECKS + SAVE
# ═════════════════════════════════════════════════════════════════════════
def validate(records):
    seen = set()
    for r in records:
        key = (r["id"], r["effective_date"])
        assert key not in seen, f"duplicate id+date: {key}"
        seen.add(key)
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["effective_date"]), r
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["last_verified"]), r
        assert r["price_ttd"] > 0, r
    # An old price can't have been confirmed after its replacement took over.
    by_id = {}
    for r in records:
        by_id.setdefault(r["id"], []).append(r)
    for pid, rows in by_id.items():
        rows.sort(key=lambda r: r["effective_date"])
        for older, newer in zip(rows, rows[1:]):
            assert older["last_verified"] < newer["effective_date"], f"{pid}: old price verified after replacement"
    return True


if __name__ == "__main__":
    validate(RECORDS)
    RECORDS.sort(key=lambda r: (r["plan_type"], r["provider"], r["id"], r["effective_date"]))
    with open("tt_all_plans.json", "w", encoding="utf-8") as f:
        json.dump(RECORDS, f, indent=2, ensure_ascii=False)
    plans = {r["id"] for r in RECORDS}
    by_type = Counter(r["plan_type"] for r in RECORDS if r["id"] in plans)
    print(f"Saved tt_all_plans.json: {len(RECORDS)} price records for {len(plans)} plans")
    print({t: len({r['id'] for r in RECORDS if r['plan_type'] == t}) for t in by_type})
