---
applyTo: '**'
---

# Architecture Guidelines

## 🎯 Core Philosophy
This codebase prioritizes clarity, predictability, and navigability over traditional software engineering abstractions. Follow these patterns strictly.

---

## 🧠 Step 1: Understanding & Context Recovery

### **1. Create an `Architectural Overview` Docstring**
Include at the top of your file:
- **Responsibility:** What business problem this solves (1-2 sentences)
- **Key Interactions:** Conceptual inputs, outputs, and configuration
- **Navigation Guide:** Data flow and section markers for AI navigation
- **For Navigation:** Explicitly instruct use of VS Code outline (Ctrl+Shift+O)

**Maintainability Rule:** Document concepts that change infrequently, not implementation details.

### **2. AI Comprehension Optimization (PROVEN PATTERNS)**

**Configuration Architecture Integration**:
```python
"""
CONFIGURATION ARCHITECTURE:
- Single source of truth: All configuration in CONFIG dictionary
- Coordination boundaries: Orchestrator functions extract config values
- Primitive injection: Business logic accepts explicit typed parameters
- Zero hidden dependencies: All behavior predictable from signatures
- Full testability: Functions accept primitives, no config mocking required
"""
```

**Context Complexity Metrics**:
- **Configuration Context**: <200 lines total
- **Coordination Points**: <10 functions access CONFIG
- **CONFIG Per-Function**: <5 accesses in orchestrators, 0 in business logic
- **Hidden Dependencies**: Zero functions with undeclared dependencies
- **Type Explicitness**: 100% of parameters/returns have type hints

### **3. Fallback Search Strategy**
If you lose context:
1. Search for section markers: `# ═════`
2. Find entry point: `if __name__ == "__main__"`
3. Use AI recovery functions: `_ai_context_recovery_summary()`

---

## 🚀 Core Implementation Patterns

### **1. Structure: Cohesive Modules with Clear Sections**
Use highly visible, searchable section markers:
```python
# ═══════════════════════════════════════════════════════════════════════════
# 🏗️ INITIALIZATION SECTION
# ═══════════════════════════════════════════════════════════════════════════
```

Keep related code together within modules. Prefer cohesion (related code in same place) over premature distribution across files.

### **2. Simplicity: Prefer Data over Abstraction**
- Use **standalone functions** instead of complex class hierarchies
- **Choose dicts vs dataclasses based on context** (see guidance below)
- Keep data shapes explicit and visible

**Dict vs Dataclass Decision Matrix:**

| Use Dict When... | Use Dataclass When... |
|------------------|----------------------|
| Prototyping/exploratory code | Schema is stable (production) |
| ≤3 simple fields | 4+ fields |
| No polymorphism (variants) | Data has variants (split/unsplit, partitioned) |
| Same module only | Cross-layer communication (solver→viz) |
| Direct JSON serialization needed | Type safety and IDE support needed |

**Critical Anti-Pattern (Causes Bugs):**
```python
# ❌ WRONG - Dict with inconsistent access patterns
x = item.get("x", item.get("easting", 0))  # Which key is canonical?
tier2 = stats.get("tier2_wkt")  # Exists for unsplit, missing for split

# ❌ WRONG - Deep nested dict access without validation
result = data.get("a", {}).get("b", {}).get("c", [])  # Silently fails
```

**Correct Pattern - Dataclass with variant handling:**
```python
@dataclass
class ClusterStats:
    was_partitioned: bool
    value: Optional[str] = None        # For non-partitioned
    partitions: List[Partition] = None # For partitioned
    
    def get_value(self) -> str:
        """Single access point handles all variants."""
        if self.was_partitioned:
            return merge([p.value for p in self.partitions])
        return self.value
    
    @classmethod
    def from_dict(cls, d: dict) -> "ClusterStats":
        # Explicit field mapping - no silent failures
        return cls(
            was_partitioned=d.get("was_partitioned", False),
            value=d.get("value"),
            partitions=[Partition.from_dict(p) for p in d.get("partitions", [])]
        )
```

The tradeoffs are:
- **Dict**: Flexible but error-prone - typos, missing keys fail silently
- **Dataclass**: Strict but safe - IDE catches errors, type hints document schema

**Guideline:** Start with dicts for CONFIG and simple local data. Convert to dataclass when:
1. Data crosses module boundaries (solver→viz)
2. Data has variants/polymorphism
3. Deep nesting with optional keys
4. Same dict structure appears in 3+ functions

### **3. Configuration: Hybrid Architecture Pattern (PROVEN)**

