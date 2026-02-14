"""
Glaze Designer — Describe a glaze, get a recipe.
=================================================
Natural-language interface on top of glaze_engine.py.
Cone 6 oxidation focus.
"""

import re
from typing import Dict, List, Optional, Tuple
from glaze_engine import (
    load_materials_db,
    recipe_to_umf,
    umf_to_recipe,
    check_limits,
    thermal_expansion,
    food_safety_check,
    format_umf,
    format_limit_check,
    CONE6_LIMITS,
)

# ── Surface type targets ──────────────────────────────────────────────────

SURFACE_TARGETS = {
    "glossy": {
        "Al2O3": (0.30, 0.45),
        "SiO2":  (3.0, 4.5),
    },
    "satin": {
        "Al2O3": (0.35, 0.50),
        "SiO2":  (2.8, 3.8),
    },
    "matte": {
        "Al2O3": (0.25, 0.40),
        "SiO2":  (2.0, 3.2),
    },
    "crystalline": {
        "Al2O3": (0.02, 0.10),
        "SiO2":  (2.5, 4.0),
        "ZnO":   (0.30, 0.60),
    },
}

# ── Flux system presets ───────────────────────────────────────────────────

FLUX_PRESETS = {
    "default": {
        "CaO":  (0.30, 0.55),
        "MgO":  (0.00, 0.10),
        "ZnO":  (0.00, 0.10),
        "Na2O": (0.05, 0.20),
        "K2O":  (0.03, 0.15),
    },
    "buttery_matte": {
        "CaO":  (0.10, 0.30),
        "MgO":  (0.20, 0.35),
        "ZnO":  (0.00, 0.05),
        "Na2O": (0.05, 0.15),
        "K2O":  (0.03, 0.12),
    },
    "silky_matte": {
        "CaO":  (0.45, 0.65),
        "MgO":  (0.00, 0.10),
        "ZnO":  (0.00, 0.05),
        "Na2O": (0.05, 0.15),
        "K2O":  (0.03, 0.12),
    },
    "zinc_matte": {
        "CaO":  (0.10, 0.30),
        "MgO":  (0.00, 0.10),
        "ZnO":  (0.25, 0.50),
        "Na2O": (0.05, 0.15),
        "K2O":  (0.03, 0.12),
    },
    "boron_gloss": {
        "CaO":  (0.15, 0.40),
        "MgO":  (0.00, 0.10),
        "ZnO":  (0.00, 0.10),
        "Na2O": (0.05, 0.20),
        "K2O":  (0.03, 0.15),
        "B2O3": (0.15, 0.50),
    },
}

# ── Color systems (additions as wt% of base recipe batch) ────────────────

COLOR_SYSTEMS = {
    "cobalt_blue": {
        "additions": {"Cobalt Carbonate": 1.0},
        "notes": "Classic cobalt blue, 0.5-2% cobalt carbonate",
    },
    "copper_green": {
        "additions": {"Copper Carbonate": 2.0},
        "notes": "Copper green, 1-3% copper carbonate",
    },
    "chrome_green": {
        "additions": {"Chrome Oxide": 0.3},
        "notes": "Chrome green, 0.2-0.5% chrome oxide",
    },
    "iron_amber": {
        "additions": {"Red Iron Oxide": 1.5},
        "notes": "Light iron amber, 1-2%",
    },
    "iron_brown": {
        "additions": {"Red Iron Oxide": 4.0},
        "notes": "Iron brown, 3-5%",
    },
    "tenmoku": {
        "additions": {"Red Iron Oxide": 10.0},
        "notes": "Tenmoku, 8-12% iron oxide",
    },
    "saturated_iron": {
        "additions": {"Red Iron Oxide": 14.0},
        "notes": "Saturated iron red, >12% iron",
    },
    "tin_white": {
        "additions": {"Tin Oxide": 4.0},
        "notes": "Tin white opacifier, 3-5%",
    },
    "zircopax_white": {
        "additions": {"Zircopax": 10.0},
        "notes": "Zircopax opacifier, 8-12%",
    },
    "titanium_white": {
        "additions": {"Titanium Dioxide": 3.0},
        "notes": "Titanium white/cream, 2-4%",
    },
    "black": {
        "additions": {"Cobalt Carbonate": 1.0, "Red Iron Oxide": 4.0, "Manganese Dioxide": 3.0},
        "notes": "Black: cobalt + iron + manganese combo",
    },
    "celadon": {
        "additions": {"Red Iron Oxide": 1.0},
        "notes": "Light iron 0.5-1.5% — note: true celadon requires reduction; this approximates in oxidation",
    },
    "rutile_variegation": {
        "additions": {"Rutile": 4.0},
        "notes": "Rutile for variegation/breaking, 3-5%",
    },
}

