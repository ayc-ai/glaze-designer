"""
Ceramic Glaze Chemistry Engine
==============================
Core calculations for cone 6 oxidation glaze formulation:
- Recipe ↔ Unity Molecular Formula (UMF) conversion
- Limit formula validation
- Thermal expansion estimation
- Food safety checks
"""

import json
import os
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Oxide molecular weights (g/mol)
# ---------------------------------------------------------------------------
OXIDE_MW: Dict[str, float] = {
    "SiO2":   60.08,
    "Al2O3": 101.96,
    "B2O3":   69.62,
    "Na2O":   61.98,
    "K2O":    94.20,
    "CaO":    56.08,
    "MgO":    40.30,
    "ZnO":    81.38,
    "SrO":   103.62,
    "BaO":   153.33,
    "Li2O":   29.88,
    "Fe2O3": 159.69,
    "TiO2":   79.87,
    "MnO":    70.94,
    "P2O5":  141.94,
    "CoO":    74.93,
    "CuO":    79.55,
    "Cr2O3": 151.99,
    "NiO":    74.69,
}

# ---------------------------------------------------------------------------
# Oxide groupings for UMF
# ---------------------------------------------------------------------------
FLUX_OXIDES = {"Na2O", "K2O", "CaO", "MgO", "ZnO", "SrO", "BaO", "Li2O"}
AMPHOTERIC_OXIDES = {"Al2O3", "B2O3"}
GLASS_FORMER_OXIDES = {"SiO2"}
COLORANT_OXIDES = {"Fe2O3", "TiO2", "MnO", "P2O5", "CoO", "CuO", "Cr2O3", "NiO"}

# ---------------------------------------------------------------------------
# Cone 6 oxidation limit ranges (Hesselberth & Roy style)
# Format: {oxide: (min, max)} in UMF moles (fluxes sum to 1.0)
# ---------------------------------------------------------------------------
CONE6_LIMITS: Dict[str, Tuple[float, float]] = {
    # Fluxes (must sum to ~1.0)
    "Na2O":  (0.05, 0.30),
    "K2O":   (0.03, 0.25),
    "CaO":   (0.10, 0.65),
    "MgO":   (0.00, 0.35),
    "ZnO":   (0.00, 0.30),
    "SrO":   (0.00, 0.20),
    "BaO":   (0.00, 0.15),
    "Li2O":  (0.00, 0.10),
    # Amphoterics
    "Al2O3": (0.20, 0.55),
    "B2O3":  (0.00, 0.60),
    # Glass formers
    "SiO2":  (2.50, 5.00),
}

# ---------------------------------------------------------------------------
# Thermal expansion coefficients (× 10⁻⁷ /°C, Appen factors)
# ---------------------------------------------------------------------------
THERMAL_EXPANSION_COEFFICIENTS: Dict[str, float] = {
    "SiO2":   38.0,
    "Al2O3":  16.7,
    "B2O3":    5.0,   # low-B2O3 glazes; anomalous at high levels
    "Na2O":  395.0,
    "K2O":   283.0,
    "CaO":   163.0,
    "MgO":    45.0,
    "ZnO":    50.0,
    "SrO":   160.0,
    "BaO":   140.0,
    "Li2O":  270.0,
    "Fe2O3":  55.0,
    "TiO2":  -15.0,
    "MnO":    55.0,
    "P2O5":  -40.0,
    "CoO":    50.0,
    "CuO":    30.0,
    "Cr2O3":  50.0,
    "NiO":    50.0,
}


# ---------------------------------------------------------------------------
# Load materials database
# ---------------------------------------------------------------------------
def load_materials_db(path: Optional[str] = None) -> dict:
    """Load and return the materials database from JSON."""
    if path is None:
        path = os.path.join(os.path.dirname(__file__), "materials_db.json")
    with open(path) as f:
        data = json.load(f)
    return data["materials"]


