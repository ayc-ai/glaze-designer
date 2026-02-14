# 🏺 Glaze Designer — Cone 6 Oxidation

A ceramic glaze chemistry engine and designer tool. Describe what you want, get a recipe.

## Features
- **Design Mode** — describe a glaze in natural language → get a recipe with UMF, limit checks, CTE, food safety
- **Analyze Mode** — input any recipe → full chemistry breakdown
- **Reference Library** — 190+ cone 5-6 recipes from Digitalfire and Glazy
- **Variation Engine** — tweak recipes ("more matte", "reduce crazing", etc.)
- **Batch Calculator** — scale to any batch size

## Quick Start
```bash
pip install flask
python app.py
# Open http://localhost:5000
```

## Architecture
- `glaze_engine.py` — Core chemistry (UMF calc, limit checks, thermal expansion, food safety)
- `glaze_designer.py` — Natural language → recipe translation
- `app.py` — Flask web server + API
- `materials_db.json` — 34 raw materials with oxide analyses
- `digitalfire_recipes.json` — 47 Digitalfire reference recipes
- `glazy_recipes.json` — 137 Glazy community recipes

## API Endpoints
- `POST /api/design` — {description, clay_body, cone} → recipe
- `POST /api/analyze` — {recipe: {material: percent}} → analysis
- `POST /api/variation` — {recipe, direction} → modified recipe
- `POST /api/scale` — {recipe, target_weight} → batch
- `GET /api/materials` — available materials list
- `GET /api/clay-bodies` — clay body options

## License
MIT