# ── Material selection for different flux systems ─────────────────────────

BASE_MATERIALS = [
    "Custer Feldspar", "Nepheline Syenite", "EPK Kaolin",
    "Silica", "Whiting", "Bentonite",
]

FLUX_MATERIALS = {
    "default":       BASE_MATERIALS,
    "buttery_matte": BASE_MATERIALS + ["Dolomite", "Talc"],
    "silky_matte":   BASE_MATERIALS + ["Wollastonite"],
    "zinc_matte":    BASE_MATERIALS + ["Zinc Oxide"],
    "boron_gloss":   BASE_MATERIALS + ["Ferro Frit 3134"],
    "crystalline":   ["Ferro Frit 3110", "Silica", "Zinc Oxide", "EPK Kaolin"],
}

# ── Clay body CTE estimates (×10⁻⁷/°C) ──────────────────────────────────

CLAY_BODIES = {
    "porcelain":  55.0,
    "stoneware":  60.0,
    "nz_6":       55.0,
    "glacier":    55.0,
    "oregon_brown": 62.0,
}


# ══════════════════════════════════════════════════════════════════════════
# Description parser
# ══════════════════════════════════════════════════════════════════════════

def parse_description(desc: str) -> dict:
    """Parse a natural-language glaze description into structured targets."""
    d = desc.lower().strip()
    result = {
        "surface": "glossy",
        "flux_system": "default",
        "colors": [],
        "effects": [],
        "food_safe_requested": False,
        "clay_body": None,
        "notes": [],
    }

    # Surface
    if "crystalline" in d:
        result["surface"] = "crystalline"
    elif "matte" in d:
        result["surface"] = "matte"
    elif "satin" in d:
        result["surface"] = "satin"
    else:
        result["surface"] = "glossy"

    # Flux system
    if "buttery" in d:
        result["flux_system"] = "buttery_matte"
        result["surface"] = "matte"
    elif "silky" in d and "matte" in d:
        result["flux_system"] = "silky_matte"
    elif "zinc" in d and "matte" in d:
        result["flux_system"] = "zinc_matte"
        result["notes"].append("⚠️  Zinc matte glazes may not be food-safe — test with leach test")
    elif "boron" in d:
        result["flux_system"] = "boron_gloss"
    elif "crystalline" in d:
        result["flux_system"] = "crystalline"

    # Colors
    if "tenmoku" in d or "temoku" in d:
        result["colors"].append("tenmoku")
    elif "celadon" in d:
        result["colors"].append("celadon")
        result["notes"].append("True celadon requires reduction firing; this is an oxidation approximation")
    elif "black" in d:
        result["colors"].append("black")
    elif any(w in d for w in ["blue-green", "blue green", "teal"]):
        result["colors"].extend(["cobalt_blue", "copper_green"])
    elif "blue" in d and "rutile" in d:
        result["colors"].append("cobalt_blue")
        result["effects"].append("rutile_variegation")
        result["notes"].append("Rutile blue works best on a boron/high-alumina base")
    elif "blue" in d:
        result["colors"].append("cobalt_blue")
    elif "green" in d and "chrome" in d:
        result["colors"].append("chrome_green")
    elif "green" in d:
        result["colors"].append("copper_green")
    elif "red" in d or "orange" in d:
        result["notes"].append("True reds/oranges are impossible in cone 6 oxidation without inclusion stains. Using saturated iron red as closest alternative.")
        result["colors"].append("saturated_iron")
    elif "amber" in d:
        result["colors"].append("iron_amber")
    elif "brown" in d:
        result["colors"].append("iron_brown")
    elif "iron" in d and not any(c in d for c in ["blue", "green", "black"]):
        result["colors"].append("iron_brown")

    # White/cream
    if "white" in d:
        result["colors"].append("zircopax_white")
    elif "cream" in d:
        result["colors"].append("titanium_white")

    # Effects
    if any(w in d for w in ["variegat", "breaking", "rutile"]) and "rutile_variegation" not in result["effects"]:
        result["effects"].append("rutile_variegation")

    # Clear/transparent — no colorants
    if "clear" in d or "transparent" in d:
        result["colors"] = []
        result["effects"] = []

    # Food safety
    if "food safe" in d or "food-safe" in d or "foodsafe" in d:
        result["food_safe_requested"] = True

    # Clay body
    if "porcelain" in d:
        result["clay_body"] = "porcelain"
    elif "stoneware" in d:
        result["clay_body"] = "stoneware"

    return result