# ---------------------------------------------------------------------------
# recipe_to_umf
# ---------------------------------------------------------------------------
def recipe_to_umf(
    recipe: Dict[str, float],
    materials_db: Optional[dict] = None,
) -> Dict[str, float]:
    """
    Convert a weight-percent recipe to a Unity Molecular Formula (UMF).

    Parameters
    ----------
    recipe : dict
        {material_name: weight_amount} — does NOT need to sum to 100.
    materials_db : dict, optional
        Materials database (loaded from JSON if not provided).

    Returns
    -------
    dict
        {oxide: moles} normalized so that RO/R2O fluxes sum to 1.0.
    """
    if materials_db is None:
        materials_db = load_materials_db()

    # Step 1: Accumulate oxide weights from all materials
    oxide_weights: Dict[str, float] = {}
    total_weight = sum(recipe.values())

    for material_name, amount in recipe.items():
        mat = materials_db.get(material_name)
        if mat is None:
            raise KeyError(f"Material '{material_name}' not found in database")
        for oxide, wt_pct in mat.get("oxides", {}).items():
            oxide_weights[oxide] = oxide_weights.get(oxide, 0.0) + amount * wt_pct / 100.0

    # Step 2: Convert weights to moles
    oxide_moles: Dict[str, float] = {}
    for oxide, weight in oxide_weights.items():
        mw = OXIDE_MW.get(oxide)
        if mw is None:
            continue  # skip oxides we don't track (SnO2, ZrO2 etc.)
        oxide_moles[oxide] = weight / mw

    # Step 3: Normalize — fluxes sum to 1.0
    flux_total = sum(oxide_moles.get(f, 0.0) for f in FLUX_OXIDES)
    if flux_total <= 0:
        # Can't normalize; return raw moles
        return oxide_moles

    umf = {}
    for oxide, moles in oxide_moles.items():
        umf[oxide] = moles / flux_total

    return umf


# ---------------------------------------------------------------------------
# check_limits
# ---------------------------------------------------------------------------
def check_limits(
    umf: Dict[str, float],
    cone: int = 6,
) -> List[dict]:
    """
    Validate a UMF against cone 6 oxidation limit ranges.

    Returns a list of dicts: {oxide, value, min, max, status}
    status is 'ok', 'low', or 'high'.
    """
    limits = CONE6_LIMITS  # only cone 6 implemented
    results = []
    for oxide, (lo, hi) in limits.items():
        val = umf.get(oxide, 0.0)
        if val < lo - 1e-9:
            status = "low"
        elif val > hi + 1e-9:
            status = "high"
        else:
            status = "ok"
        results.append({
            "oxide": oxide,
            "value": round(val, 4),
            "min": lo,
            "max": hi,
            "status": status,
        })
    return results


# ---------------------------------------------------------------------------
# thermal_expansion
# ---------------------------------------------------------------------------
def thermal_expansion(umf: Dict[str, float]) -> float:
    """
    Estimate coefficient of thermal expansion (CTE) from UMF.

    Uses Appen-style mole-fraction weighted coefficients.
    Returns CTE in units of 10⁻⁷ /°C.
    """
    total_moles = sum(umf.values())
    if total_moles <= 0:
        return 0.0

    cte = 0.0
    for oxide, moles in umf.items():
        coeff = THERMAL_EXPANSION_COEFFICIENTS.get(oxide, 0.0)
        cte += coeff * (moles / total_moles)
    return round(cte, 1)


