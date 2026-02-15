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


def describe_glaze(recipe_dict, umf, limits, cte, food_safety):
    """Generate a human-readable description of a glaze from its analysis."""
    lines = []
    
    # Determine surface type from alumina:silica ratio
    al = umf.get("Al2O3", 0)
    si = umf.get("SiO2", 0)
    ratio = si / al if al > 0.01 else 99
    
    if al < 0.15:
        surface = "very fluid/crystalline"
    elif al < 0.25:
        surface = "fluid"
    elif ratio > 8:
        surface = "glossy"
    elif ratio > 6:
        surface = "satin"
    else:
        surface = "matte"
    
    # Dominant flux
    fluxes = {k: umf.get(k, 0) for k in ["CaO","Na2O","K2O","MgO","ZnO","SrO","BaO","Li2O","B2O3"]}
    top_flux = max(fluxes, key=fluxes.get) if fluxes else "CaO"
    flux_names = {"CaO":"calcium","Na2O":"sodium","K2O":"potassium","MgO":"magnesia",
                  "ZnO":"zinc","SrO":"strontium","BaO":"barium","Li2O":"lithium","B2O3":"boron"}
    
    # Colorants in recipe
    colorant_map = {
        "Red Iron Oxide": ("iron", "Fe2O3"), "Cobalt Carbonate": ("cobalt", "CoO"),
        "Cobalt Oxide": ("cobalt", "CoO"), "Copper Carbonate": ("copper", "CuO"),
        "Copper Oxide": ("copper", "CuO"), "Chrome Oxide": ("chrome", "Cr2O3"),
        "Manganese Dioxide": ("manganese", "MnO"), "Rutile": ("rutile/titanium", "TiO2"),
        "Tin Oxide": ("tin", "SnO2"), "Titanium Dioxide": ("titanium", "TiO2"),
        "Zircopax": ("zirconium", "ZrO2"), "Silicon Carbide": ("silicon carbide", None),
    }
    colorants_found = []
    for mat in recipe_dict:
        if mat in colorant_map:
            total = sum(recipe_dict.values())
            pct = recipe_dict[mat] / total * 100 if total else 0
            colorants_found.append((colorant_map[mat][0], pct))
    
    # Build description
    lines.append(f"This is a **{surface}** glaze with a **{flux_names.get(top_flux, top_flux)}-dominant** flux system.")
    
    # Silica/alumina commentary
    if si < 2.5:
        lines.append(f"Low silica ({si:.1f}) makes this a fluid, active glaze — expect movement and potential for special effects.")
    elif si > 4.0:
        lines.append(f"High silica ({si:.1f}) gives this glaze durability and chemical resistance.")
    
    if al > 0.5:
        lines.append(f"High alumina ({al:.2f}) will keep this glaze stiff and resistant to running.")
    elif al < 0.2:
        lines.append(f"Low alumina ({al:.2f}) — this glaze will be very fluid. Watch for running off vertical surfaces.")
    
    # Flux commentary
    if fluxes.get("ZnO", 0) > 0.15:
        lines.append("High zinc oxide promotes matte/crystalline surfaces and can create interesting textural effects.")
    if fluxes.get("MgO", 0) > 0.15:
        lines.append("Significant magnesia contributes a buttery, smooth matte surface quality.")
    if fluxes.get("B2O3", 0) > 0.15:
        lines.append("Boron flux helps the glaze melt at lower temperatures and promotes a smooth, healed surface.")
    if fluxes.get("SrO", 0) > 0.1:
        lines.append("Strontium gives a warmer, smoother quality than calcium — often preferred for subtle color responses.")
    if fluxes.get("Na2O", 0) > 0.25:
        lines.append("High sodium — expect high thermal expansion (potential crazing) and vivid color response from colorants.")
    
    # Colorant commentary
    if colorants_found:
        for cname, cpct in colorants_found:
            if cname == "iron" and cpct > 10:
                lines.append(f"Very high iron ({cpct:.1f}%) — saturated iron territory. Expect dark brown/black with possible metallic crystal formation on cooling.")
            elif cname == "iron" and cpct > 5:
                lines.append(f"Medium-high iron ({cpct:.1f}%) — tenmoku/dark amber range. Crystals possible with slow cooling.")
            elif cname == "iron" and cpct > 1:
                lines.append(f"Light iron ({cpct:.1f}%) — will give warm cream to amber tones depending on base chemistry.")
            elif cname == "cobalt":
                lines.append(f"Cobalt ({cpct:.1f}%) — strong blue colorant. A little goes a long way.")
            elif cname == "copper":
                lines.append(f"Copper ({cpct:.1f}%) — green in oxidation, can shift toward turquoise in high-alkali bases.")
            elif cname == "rutile/titanium":
                lines.append(f"Rutile ({cpct:.1f}%) — promotes variegation, breaking effects, and visual texture in the glaze surface.")
            elif cname == "tin":
                lines.append(f"Tin oxide ({cpct:.1f}%) — opacifier that also serves as crystal nucleation sites.")
            elif cname == "silicon carbide":
                lines.append(f"Silicon carbide ({cpct:.1f}%) — creates localized reduction in oxidation kilns. Used for faux celadon effects.")
    else:
        lines.append("No colorants detected — this should fire as a clear or white base glaze.")
    
    # CTE / fit
    if isinstance(cte, dict):
        cte_val = cte.get("value", 0)
    else:
        cte_val = cte
    if cte_val > 80:
        lines.append(f"High thermal expansion (CTE {cte_val:.0f}) — likely to craze on most bodies. Can be intentional for decorative crackle effects.")
    elif cte_val > 70:
        lines.append(f"Moderate thermal expansion (CTE {cte_val:.0f}) — should fit most mid-fire bodies well.")
    elif cte_val < 65:
        lines.append(f"Low thermal expansion (CTE {cte_val:.0f}) — good for porcelain. Risk of shivering on high-expansion bodies.")
    
    # Limits commentary
    over = [l for l in limits if l.get("status") == "high"]
    under = [l for l in limits if l.get("status") == "low"]
    if over:
        oxides = ", ".join(l["oxide"] for l in over)
        lines.append(f"Note: {oxides} above standard cone 6 limits — this may be intentional for the desired effect.")
    if not over and not under:
        lines.append("All oxides within standard cone 6 limits — well-balanced chemistry.")
    
    return " ".join(lines)


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

        description = describe_glaze(recipe_dict, umf, limits, cte, food_safety)

        # Water recommendation for mixing
        # Target specific gravity ~1.45-1.50 for dipping glazes
        # SG = (dry + water) / (dry/2.5 + water)  where 2.5 is avg powder density
        # For SG=1.45: water = dry * (2.5 - 1.45) / (1.45 * (2.5 - 1))
        # Simplified: ~70-80% water by weight of dry materials for SG ~1.45-1.50
        dry_total = sum(recipe_dict.values())
        water_for_dip = round(dry_total * 0.75, 0)  # ~SG 1.47
        water_for_spray = round(dry_total * 0.95, 0)  # thinner, ~SG 1.35
        water_rec = {
            "dipping": {"water_g": water_for_dip, "sg": 1.47, "note": "Standard dipping consistency"},
            "spraying": {"water_g": water_for_spray, "sg": 1.35, "note": "Thinner for spray application"},
            "note": f"For {dry_total:.0f}g dry materials. Adjust to preference — start thick, add water gradually. Always measure with a hydrometer if available."
        }

        return {
            "success": True,
            "recipe": recipe_dict,
            "recipe_table": recipe_table,
            "umf": {k: round(v, 4) for k, v in umf.items()},
            "limits": limits,
            "cte": cte,
            "food_safety": food_safety,
            "description": description,
            "water": water_rec,
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
            "ingredient_explanations": result.get("ingredient_explanations", ""),
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
    import urllib.request, urllib.error
    OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")
    # Also check a local .env file
    if not OPENAI_KEY:
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
        if os.path.exists(env_path):
            for line in open(env_path):
                if line.startswith('OPENAI_API_KEY='):
                    OPENAI_KEY = line.split('=', 1)[1].strip()
    if not OPENAI_KEY:
        return jsonify({"success": False, "message": "Set OPENAI_API_KEY in .env file to enable image generation."})
    data = request.get_json() or {}
    description = data.get("description", "")
    recipe_summary = data.get("recipe_summary", "")
    if not description:
        return jsonify({"success": False, "message": "No description provided."})

    prompt = (
        f"A close-up macro photograph of a ceramic glaze test tile. The glaze is: {description}. "
        "Shot from above at a slight angle, filling the frame. Show only the glazed ceramic surface — "
        "no text, no labels, no annotations, no diagrams, no words of any kind. "
        "Focus on the glaze surface texture, color depth, light reflections, and any visible effects "
        "like crazing lines, crystals, color breaks, or pooling. "
        "The test tile is a simple flat or slightly curved piece. Neutral background. "
        "Natural soft studio lighting. Photorealistic, shot on a macro lens, shallow depth of field. "
        "Style: ceramic glaze test tile photography as seen on Glazy.org or ceramic studio documentation."
    )

    payload = json.dumps({
        "model": "dall-e-3",
        "prompt": prompt,
        "n": 1,
        "size": "1024x1024",
        "quality": "standard"
    }).encode()

    req = urllib.request.Request(
        "https://api.openai.com/v1/images/generations",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_KEY}"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode())
        image_url = result["data"][0]["url"]
        revised_prompt = result["data"][0].get("revised_prompt", "")

        # Auto-save image locally
        saved_path = ""
        try:
            save_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saved_glazes")
            os.makedirs(save_dir, exist_ok=True)
            import re, time
            slug = re.sub(r'[^a-z0-9]+', '-', description.lower().strip())[:60].strip('-')
            ts = time.strftime("%Y%m%d-%H%M%S")
            img_name = f"{ts}_{slug}.png"
            img_path = os.path.join(save_dir, img_name)
            with urllib.request.urlopen(image_url, timeout=30) as img_resp:
                with open(img_path, 'wb') as f:
                    f.write(img_resp.read())

            # Save recipe card alongside
            recipe_html = data.get("recipe_html", "")
            ingredients_html = data.get("ingredients_html", "")
            card_path = os.path.join(save_dir, f"{ts}_{slug}.md")
            with open(card_path, 'w') as f:
                f.write(f"# {description}\n\n")
                f.write(f"*Generated {time.strftime('%Y-%m-%d %H:%M')}*\n\n")
                f.write(f"![Preview]({img_name})\n\n")
                if recipe_summary:
                    f.write("## Recipe\n\n")
                    f.write("| Material | % |\n|---|---|\n")
                    for part in recipe_summary.split(', '):
                        # "Nepheline Syenite 25.8%" → table row
                        idx = part.rfind(' ')
                        if idx > 0:
                            f.write(f"| {part[:idx]} | {part[idx+1:]} |\n")
                        else:
                            f.write(f"| {part} | |\n")
                    f.write("\n")
                if ingredients_html:
                    f.write("## How It Works\n\n")
                    for line in ingredients_html.strip().split('\n'):
                        line = line.strip()
                        if line:
                            # Split on " — " to get material name vs explanation
                            if ' — ' in line:
                                mat, expl = line.split(' — ', 1)
                                f.write(f"**{mat.strip()}** — {expl.strip()}\n\n")
                            else:
                                f.write(f"{line}\n\n")
            saved_path = img_path
        except Exception as save_err:
            print(f"Warning: could not save image locally: {save_err}")

        return jsonify({"success": True, "image_url": image_url, "revised_prompt": revised_prompt, "saved_path": saved_path})
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        try:
            err_msg = json.loads(body).get("error", {}).get("message", body)
        except Exception:
            err_msg = body
        return jsonify({"success": False, "message": f"OpenAI error: {err_msg}"}), 500
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