**Anti-Pattern:** Scattered global configuration dictionaries.

**Correct Pattern:** CONFIG Dictionary + Coordination Boundaries + Primitive Injection

```python
CONFIG = {
    "processing": {"batch_size": 1000},
    "validation": {"strict_mode": True}
}

# Coordination boundary - extracts CONFIG values
def orchestrator(input_data):
    batch_size = CONFIG["processing"]["batch_size"]
    strict_mode = CONFIG["validation"]["strict_mode"]
    return process_data(input_data, batch_size, strict_mode)

# Business logic - explicit parameters only
def process_data(data: Any, batch_size: int, strict_mode: bool) -> Any:
    # Function behavior completely predictable from signature
    # No hidden CONFIG dependencies
```

**Critical Rules:**
- Never create globals outside CONFIG
- Only orchestrator functions access CONFIG
- Business logic accepts primitives only
- **<10 total coordination boundary functions**
- **<5 CONFIG accesses per orchestrator function**
- **0 CONFIG accesses in business logic functions**

**Function Classification:**
- **Orchestrator**: Coordinates workflow, extracts CONFIG, calls business logic (0-5 CONFIG accesses)
- **Business Logic**: Processes data, accepts explicit parameters (0 CONFIG accesses - STRICT)

### **4. Visibility: Debugging and Modification Zones**

**Complexity Limits:**
- **Maximum nesting depth**: 4 levels (target: 3 levels)
- **Exception**: Try/except blocks don't count toward nesting

**Nesting Depth Check:**
```python
# ❌ WRONG - 5 levels
if condition_1:           # Level 1
    for item in items:    # Level 2
        if condition_2:   # Level 3
            for x in y:   # Level 4
                if c:     # Level 5 (OVER LIMIT)

# ✅ CORRECT - 3 levels (extract inner logic)
if condition_1:
    items_filtered = filter_items(items, condition_2)
    for item in items_filtered:
        process_item(item)  # Extracted function
```

**Debugging Patterns:**
- **Use logger.info() over print()** with progress indicators (🚀, 📊, ✅)
- **Structure functions with internal sections** (`# === SECTION NAME ===`)
- **Structured error messages**: `logger.error(f"❌ WORKFLOW FAILED: {str(e)}")`
- **Defensive data handling**: `df.columns = df.columns.str.strip()`
- **MODIFICATION POINT:** markers for obvious change zones
- **State summary functions**: `print_configuration()`, `_debug_current_state_for_ai()`

### **5. Testing: Simple Functions**
Write simple test functions in `tests` folder with assert statements and success indicators.

### **6. Size Constraints (STRICT - ENFORCED DURING DEVELOPMENT)**

**HARD LIMITS (Non-Negotiable):**
- **Function Maximum**: 75 lines
- **CONFIG Dictionary**: <200 lines total
- **Nesting Depth**: ≤4 levels (optimize for 3)

**Function Size Enforcement:**
Check function length at these milestones during development:
- **50 lines** → ⚠️ Warning: Approaching limit. Plan extraction strategy.
- **75 lines** → 🔴 STOP: Refactor before adding more code.
- **100 lines** → ❌ CRITICAL: Immediate refactor required.

**Quick Refactoring Checklist:**
- Internal `# === SECTIONS ===` present? → Extract each to function
- Nested loops/conditionals? → Extract to named helpers
- Multiple responsibilities? → Split orchestration from business logic
- Repeated patterns? → Extract shared logic

**Exemption Process:** None. All functions must comply.

### **7. Type Safety Requirements (MANDATORY)**

**Rule:** All functions MUST have complete type hints on parameters and return values.

**Enforcement Checklist:**
- ✅ Every parameter has type annotation
- ✅ Return type declared (use `-> None` if no return)
- ✅ Use `Optional[T]` for nullable parameters/returns
- ✅ Import types: `from typing import List, Dict, Optional, Any`

**Example:**
```python
from typing import Optional, Dict, Any
import pandas as pd

# ❌ WRONG - No type hints
def process_data(df, config, mode=None):
    return transformed_df

# ✅ CORRECT - Complete type contract
def process_data(
    df: pd.DataFrame,
    config: Dict[str, Any],
    mode: Optional[str] = None
) -> pd.DataFrame:
    return transformed_df
```

**Why 100% Coverage:**
- AI understands function contracts without reading implementation
- Autocomplete works correctly
- Type errors caught before runtime
- Function signatures are self-documenting

**Exemptions:** None. Even single-line helpers must have type hints.

### **8. Code Duplication Prevention**