# ---------------------------------------------------------------------------
# food_safety_check
# ---------------------------------------------------------------------------
def food_safety_check(
    recipe: Dict[str, float],
    umf: Dict[str, float],
) -> List[str]:
    """
    Flag food-safety concerns based on recipe and UMF.

    Checks for:
    - High barium (BaO > 0.05 UMF)
    - Lithium (Li2O > 0.05 UMF)
    - High zinc (ZnO > 0.25 UMF)
    - Excessive colorant oxides
    - Specific toxic materials in recipe
    """
    warnings = []

    # UMF-based checks
    if umf.get("BaO", 0) > 0.05:
        warnings.append(f"⚠️  High BaO ({umf.get('BaO', 0):.3f} mol) — barium is toxic if leachable")

    if umf.get("Li2O", 0) > 0.05:
        warnings.append(f"⚠️  High Li2O ({umf.get('Li2O', 0):.3f} mol) — lithium concerns at high levels")

    if umf.get("ZnO", 0) > 0.25:
        warnings.append(f"⚠️  High ZnO ({umf.get('ZnO', 0):.3f} mol) — may leach in acidic foods")

    if umf.get("CuO", 0) > 0.02:
        warnings.append(f"⚠️  Copper oxide ({umf.get('CuO', 0):.3f} mol) — test for leaching")

    if umf.get("CoO", 0) > 0.03:
        warnings.append(f"⚠️  High cobalt ({umf.get('CoO', 0):.3f} mol) — may be problematic")

    if umf.get("Cr2O3", 0) > 0.01:
        warnings.append(f"⚠️  Chrome oxide present — avoid in food surfaces")

    if umf.get("MnO", 0) > 0.05:
        warnings.append(f"⚠️  High manganese ({umf.get('MnO', 0):.3f} mol)")

    if umf.get("NiO", 0) > 0.005:
        warnings.append(f"⚠️  Nickel oxide present — toxic, not food-safe")

    # Recipe-based checks
    recipe_lower = {k.lower(): v for k, v in recipe.items()}
    total = sum(recipe.values())
    for name, amount in recipe.items():
        pct = amount / total * 100 if total > 0 else 0
        nl = name.lower()
        if "barium" in nl and pct > 5:
            warnings.append(f"⚠️  {name} at {pct:.1f}% — barium compound, test thoroughly")
        if "lead" in nl:
            warnings.append(f"🚫 {name} — LEAD IS NOT FOOD-SAFE")

    if not warnings:
        warnings.append("✅ No obvious food-safety concerns (still test with lab leach test)")

    return warnings


# ---------------------------------------------------------------------------
# scale_recipe
# ---------------------------------------------------------------------------
def scale_recipe(
    recipe: Dict[str, float],
    target_weight: float,
) -> Dict[str, float]:
    """Scale a recipe to a target total weight (grams)."""
    total = sum(recipe.values())
    if total <= 0:
        return recipe.copy()
    factor = target_weight / total
    return {mat: round(amt * factor, 1) for mat, amt in recipe.items()}


# ---------------------------------------------------------------------------
# umf_to_recipe (linear programming)
# ---------------------------------------------------------------------------
def umf_to_recipe(
    target_umf: Dict[str, float],
    available_materials: List[str],
    materials_db: Optional[dict] = None,
    total_batch: float = 100.0,
) -> Optional[Dict[str, float]]:
    """
    Solve for a recipe that produces a target UMF using linear programming.

    Parameters
    ----------
    target_umf : dict
        Target UMF {oxide: moles} (fluxes sum to 1.0).
    available_materials : list
        Material names to use.
    materials_db : dict, optional
    total_batch : float
        Target total weight for the recipe.

    Returns
    -------
    dict or None
        {material_name: weight} or None if infeasible.
    """
    if materials_db is None:
        materials_db = load_materials_db()

    target_oxides = [ox for ox in target_umf if target_umf[ox] != 0]
    if not target_oxides:
        return {}

    n_mats = len(available_materials)
    n_ox = len(target_oxides)

    # Build A matrix: moles of oxide j per gram of material i
    A_eq = [[0.0] * n_mats for _ in range(n_ox)]
    for i, mat_name in enumerate(available_materials):
        mat = materials_db[mat_name]
        for j, oxide in enumerate(target_oxides):
            wt_pct = mat.get("oxides", {}).get(oxide, 0.0)
            mw = OXIDE_MW.get(oxide, 1.0)
            A_eq[j][i] = (wt_pct / 100.0) / mw

    # UMF normalization: sum_i(A[j,i]*x[i]) = target[j] * s
    # Variables: x[0..n_mats-1] = material weights, x[n_mats] = s (scale)
    n_vars = n_mats + 1
    A = [[0.0] * n_vars for _ in range(n_ox)]
    for j in range(n_ox):
        for i in range(n_mats):
            A[j][i] = A_eq[j][i]
        A[j][n_mats] = -target_umf.get(target_oxides[j], 0.0)

    b = [0.0] * n_ox
    c = [0.0] * n_vars
    for i in range(n_mats):
        c[i] = 1.0

    result_x = _linprog_simplex(c, A, b, n_vars, lower_bounds=[0.0]*n_mats + [0.001])

    if result_x is None:
        return None

    weights = result_x[:n_mats]
    total = sum(weights)
    if total < 1e-9:
        return None

    factor = total_batch / total
    recipe = {}
    for i, mat_name in enumerate(available_materials):
        w = weights[i] * factor
        if w > 0.01:
            recipe[mat_name] = round(w, 2)

    return recipe


