"""CYP450 pathway roles curated from FDA labeling + Flockhart-style public data.

Used for INFERENCE of hidden interactions (plan3): if A inhibits/induces
an enzyme that metabolizes B, we flag the pair even when no direct
clinical study exists. trust=0.5 (plan3 tier: enzyme inference).

Enzymes: 1A2, 2C9, 2C19, 2D6, 3A4, 2E1, p_gp (P-glycoprotein).
Only well-documented, high-confidence roles are included. Figshare 2E1
records are substrate evidence only; they do not imply inhibition or induction.
"""
ENZYMES = ("1A2", "2C9", "2C19", "2D6", "3A4", "2E1", "p_gp")

# class_id -> {"substrates": [...], "inhibitors": [...], "inducers": [...]}
CYP_CLASS_ROLES = {
    "antifungicos":        {"substrates": ["3A4"], "inhibitors": ["3A4", "2C9", "2C19"]},
    "macrolidos":          {"substrates": ["3A4"], "inhibitors": ["3A4"]},
    "isrs":                {"substrates": ["2D6"], "inhibitors": ["2D6"]},
    "isrsn":               {"substrates": ["2D6"]},
    "triciclicos":         {"substrates": ["2D6"]},
    "antipsicoticos":      {"substrates": ["2D6", "3A4"]},
    "benzodiacepinas":     {"substrates": ["3A4"]},
    "hipnoticos":          {"substrates": ["3A4"]},
    "estatinas":           {"substrates": ["3A4"]},
    "anticoagulantes":     {"substrates": ["2C9", "2C19", "3A4"]},
    "antiplaquetarios":    {"substrates": ["2C19"]},
    "antihipertensivos":   {"substrates": ["3A4", "2C9"]},
    "antiarritmicos":      {"substrates": ["3A4"], "inhibitors": ["2C9", "2D6", "3A4"]},
    "digoxina":            {"substrates": ["p_gp"]},
    "teofilina":           {"substrates": ["1A2"]},
    "anticonvulsivantes":  {"substrates": ["3A4", "2C9", "2C19"],
                            "inducers": ["3A4", "2C9", "2C19", "1A2"]},
    "anticonceptivos":     {"substrates": ["3A4"]},
    "inmunosupresores":    {"substrates": ["3A4", "p_gp"]},
    "opioides":            {"substrates": ["2D6", "3A4"]},
    "antidiabeticos":      {"substrates": ["2C9"]},
    "betabloqueantes":     {"substrates": ["2D6"]},
    "omeprazol":           {"substrates": ["2C19", "3A4"], "inhibitors": ["2C19"]},
    "antirretrovirales":   {"substrates": ["3A4"], "inhibitors": ["3A4"], "inducers": ["3A4"]},
    "vasodilatadores":     {"substrates": ["3A4"]},
    "antiemeticos":        {"substrates": ["3A4"]},
    "antigotosos":         {"substrates": ["3A4", "p_gp"]},
    "corticosteroides":    {"substrates": ["3A4"]},
    "antibioticos":        {"inhibitors": ["1A2"]},
    "aines":               {"substrates": ["2C9"]},
    "quimioterapia":       {"substrates": ["3A4"]},
    "alfa_bloqueantes":    {"substrates": ["3A4", "2D6"]},
    "antimigrañosos":      {"substrates": ["3A4"]},
    "antihistaminicos":    {"substrates": ["p_gp"]},
    "melatonina_rx":       {"substrates": ["1A2"]},
}

# herb_id -> same shape
CYP_HERB_ROLES = {
    "hypericum":     {"inducers": ["3A4", "2C9", "2C19", "p_gp"]},   # St. John's wort (FDA-labeled inducer)
    "curcuma":       {"inhibitors": ["3A4"]},                        # turmeric/curcumin
    "ajo":           {"inhibitors": ["2C9"]},                        # garlic
    "ginkgo":        {"inhibitors": ["2C19"]},                       # ginkgo biloba
    "ginseng":       {"inhibitors": ["2D6"]},                        # Panax ginseng
    "equinacea":     {"inhibitors": ["1A2"]},                        # echinacea
    "kava":          {"inhibitors": ["2D6", "2C9", "3A4"]},          # kava
    "berberina":     {"inhibitors": ["3A4", "2D6"]},                 # berberine/goldenseal
    "cardo_mariano": {"inhibitors": ["3A4"]},                        # milk thistle (silymarin)
    "schisandra":    {"inhibitors": ["3A4", "2C9"]},                 # schisandra
    "guarana":       {"substrates": ["1A2"]},                        # caffeine
}
