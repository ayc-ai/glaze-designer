"""
Ceramic Glaze Designer — Web Application
"""
import sys, os, json

# Add parent directory so we can import glaze_engine and glaze_designer
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, request, jsonify, send_from_directory
import glaze_engine
import glaze_designer

app = Flask(__name__, static_folder="static")

# Load materials DB once
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "materials_db.json")
with open(DB_PATH) as f:
    _raw_db = json.load(f)
MATERIALS_DB = _raw_db["materials"]

CLAY_BODY_OPTIONS = [
    {"id": "nz_6", "name": "NZ 6 Porcelain", "cone": "5-6", "cte": 55.0, "color": "White"},
    {"id": "glacier", "name": "Glacier Porcelain", "cone": "5-6", "cte": 55.0, "color": "White"},
    {"id": "oregon_brown", "name": "Oregon Brown Stoneware", "cone": 6, "cte": 62.0, "color": "Dark Brown"},
]

CLAY_BODY_MAP = {
    "nz_6": "nz_6",
    "glacier": "glacier",
    "oregon_brown": "oregon_brown",
    "porcelain": "porcelain",
    "stoneware": "stoneware",
}

# Reference glazes parsed from designed_glazes.md
REFERENCE_GLAZES = [
    {
        "name": "Honey Shino",
        "description": "Textured/crazed cream-to-yellow shino, satin to semi-gloss",
        "cone": 6,
        "recipe": {
            "Nepheline Syenite": 62.0, "EPK Kaolin": 8.0, "Strontium Carbonate": 8.0,
            "Dolomite": 7.0, "Ball Clay": 5.0, "Silica": 5.0, "Whiting": 5.0
        },
        "additions": {"Red Iron Oxide": 1.5, "Bentonite": 2.0},
        "notes": "Apply thick for more texture. Na2O and Al2O3 slightly over limits — intentional for shino character."
    },
    {
        "name": "Copper Dust",
        "description": "Crystalline tea dust with blue-green color shift, glossy with crystals",
        "cone": 6,
        "recipe": {
            "Nepheline Syenite": 38.0, "Silica": 22.0, "Whiting": 15.0,
            "Ferro Frit 3134": 10.0, "Dolomite": 5.0, "Talc": 5.0, "EPK Kaolin": 5.0
        },
        "additions": {"Red Iron Oxide": 6.0, "Rutile": 4.0, "Copper Carbonate": 2.5, "Cobalt Carbonate": 0.3, "Bentonite": 2.0},
        "notes": "Slow cool for more crystal development. Hold 1050°C for 30-60 min."
    },
    {
        "name": "Oribe Seafoam Base",
        "description": "Consistent copper-green Oribe, glossy",
        "cone": 6,
        "recipe": {
            "Ferro Frit 3134": 35.0, "Silica": 25.0, "EPK Kaolin": 15.0,
            "Whiting": 10.0, "Nepheline Syenite": 10.0, "Wollastonite": 5.0
        },
        "additions": {"Copper Carbonate": 4.0, "Bentonite": 2.0, "Tin Oxide": 1.0},
        "notes": "Use as base layer in Oribe layered system."
    },
    {
        "name": "Eggshell (CAC)",
        "description": "High zinc matte with rutile variegation",
        "cone": 6,
        "recipe": {
            "Custer Feldspar": 43.0, "Ball Clay": 1.5, "Whiting": 5.6,
            "Strontium Carbonate": 6.6, "Zinc Oxide": 19.5, "Silica": 16.0, "Rutile": 6.5
        },
        "additions": {},
        "notes": "High zinc matte. Rutile for variegation/texture."
    },
    {
        "name": "Floating Blue",
        "description": "Classic floating blue with rutile and cobalt",
        "cone": 6,
        "recipe": {
            "Nepheline Syenite": 44.6, "Gerstley Borate": 27.0, "Silica": 20.3, "EPK Kaolin": 22.3
        },
        "additions": {"Red Iron Oxide": 2.0, "Cobalt Carbonate": 1.5, "Rutile": 3.0},
        "notes": "Classic floating blue. Can sub cobalt oxide at ~71% of carbonate amount."
    },
]