# ══════════════════════════════════════════════════════════════════════════
# Core designer function
# ══════════════════════════════════════════════════════════════════════════

def design_glaze(description: str, clay_body: Optional[str] = None) -> dict:
    """
    Design a glaze from a natural-language description.

    Returns dict with: recipe, umf, limits, expansion, food_safety, 
                       colorant_additions, explanation, notes
    """
    db = load_materials_db()
    parsed = parse_description(description)
    if clay_body:
        parsed["clay_body"] = clay_body

    explanation = []
    explanation.append(f"Parsed description: surface={parsed['surface']}, "
                       f"flux={parsed['flux_system']}, colors={parsed['colors']}, "
                       f"effects={parsed['effects']}")

    # Build target UMF from surface + flux system
    surface = SURFACE_TARGETS.get(parsed["surface"], SURFACE_TARGETS["glossy"])
    flux = FLUX_PRESETS.get(parsed["flux_system"], FLUX_PRESETS["default"])

    # Use midpoints of ranges as target
    target_umf = {}
    for oxide, (lo, hi) in flux.items():
        target_umf[oxide] = (lo + hi) / 2.0
    for oxide, (lo, hi) in surface.items():
        target_umf[oxide] = (lo + hi) / 2.0

    # Normalize fluxes to sum to 1.0
    from glaze_engine import FLUX_OXIDES
    flux_sum = sum(target_umf.get(f, 0) for f in FLUX_OXIDES)
    if flux_sum > 0:
        for f in FLUX_OXIDES:
            if f in target_umf:
                target_umf[f] /= flux_sum

    explanation.append(f"Target UMF midpoints (flux-normalized): "
                       + ", ".join(f"{k}={v:.3f}" for k, v in sorted(target_umf.items())))

    # Select materials
    flux_key = parsed["flux_system"]
    if parsed["surface"] == "crystalline":
        flux_key = "crystalline"
    materials = FLUX_MATERIALS.get(flux_key, BASE_MATERIALS)

    # Solve
    recipe = umf_to_recipe(target_umf, materials, db)
    if recipe is None:
        # Try with broader material set
        broad = list(set(BASE_MATERIALS + materials + ["Ferro Frit 3134", "Dolomite", "Talc", "Wollastonite", "Zinc Oxide"]))
        recipe = umf_to_recipe(target_umf, broad, db)
        if recipe is None:
            return {
                "success": False,
                "error": "Could not solve for a recipe with available materials. Try adjusting the description.",
                "explanation": explanation,
                "notes": parsed["notes"],
            }
        explanation.append("Used expanded material set to find solution")

    # Compute UMF of result
    umf = recipe_to_umf(recipe, db)
    limits = check_limits(umf)
    cte = thermal_expansion(umf)

    # Colorant/effect additions
    colorant_additions = {}
    color_notes = []
    batch_total = sum(recipe.values())

    for color_key in parsed["colors"] + parsed["effects"]:
        cs = COLOR_SYSTEMS.get(color_key)
        if cs:
            for mat, pct in cs["additions"].items():
                amt = round(batch_total * pct / 100.0, 2)
                colorant_additions[mat] = colorant_additions.get(mat, 0) + amt
            color_notes.append(cs["notes"])

    # Food safety
    full_recipe = dict(recipe)
    full_recipe.update(colorant_additions)
    food_safety = food_safety_check(full_recipe, umf)

    # Expansion fit
    body_cte = None
    crazing_note = None
    if parsed["clay_body"] and parsed["clay_body"] in CLAY_BODIES:
        body_cte = CLAY_BODIES[parsed["clay_body"]]
        diff = cte - body_cte
        if diff > 5:
            crazing_note = f"⚠️  Glaze CTE ({cte:.1f}) > body CTE ({body_cte:.1f}) — risk of CRAZING"
        elif diff < -10:
            crazing_note = f"⚠️  Glaze CTE ({cte:.1f}) << body CTE ({body_cte:.1f}) — risk of SHIVERING"
        else:
            crazing_note = f"✅ Glaze CTE ({cte:.1f}) ≈ body CTE ({body_cte:.1f}) — good fit"

    return {
        "success": True,
        "description": description,
        "parsed": parsed,
        "recipe": recipe,
        "colorant_additions": colorant_additions,
        "umf": umf,
        "limits": limits,
        "cte": cte,
        "body_cte": body_cte,
        "crazing_note": crazing_note,
        "food_safety": food_safety,
        "color_notes": color_notes,
        "explanation": explanation,
        "notes": parsed["notes"],
    }


