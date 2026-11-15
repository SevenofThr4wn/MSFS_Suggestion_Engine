import re

def is_military_stand_gate(name, terminal="", g_type="", is_military=False):
    if is_military:
        return True

    name_l = str(name or "").lower().strip()
    term_l = str(terminal or "").lower().strip()
    type_l = str(g_type or "").lower().strip()

    mil_phrases = (
            "air base", "base aerienne", "base aérienne", "military apron", "mil apron",
            "mil ramp", "military ramp", "nato", "otan", "fighter", "squadron", "escadron", "cotam",
        )

    if "military" in name_l or "military" in term_l or "military" in type_l or "mil_" in type_l:
        return True

    for text in (name_l, term_l):
        if any(p in text for p in mil_phrases):
            return True

        words = [w for w in re.split(r"[\s\-_/(),]+", text) if w]

        if "mil" in words or "mod" in words or "faf" in words or "usaf" in words or "raf" in words:
            return True

        for w in words:
            if w.startswith("mil") and len(w) > 3 and w[3].isdigit():
                return True
    return False




    

    