def analyze_recipe(recipe_dict):
    """Common analysis logic for a recipe dict {material: percent}."""
    # Validate materials
    missing = [m for m in recipe_dict if m not in MATERIALS_DB]
    if missing:
        return {"success": False, "error": f"Unknown materials: {', '.join(missing)}. Check spelling."}

    try:
        umf = glaze_engine.recipe_to_umf(recipe_dict, MATERIALS_DB)
        limits = glaze_engine.check_limits(umf)
        cte = glaze_engine.thermal_expansion(umf)
        food_safety = glaze_engine.food_safety_check(recipe_dict, umf)

        total = sum(recipe_dict.values())
        recipe_table = []
        for mat, amt in sorted(recipe_dict.items(), key=lambda x: -x[1]):
            recipe_table.append({"material": mat, "percent": round(amt / total * 100, 1) if total else 0, "grams": round(amt, 2)})

        return {
            "success": True,
            "recipe": recipe_dict,
            "recipe_table": recipe_table,
            "umf": {k: round(v, 4) for k, v in umf.items()},
            "limits": limits,
            "cte": cte,
            "food_safety": food_safety,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/static/<path:path>")
def static_files(path):
    return send_from_directory("static", path)


@app.route("/api/materials")
def get_materials():
    return jsonify(sorted(MATERIALS_DB.keys()))


@app.route("/api/clay-bodies")
def get_clay_bodies():
    return jsonify(CLAY_BODY_OPTIONS)


def load_all_references():
    """Load all recipe sources into a unified library."""
    all_refs = []
    
    # 1. Designed/personal glazes
    for r in REFERENCE_GLAZES:
        all_refs.append({
            "name": r["name"],
            "source": "designed" if r["name"] in ["Honey Shino","Copper Dust","Oribe Seafoam Base"] else "personal",
            "cone": str(r.get("cone", "6")),
            "surface": r.get("description", "").split(",")[0] if "," in r.get("description","") else "",
            "description": r.get("description", ""),
            "recipe": r["recipe"],
            "additions": r.get("additions", {}),
            "notes": r.get("notes", ""),
        })
    
    # 2. Digitalfire recipes
    df_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "digitalfire_recipes.json")
    if os.path.exists(df_path):
        with open(df_path) as f:
            df_recipes = json.load(f)
        for r in df_recipes:
            recipe_dict = {}
            for m in r.get("materials", []):
                recipe_dict[m["name"]] = m["percent"]
            all_refs.append({
                "name": f"{r.get('code', '')} — {r.get('name', '')}".strip(" —"),
                "source": "digitalfire",
                "cone": str(r.get("cone", "6")),
                "surface": r.get("surface", ""),
                "description": r.get("notes", "")[:120] if r.get("notes") else "",
                "recipe": recipe_dict,
                "additions": {},
                "notes": r.get("notes", ""),
            })
    
    # 3. Glazy recipes
    gl_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "glazy_recipes.json")
    if os.path.exists(gl_path):
        with open(gl_path) as f:
            gl_recipes = json.load(f)
        for r in gl_recipes:
            recipe_dict = {}
            additions_dict = {}
            for m in r.get("materials", []):
                if m.get("is_additional"):
                    additions_dict[m["name"]] = m["percent"]
                else:
                    recipe_dict[m["name"]] = m["percent"]
            surface = r.get("surface", "")
            color = r.get("color", "")
            label = f"{surface} {color}".strip() if surface or color else ""
            all_refs.append({
                "name": r.get("name", "Unnamed"),
                "source": "glazy",
                "cone": str(r.get("cone", "6")),
                "surface": surface.lower() if surface else "",
                "description": label,
                "recipe": recipe_dict,
                "additions": additions_dict,
                "notes": r.get("description", ""),
                "glazy_url": r.get("glazy_url", ""),
                "rating": r.get("rating"),
            })
    
    return all_refs

ALL_REFERENCES = load_all_references()

@app.route("/api/references")
def get_references():
    source = request.args.get("source", "all")
    surface = request.args.get("surface", "all")
    refs = ALL_REFERENCES
    if source != "all":
        refs = [r for r in refs if r.get("source") == source]
    if surface != "all":
        refs = [r for r in refs if surface in r.get("surface", "").lower()]
    return jsonify(refs)