**Rule:** Shared logic MUST be extracted before duplication exceeds 20 lines.

**Detection Pattern:**
If you write similar code in two places, ask:
1. Is core logic identical? → Extract to shared function
2. Only rendering differs? → Separate data prep from rendering
3. Different APIs, same workflow? → Create data layer + multiple renderers

**Refactoring Trigger:** `Similarity > 70% AND Length > 20 lines`

**Pattern: Shared Data Layer**
```python
# ❌ WRONG - Duplicate 300-line functions
def generate_plot_matplotlib(...):
    # 250 lines of data prep (DUPLICATED)
    # 50 lines matplotlib rendering

def generate_plot_plotly(...):
    # 250 lines of data prep (DUPLICATED)
    # 50 lines plotly rendering

# ✅ CORRECT - Separated data from rendering
def prepare_plot_data(...) -> Dict[str, Any]:
    # 250 lines of data prep (SHARED)
    return {"x": x_data, "y": y_data, ...}

def render_matplotlib(plot_data: Dict[str, Any]) -> None:
    # 50 lines matplotlib rendering

def render_plotly(plot_data: Dict[str, Any]) -> None:
    # 50 lines plotly rendering
```

**Benefit:** Bug fixes in shared logic require single edit, not N edits.

---

## Multi-Layer Codebase Guidelines

These guidelines prevent bugs in producer-consumer architectures (e.g., solver→visualization, backend→frontend, service→renderer).

### 🔴 CRITICAL: Never Recompute Derived Data

**The #1 Bug Pattern:** Producer computes derived data and stores it, but consumer recomputes from scratch causing mismatches.

**ALWAYS:**
```python
# ✅ CORRECT: Use producer's exact computed result
cached_result = data.get("computed_value")
if cached_result:
    result = deserialize(cached_result)
else:
    logger.warning("computed_value missing - using fallback")
    result = compute_manually(...)  # FALLBACK ONLY
```

**NEVER:**
```python
# ❌ WRONG: Recomputing in consumer
result = compute_from_inputs(param1, param2)  # May differ from producer!
```

**Why This Matters:**
- Producer and consumer might use different input values
- Floating-point operations may produce slightly different results
- Split/partitioned data has per-partition results, not aggregate

### Polymorphic Data Access

When data has different shapes based on type (e.g., split vs unsplit, simple vs complex):

**ALWAYS check type flag before accessing nested data:**

```python
def get_computed_result(stats: Dict) -> Any:
    """Handle all data variants uniformly."""
    if stats.get("was_partitioned"):
        # Partitioned data: result is per-partition
        partitions = stats.get("partitions", [])
        results = [p.get("computed_value") for p in partitions if p.get("computed_value")]
        return merge_results(results) if results else None
    else:
        # Simple data: result is at top level
        return stats.get("computed_value")
```

**Document Data Location by Type:**
| Data | Simple Type | Partitioned Type |
|------|-------------|------------------|
| `computed_value` | `stats["computed_value"]` | `stats["partitions"][i]["computed_value"]` |
| `config_used` | `stats["config_used"]` | `stats["config_used"]` (same) |

### Producer-to-Consumer Data Contract

**Producer MUST export:**
```python
output = {
    # REQUIRED - type discriminator
    "was_partitioned": bool,
    
    # REQUIRED - computed results
    "computed_value": str,      # Serialized result
    "parameters_used": dict,    # For debugging/validation
    
    # FOR PARTITIONED DATA
    "partitions": [
        {
            "computed_value": str,
            "partition_id": int,
        }
    ],
}
```

**Consumer MUST NOT:**
- Recompute derived values from scratch (use stored results)
- Assume data location without checking type flag
- Use early returns that skip variant handling

### Config Key Standardization

**Single Source of Truth for Shared Parameters:**
- Define canonical location: `CONFIG["module_name"]["param_name"]`
- Consumer MUST use same keys - never create parallel `other_module_param_name`

```python
# In orchestrator (extracts once, passes to all consumers)
shared_config = {
    "multiplier": CONFIG["producer"]["multiplier"],
    "threshold": CONFIG["producer"]["threshold"],
}
run_producer(..., config=shared_config)
run_consumer(..., config=shared_config)
```

### Typed Data Structures for Cross-Layer Communication

**When adding new inter-module data:**

1. **Define dataclass in `models/`:**
```python
@dataclass
class ComputedResult:
    value_serialized: str
    parameters: dict
    
    def get_value(self) -> Any:
        return deserialize(self.value_serialized)
```