# ══════════════════════════════════════════════════════════════════════════
# Variation suggester
# ══════════════════════════════════════════════════════════════════════════

VARIATION_ADJUSTMENTS = {
    "more matte": {"Al2O3": -0.03, "SiO2": -0.3, "MgO": 0.05},
    "more glossy": {"Al2O3": 0.03, "SiO2": 0.4, "MgO": -0.03},
    "more blue": {},  # handled via colorant
    "reduce crazing": {"Na2O": -0.03, "K2O": -0.02, "SiO2": 0.3},
    "more fluid": {"SiO2": -0.3, "B2O3": 0.05, "CaO": 0.03},
    "more durable": {"Al2O3": 0.03, "SiO2": 0.2},
    "less runny": {"Al2O3": 0.04, "SiO2": 0.3},
}


def suggest_variations(base_result: dict, direction: str) -> dict:
    """
    Adjust a base recipe in a given direction and re-solve.

    Parameters
    ----------
    base_result : dict
        Output from design_glaze().
    direction : str
        E.g. "more matte", "reduce crazing", "more fluid".

    Returns
    -------
    dict
        New design_glaze-style result.
    """
    if not base_result.get("success"):
        return {"success": False, "error": "Cannot vary a failed recipe"}

    db = load_materials_db()
    base_umf = base_result["umf"]
    direction_lower = direction.lower().strip()

    adjustments = VARIATION_ADJUSTMENTS.get(direction_lower, {})

    # Build new target
    target = dict(base_umf)
    # Remove colorant oxides from target (they come from additions)
    from glaze_engine import COLORANT_OXIDES
    for ox in COLORANT_OXIDES:
        target.pop(ox, None)

    for oxide, delta in adjustments.items():
        target[oxide] = max(0, target.get(oxide, 0) + delta)

    # Handle colorant-based directions
    new_color_additions = dict(base_result.get("colorant_additions", {}))
    if "more blue" in direction_lower:
        new_color_additions["Cobalt Carbonate"] = new_color_additions.get("Cobalt Carbonate", 0) + 0.5

    # Re-normalize fluxes
    from glaze_engine import FLUX_OXIDES
    flux_sum = sum(target.get(f, 0) for f in FLUX_OXIDES)
    if flux_sum > 0:
        for f in FLUX_OXIDES:
            if f in target:
                target[f] /= flux_sum

    # Determine materials from base
    parsed = base_result.get("parsed", {})
    flux_key = parsed.get("flux_system", "default")
    if parsed.get("surface") == "crystalline":
        flux_key = "crystalline"
    materials = FLUX_MATERIALS.get(flux_key, BASE_MATERIALS)

    recipe = umf_to_recipe(target, materials, db)
    if recipe is None:
        broad = list(set(BASE_MATERIALS + materials + ["Ferro Frit 3134", "Dolomite", "Talc", "Wollastonite", "Zinc Oxide"]))
        recipe = umf_to_recipe(target, broad, db)
        if recipe is None:
            return {"success": False, "error": f"Could not solve variation '{direction}'"}

    umf = recipe_to_umf(recipe, db)
    limits = check_limits(umf)
    cte = thermal_expansion(umf)

    full_recipe = dict(recipe)
    full_recipe.update(new_color_additions)
    food_safety = food_safety_check(full_recipe, umf)

    body_cte = base_result.get("body_cte")
    crazing_note = None
    if body_cte:
        diff = cte - body_cte
        if diff > 5:
            crazing_note = f"⚠️  Glaze CTE ({cte:.1f}) > body CTE ({body_cte:.1f}) — CRAZING risk"
        elif diff < -10:
            crazing_note = f"⚠️  Glaze CTE ({cte:.1f}) << body CTE ({body_cte:.1f}) — SHIVERING risk"
        else:
            crazing_note = f"✅ Glaze CTE ({cte:.1f}) ≈ body CTE ({body_cte:.1f}) — good fit"

    return {
        "success": True,
        "description": f"Variation of '{base_result['description']}' → {direction}",
        "recipe": recipe,
        "colorant_additions": new_color_additions,
        "umf": umf,
        "limits": limits,
        "cte": cte,
        "body_cte": body_cte,
        "crazing_note": crazing_note,
        "food_safety": food_safety,
        "explanation": [f"Adjusted from base: {adjustments}", f"Direction: {direction}"],
        "notes": [],
    }