def _linprog_simplex(
    c: List[float],
    A_eq: List[List[float]],
    b_eq: List[float],
    n_vars: int,
    lower_bounds: Optional[List[float]] = None,
    max_iter: int = 5000,
) -> Optional[List[float]]:
    """
    Minimal simplex solver for: min c·x s.t. A_eq·x = b_eq, x >= lb.

    Handles equality constraints via two-phase simplex.
    Pure Python, no dependencies.
    """
    m = len(A_eq)  # number of constraints
    n = n_vars     # original variables

    if lower_bounds is None:
        lower_bounds = [0.0] * n

    # Shift variables: y_i = x_i - lb_i, so y_i >= 0
    # A·(y+lb) = b => A·y = b - A·lb
    b_shifted = list(b_eq)
    for i in range(m):
        for j in range(n):
            b_shifted[i] -= A_eq[i][j] * lower_bounds[j]

    # Make b_shifted >= 0 by flipping rows if needed
    row_flip = [False] * m
    for i in range(m):
        if b_shifted[i] < -1e-12:
            b_shifted[i] = -b_shifted[i]
            A_eq[i] = [-a for a in A_eq[i]]
            row_flip[i] = True

    # Phase 1: add artificial variables to find a basic feasible solution
    # Tableau: [A | I | b]  with objective min sum(artificials)
    # Columns: y_0..y_{n-1}, a_0..a_{m-1}
    total_cols = n + m  # y vars + artificial vars
    # Tableau rows: m constraint rows + 1 objective row
    # tab[i] = [coeffs..., rhs]
    tab = []
    for i in range(m):
        row = [0.0] * (total_cols + 1)
        for j in range(n):
            row[j] = A_eq[i][j]
        row[n + i] = 1.0  # artificial
        row[total_cols] = b_shifted[i]
        tab.append(row)

    # Objective row for phase 1: min sum of artificials
    obj = [0.0] * (total_cols + 1)
    for i in range(m):
        obj[n + i] = 1.0
    # Subtract basic rows from objective
    for i in range(m):
        for j in range(total_cols + 1):
            obj[j] -= tab[i][j]
    tab.append(obj)

    basis = list(range(n, n + m))  # artificial vars are initial basis

    def pivot(tab, m, total_cols, row, col):
        piv = tab[row][col]
        if abs(piv) < 1e-15:
            return False
        inv_piv = 1.0 / piv
        for j in range(total_cols + 1):
            tab[row][j] *= inv_piv
        for i in range(m + 1):
            if i == row:
                continue
            factor = tab[i][col]
            if abs(factor) < 1e-15:
                continue
            for j in range(total_cols + 1):
                tab[i][j] -= factor * tab[row][j]
        return True

    # Phase 1 simplex
    for _ in range(max_iter):
        # Find most negative reduced cost
        obj_row = tab[m]
        min_rc = -1e-9
        enter = -1
        for j in range(total_cols):
            if obj_row[j] < min_rc:
                min_rc = obj_row[j]
                enter = j
        if enter == -1:
            break  # optimal

        # Min ratio test
        min_ratio = float('inf')
        leave = -1
        for i in range(m):
            if tab[i][enter] > 1e-12:
                ratio = tab[i][total_cols] / tab[i][enter]
                if ratio < min_ratio:
                    min_ratio = ratio
                    leave = i
        if leave == -1:
            return None  # unbounded

        pivot(tab, m, total_cols, leave, enter)
        basis[leave] = enter

    # Check if artificials are zero
    phase1_val = tab[m][total_cols]
    if abs(phase1_val) > 1e-6:
        return None  # infeasible

    # Phase 2: optimize original objective over feasible set
    # Replace objective row with original c (in shifted y-space)
    obj2 = [0.0] * (total_cols + 1)
    for j in range(n):
        obj2[j] = c[j]
    # Set artificial columns to large M to keep them out
    for j in range(n, n + m):
        obj2[j] = 1e6

    tab[m] = obj2

    # Express objective in terms of non-basic variables
    for i in range(m):
        bv = basis[i]
        if abs(tab[m][bv]) > 1e-15:
            factor = tab[m][bv]
            for j in range(total_cols + 1):
                tab[m][j] -= factor * tab[i][j]

    # Phase 2 simplex
    for _ in range(max_iter):
        obj_row = tab[m]
        min_rc = -1e-9
        enter = -1
        for j in range(total_cols):
            if obj_row[j] < min_rc:
                min_rc = obj_row[j]
                enter = j
        if enter == -1:
            break

        min_ratio = float('inf')
        leave = -1
        for i in range(m):
            if tab[i][enter] > 1e-12:
                ratio = tab[i][total_cols] / tab[i][enter]
                if ratio < min_ratio:
                    min_ratio = ratio
                    leave = i
        if leave == -1:
            return None

        pivot(tab, m, total_cols, leave, enter)
        basis[leave] = enter

    # Extract solution (in y-space)
    y = [0.0] * n
    for i in range(m):
        bv = basis[i]
        if bv < n:
            y[bv] = tab[i][total_cols]

    # Shift back: x = y + lb
    x = [y[j] + lower_bounds[j] for j in range(n)]
    return x