2. **Export from producer as dict, convert at boundary:**
```python
# Producer returns dict (for JSON serialization)
return {"value_serialized": ..., "parameters": ...}

# Consumer converts at entry point
result = ComputedResult(**data["computed_result"])
value = result.get_value()  # Type-safe access
```

### Entity Data Standardization

**Use typed dataclasses, not `Dict[str, Any]`:**

```python
# ✅ CORRECT
entities: List[Entity] = [Entity.from_dict(d) for d in raw_data]
identifier = entity.id  # Consistent access

# ❌ WRONG - Multiple fallback patterns
id = item.get("id", item.get("entity_id", item.get("ID", 0)))
```

**Standard Fields:**
- Use consistent field names across the codebase
- Use dataclass `.from_dict()` with explicit field mapping
- Use properties for derived values (e.g., `.normalized_id`)

### Debugging Cross-Layer Issues

**When a consumer bug appears:**

1. **Check if consumer is recomputing:**
   ```bash
   grep -n "compute\|calculate\|derive" consumer_module.py | head -20
   ```
   If compute calls exist outside fallback blocks, it's likely recomputing.

2. **Verify producer exports expected data:**
   ```python
   logger.debug(f"output keys: {output.keys()}")
   logger.debug(f"was_partitioned: {output.get('was_partitioned')}")
   ```

3. **Trace early returns that might skip cases:**
   ```python
   # Don't do this:
   if some_condition:
       return early  # Might skip partitioned data!
   
   # Do this:
   handled = set()
   for item in items:
       if handle_item(item):
           handled.add(item.id)
   ```

---

## Additional Patterns From Production Experience

### Avoid Fallback Chaining Anti-Pattern

**Problem:** Multiple fallback keys hide which field is canonical.

```python
# ❌ WRONG - Which key is the source of truth?
x = item.get("x", item.get("easting", item.get("X", 0)))

# ❌ WRONG - Multiple possible sources
r_max = stats.get("overall_r_max") or stats.get("max_spacing_m", 0.0)
```

**Solution:** Standardize field names in source, not consumer.

```python
# ✅ CORRECT - Single canonical field name
x = item["x"]  # Fails fast if missing

# ✅ CORRECT - Use from_dict() to map legacy names once
@classmethod
def from_dict(cls, d: dict) -> "Entity":
    return cls(
        x=d.get("x") or d.get("easting") or d.get("X"),  # Map ONCE at boundary
    )
```

### Early Return Must Not Skip Variants

**Problem:** Checking one variant returns before processing others.

```python
# ❌ WRONG - Exits if ANY cluster has tier2_wkt, skipping split clusters
if any(stats.get("tier2_wkt") for stats in cluster_stats.values()):
    render_all_tiers()  
    return  # Split clusters never processed!
```

**Solution:** Track what's been processed explicitly.

```python
# ✅ CORRECT - Track processed items
handled_clusters = set()

# Process variant A
for key, stats in cluster_stats.items():
    if not stats.get("was_split") and stats.get("tier2_wkt"):
        render_unsplit_tier2(stats)
        handled_clusters.add(key)

# Process variant B  
for key, stats in cluster_stats.items():
    if stats.get("was_split") and key not in handled_clusters:
        render_split_tier2(stats)
        handled_clusters.add(key)
```

### File Size Limits for Complex Modules

**When a file exceeds ~2000 LOC**, consider splitting along natural boundaries:

| Split When... | Split Into... |
|---------------|---------------|
| Class + helpers > 2000 LOC | `core.py` + `helpers.py` |
| Multiple render formats | `data_prep.py` + `render_{format}.py` |
| Algorithm + orchestration | `algorithm.py` + `orchestrator.py` |
| Many trace/layer types | `traces/layer_a.py`, `traces/layer_b.py` |

**Keep together:**
- Functions that share significant state/data structures
- Tightly coupled logic that changes together
- CONFIG extraction and its consumers

### Serialization Boundaries: When to Use WKT/JSON

**Use serialized format (WKT, JSON string) when:**
- Crossing process boundaries (multiprocessing)
- Persisting to disk/cache
- Passing through generic interfaces (Dict[str, Any])

**Use native objects when:**
- Same module/file
- Performance-critical inner loops
- Type checking is needed

```python
# ✅ CORRECT - Serialize at boundaries only
def solver_export() -> Dict[str, str]:
    return {"geometry_wkt": polygon.wkt}  # Serialize at export

def viz_import(data: Dict[str, str]) -> None:
    geom = wkt.loads(data["geometry_wkt"])  # Deserialize at import
    # Use native geometry object internally
```