# ══════════════════════════════════════════════════════════════════════════
# Pretty-print
# ══════════════════════════════════════════════════════════════════════════

def format_result(result: dict) -> str:
    """Format a design result for display."""
    lines = []
    lines.append("=" * 65)
    lines.append(f"  GLAZE DESIGN: {result.get('description', '?')}")
    lines.append("=" * 65)

    if not result.get("success"):
        lines.append(f"\n  ❌ {result.get('error', 'Unknown error')}")
        for n in result.get("notes", []):
            lines.append(f"  📝 {n}")
        for e in result.get("explanation", []):
            lines.append(f"  → {e}")
        return "\n".join(lines)

    # Recipe
    lines.append("\n📋 BASE RECIPE (100g batch):")
    lines.append(f"  {'Material':<25s} {'Grams':>8s}  {'%':>6s}")
    lines.append("  " + "-" * 42)
    total = sum(result["recipe"].values())
    for mat, amt in sorted(result["recipe"].items(), key=lambda x: -x[1]):
        lines.append(f"  {mat:<25s} {amt:8.2f}  {amt/total*100:6.1f}%")
    lines.append(f"  {'TOTAL':<25s} {total:8.2f}")

    if result.get("colorant_additions"):
        lines.append("\n🎨 COLORANT ADDITIONS (on top of base):")
        for mat, amt in sorted(result["colorant_additions"].items(), key=lambda x: -x[1]):
            pct = amt / total * 100
            lines.append(f"  + {mat:<23s} {amt:8.2f}  ({pct:.1f}%)")

    # UMF
    lines.append("\n🔬 UNITY MOLECULAR FORMULA:")
    lines.append(format_umf(result["umf"]))

    # Limits
    lines.append("\n📏 CONE 6 LIMIT CHECK:")
    lines.append(format_limit_check(result["limits"]))

    # Thermal expansion
    lines.append(f"\n🌡️  THERMAL EXPANSION: {result['cte']:.1f} × 10⁻⁷/°C")
    if result.get("crazing_note"):
        lines.append(f"  {result['crazing_note']}")

    # Food safety
    lines.append("\n🍽️  FOOD SAFETY:")
    for w in result.get("food_safety", []):
        lines.append(f"  {w}")

    # Color notes
    if result.get("color_notes"):
        lines.append("\n🎨 COLOR NOTES:")
        for n in result["color_notes"]:
            lines.append(f"  • {n}")

    # Notes
    if result.get("notes"):
        lines.append("\n📝 NOTES:")
        for n in result["notes"]:
            lines.append(f"  • {n}")

    # Explanation
    if result.get("explanation"):
        lines.append("\n🔧 DESIGN CHOICES:")
        for e in result["explanation"]:
            lines.append(f"  → {e}")

    lines.append("")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        desc = " ".join(sys.argv[1:])
        result = design_glaze(desc)
        print(format_result(result))
    else:
        # Run test descriptions
        tests = [
            "glossy transparent clear for porcelain",
            "satin blue-green with some variegation",
            "buttery matte white, food safe",
            "tenmoku brown, glossy",
        ]
        for desc in tests:
            result = design_glaze(desc)
            print(format_result(result))
            print()

        # Demo variation
        print("\n" + "=" * 65)
        print("  VARIATION DEMO: making 'glossy clear' more matte")
        print("=" * 65)
        base = design_glaze("glossy transparent clear for porcelain")
        var = suggest_variations(base, "more matte")
        print(format_result(var))