# ---------------------------------------------------------------------------
# Pretty-print helpers
# ---------------------------------------------------------------------------
def format_umf(umf: Dict[str, float]) -> str:
    """Format a UMF for display."""
    lines = []
    lines.append("  Fluxes (RO/R2O, sum ≈ 1.0):")
    flux_sum = 0
    for ox in ["Li2O", "Na2O", "K2O", "CaO", "MgO", "ZnO", "SrO", "BaO"]:
        val = umf.get(ox, 0)
        if val > 0.001:
            lines.append(f"    {ox:8s} {val:.4f}")
            flux_sum += val
    lines.append(f"    {'TOTAL':8s} {flux_sum:.4f}")

    lines.append("  Amphoterics:")
    for ox in ["Al2O3", "B2O3"]:
        val = umf.get(ox, 0)
        if val > 0.001:
            lines.append(f"    {ox:8s} {val:.4f}")

    lines.append("  Glass formers:")
    for ox in ["SiO2"]:
        val = umf.get(ox, 0)
        if val > 0.001:
            lines.append(f"    {ox:8s} {val:.4f}")

    colorants = [(ox, umf.get(ox, 0)) for ox in ["Fe2O3", "TiO2", "MnO", "P2O5", "CoO", "CuO", "Cr2O3", "NiO"] if umf.get(ox, 0) > 0.0005]
    if colorants:
        lines.append("  Colorants/Other:")
        for ox, val in colorants:
            lines.append(f"    {ox:8s} {val:.4f}")

    return "\n".join(lines)


def format_limit_check(results: List[dict]) -> str:
    """Format limit check results."""
    lines = []
    for r in results:
        icon = "✅" if r["status"] == "ok" else ("⬇️ " if r["status"] == "low" else "⬆️ ")
        lines.append(f"  {icon} {r['oxide']:8s} {r['value']:.4f}  [{r['min']:.2f} – {r['max']:.2f}]")
    return "\n".join(lines)