@app.route("/api/design", methods=["POST"])
def design():
    data = request.json or {}
    description = data.get("description", "")
    clay_body = data.get("clay_body")
    if not description:
        return jsonify({"success": False, "error": "Please provide a glaze description."})

    try:
        result = glaze_designer.design_glaze(description, clay_body=clay_body)

        if not result.get("success"):
            return jsonify(result)

        # Build recipe table
        recipe = result["recipe"]
        total = sum(recipe.values())
        recipe_table = []
        for mat, amt in sorted(recipe.items(), key=lambda x: -x[1]):
            recipe_table.append({"material": mat, "percent": round(amt / total * 100, 1), "grams": round(amt, 2)})

        # Colorant additions table
        additions_table = []
        if result.get("colorant_additions"):
            for mat, amt in sorted(result["colorant_additions"].items(), key=lambda x: -x[1]):
                additions_table.append({"material": mat, "grams": round(amt, 2), "percent": round(amt / total * 100, 1)})

        # CTE fit info
        cte_info = {"value": result["cte"]}
        if result.get("body_cte"):
            cte_info["body_cte"] = result["body_cte"]
        if result.get("crazing_note"):
            cte_info["note"] = result["crazing_note"]

        return jsonify({
            "success": True,
            "recipe": result["recipe"],
            "recipe_table": recipe_table,
            "additions_table": additions_table,
            "umf": {k: round(v, 4) for k, v in result["umf"].items()},
            "limits": result["limits"],
            "cte": cte_info,
            "food_safety": result["food_safety"],
            "color_notes": result.get("color_notes", []),
            "explanation": result.get("explanation", []),
            "notes": result.get("notes", []),
            "parsed": result.get("parsed", {}),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/analyze", methods=["POST"])
def analyze():
    data = request.json or {}
    recipe = data.get("recipe", {})
    clay_body = data.get("clay_body")
    if not recipe:
        return jsonify({"success": False, "error": "Please provide a recipe."})

    result = analyze_recipe(recipe)

    # Add CTE fit if clay body specified
    if result.get("success") and clay_body:
        body_cte = glaze_designer.CLAY_BODIES.get(clay_body)
        if body_cte:
            cte = result["cte"]
            diff = cte - body_cte
            if diff > 5:
                note = f"⚠️  Glaze CTE ({cte:.1f}) > body CTE ({body_cte:.1f}) — risk of CRAZING"
            elif diff < -10:
                note = f"⚠️  Glaze CTE ({cte:.1f}) << body CTE ({body_cte:.1f}) — risk of SHIVERING"
            else:
                note = f"✅ Glaze CTE ({cte:.1f}) ≈ body CTE ({body_cte:.1f}) — good fit"
            result["cte"] = {"value": cte, "body_cte": body_cte, "note": note}
        else:
            result["cte"] = {"value": result["cte"]}
    elif result.get("success"):
        result["cte"] = {"value": result["cte"]}

    return jsonify(result)


@app.route("/api/variation", methods=["POST"])
def variation():
    data = request.json or {}
    recipe = data.get("recipe", {})
    direction = data.get("direction", "")
    description = data.get("description", "")
    clay_body = data.get("clay_body")
    parsed = data.get("parsed", {})

    if not recipe or not direction:
        return jsonify({"success": False, "error": "Provide recipe and direction."})

    # Build a base_result-like dict for suggest_variations
    try:
        umf = glaze_engine.recipe_to_umf(recipe, MATERIALS_DB)
        base_result = {
            "success": True,
            "description": description or "base",
            "recipe": recipe,
            "umf": umf,
            "colorant_additions": data.get("colorant_additions", {}),
            "parsed": parsed,
            "body_cte": None,
        }
        if clay_body and clay_body in glaze_designer.CLAY_BODIES:
            base_result["body_cte"] = glaze_designer.CLAY_BODIES[clay_body]

        result = glaze_designer.suggest_variations(base_result, direction)

        if not result.get("success"):
            return jsonify(result)

        recipe_out = result["recipe"]
        total = sum(recipe_out.values())
        recipe_table = [{"material": m, "percent": round(a / total * 100, 1), "grams": round(a, 2)}
                        for m, a in sorted(recipe_out.items(), key=lambda x: -x[1])]

        additions_table = []
        if result.get("colorant_additions"):
            for mat, amt in sorted(result["colorant_additions"].items(), key=lambda x: -x[1]):
                additions_table.append({"material": mat, "grams": round(amt, 2), "percent": round(amt / total * 100, 1)})

        cte_info = {"value": result["cte"]}
        if result.get("body_cte"):
            cte_info["body_cte"] = result["body_cte"]
        if result.get("crazing_note"):
            cte_info["note"] = result["crazing_note"]

        return jsonify({
            "success": True,
            "recipe": result["recipe"],
            "recipe_table": recipe_table,
            "additions_table": additions_table,
            "umf": {k: round(v, 4) for k, v in result["umf"].items()},
            "limits": result["limits"],
            "cte": cte_info,
            "food_safety": result.get("food_safety", []),
            "explanation": result.get("explanation", []),
            "notes": result.get("notes", []),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/scale", methods=["POST"])
def scale():
    data = request.json or {}
    recipe = data.get("recipe", {})
    target_weight = data.get("target_weight", 1000)
    if not recipe:
        return jsonify({"success": False, "error": "Provide a recipe."})

    scaled = glaze_engine.scale_recipe(recipe, target_weight)
    total = sum(scaled.values())
    table = [{"material": m, "grams": round(a, 1), "percent": round(a / total * 100, 1)}
             for m, a in sorted(scaled.items(), key=lambda x: -x[1])]
    return jsonify({"success": True, "recipe": scaled, "recipe_table": table, "total_weight": round(total, 1)})


@app.route("/api/generate-image", methods=["POST"])
def generate_image():
    return jsonify({"success": False, "message": "Add OpenAI API key to enable glaze image generation."})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
