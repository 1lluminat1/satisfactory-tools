# Recipe Browser - Design Doc

## What It Shows

### Main view: Table of all recipes with columns:
- Recipe Name
- Building (where it's made)
- Crafting Time (seconds)
- Inputs (abbreviated, like "Iron Ingot x3")
- Outputs (abbreviated, like "Iron Plate x2")

### User interactions:
1. **Search bar** - Filter recipes by name
2. **Building dropdown** - Filter by building type (Constructor, Assembler, etc.)
3. **Click on recipe row** - Shows detailed view

### Detailed view (when clicking a recipe):
- Recipe Name (header)
- Building Name
- Crafting Time
- **Inputs table:**
  - Item Name | Quantity | Rate per minute
- **Outputs table:**
  - Item Name | Quantity | Rate per minute

*(Rate per minute = quantity / (crafting_time / 60))*

---

## Queries You Need

### Query 1: Get all recipes (for main table)
- Returns: List of all recipes with basic info
- Data structure:
```python
[
    {
        "id": 1,
        "name": "Iron Plate",
        "building": "Constructor",
        "crafting_time": 6.0,
        "inputs_summary": "Iron Ingot x3",  # or list of tuples
        "outputs_summary": "Iron Plate x2"  # or list of tuples
    },
    # ... more recipes
]
```

### Query 2: Get recipe details (for detailed view)
- Input: recipe_id
- Returns: Full recipe details
- Data structure:
```python
{
    "id": 1,
    "name": "Iron Plate",
    "building": "Constructor",
    "crafting_time": 6.0,
    "inputs": [
        {"name": "Iron Ingot", "quantity": 3}
    ],
    "outputs": [
        {"name": "Iron Plate", "quantity": 2}
    ]
}
```

### Query 3: Get all unique buildings (for dropdown filter)
- Returns: List of building names
- Data structure:
```python
["Constructor", "Assembler", "Smelter", ...]
```

---

## Implementation Order

1. **Build Query 2 first** - `get_recipe_details(session, recipe_id)`
   - Test it with a specific recipe ID
   - Make sure relationships work

2. **Build Query 3** - `get_all_buildings(session)`
   - Simple distinct query
   - Quick win

3. **Build Query 1** - `get_all_recipes(session, search=None, building=None)`
   - Loops through recipes
   - Calls `get_recipe_details` for each one? Or optimizes with joins?
   - Applies filters if provided

4. **Build Streamlit UI**
   - Use the queries you built
   - Display the data

---

# Item Explorer - Design Doc

## What It Shows

### Main view: Table of all items with columns:
- Item Name
- Form (Solid/Liquid/Gas)
- Stack Size
- Sink Points (or "-" if N/A)

### User interactions:
1. **Search bar** - Filter items by name
2. **Form dropdown** - Filter by form (All, Solid, Liquid, Gas)
3. **Click on item row** - Shows detailed view

### Detailed view (when clicking an item):
- Item Name (header)
- Form, Stack Size, Energy Value, Sink Points, etc.
- **"Used In" section:**
  - Table of recipes that consume this item (as input)
  - Recipe Name | Building | Quantity Used
- **"Produced By" section:**
  - Table of recipes that produce this item (as output)
  - Recipe Name | Building | Quantity Produced

---

## Queries You Need

### Query 1: Get all items
- Returns: List of all items with basic info
- Data structure:
```python
[
    {
        "id": 1,
        "name": "Iron Ingot",
        "form": "SOLID",
        "stack_size": 100,
        "sink_points": 2
    },
    # ... more items
]
```

### Query 2: Get recipes that use an item (as input)
- Input: item_id
- Returns: List of recipes that consume this item
- Data structure:
```python
[
    {
        "recipe_name": "Iron Plate",
        "building": "Constructor",
        "quantity": 3  # How much of this item the recipe needs
    },
    # ... more recipes
]
```

### Query 3: Get recipes that produce an item (as output)
- Input: item_id
- Returns: List of recipes that produce this item
- Data structure:
```python
[
    {
        "recipe_name": "Iron Ingot",
        "building": "Smelter",
        "quantity": 1  # How much of this item the recipe produces
    },
    # ... more recipes
]
```

---

## Implementation Order

1. **Build Query 1** - `get_all_items(session)`
   - Similar to get_all_recipes
   - Query all Items, return as list of dicts

2. **Build Queries 2 & 3** - `get_recipes_using_item(session, item_id)` and `get_recipes_producing_item(session, item_id)`
   - Query RecipeIngredient table
   - Filter by item_id and is_output flag
   - Join with Recipe and Building to get names

3. **Add formatter functions** (if needed)
   - Format items for table display
   - May not need much formatting here

4. **Build Streamlit UI**
   - Similar structure to Recipe Browser
   - Filters, table, detail view

---

**Next Step:** Build Query 1 first - `get_all_items(session)`

# Production Calculator - Design Doc

## Overview

The Production Calculator helps users plan factory production lines by calculating resource requirements and rates for desired outputs.

---

## Feature 1: Forward Calculator (Output → Inputs)

### What It Does
User specifies a desired output, calculator determines all required inputs.

### User Input:
- **Target Item:** Dropdown to select item (e.g., "Iron Plate")
- **Target Rate:** Number input for items per minute (e.g., 60)
- **Recipe Selection:** If multiple recipes produce the same item, let user choose

### Output Display:
Shows a breakdown of the entire production chain:
```
To produce: 60 Iron Plates/min

Direct Requirements:
├─ 90 Iron Ingots/min (from Constructor)
└─ Requires 1.5 Constructors running at 100%

Iron Ingot Requirements:
├─ 90 Iron Ore/min (from Smelter)  
└─ Requires 3 Smelters running at 100%

Final Raw Materials Needed:
└─ 90 Iron Ore/min

Building Summary:
├─ 1.5x Constructor
└─ 3x Smelter
```

### Key Calculations:
1. **Recipe lookup:** Find recipe that produces target item
2. **Rate calculation:** 
   - Recipe produces X items per Y seconds
   - Items per minute = (X / Y) * 60
   - To get target rate, need (target_rate / items_per_minute) machines
3. **Input requirements:** For each input to the recipe, calculate required rate
4. **Recursion:** Repeat for each input that has its own recipe (until you hit raw materials)

---

## Feature 2: Reverse Calculator (Inputs → Output)

### What It Does
User specifies available raw materials, calculator shows what can be produced.

### User Input:
- **Available Resources:** List of items with rates
  - Example: "240 Iron Ore/min, 120 Copper Ore/min"
- **Desired Output Item:** What do you want to make?

### Output Display:
```
With your inputs:
├─ 240 Iron Ore/min
└─ 120 Copper Ore/min

You can produce:
├─ 80 Iron Plates/min (uses 240 Iron Ore/min)
└─ Leftover: 0 Iron Ore/min

OR

├─ 60 Reinforced Iron Plates/min
├─ Uses: 180 Iron Ore/min, 120 Copper Ore/min  
└─ Leftover: 60 Iron Ore/min

To max out production, you need:
└─ Additional 60 Copper Ore/min
```

### Key Calculations:
1. Find all recipes that use available inputs
2. Calculate max production rate limited by available inputs
3. Show what's left over
4. Show what additional inputs would unlock more production

---

## Implementation Strategy

### Phase 1: Build Core Calculator Logic (NO UI YET!)

**Step 1: Build basic rate calculator**
- Function: `calculate_recipe_rate(recipe_id, target_rate) -> dict`
- Given a recipe and desired output rate
- Returns: required input rates and number of machines

**Step 2: Build dependency tree**
- Function: `get_production_chain(item_id, target_rate) -> dict`
- Recursively calculates entire production chain
- Handles items with no recipes (raw materials)
- Returns nested structure with all requirements

**Step 3: Handle multiple recipes**
- Some items have multiple recipes (alternates)
- Need to let user choose OR pick a default
- Add parameter: `preferred_recipes={item_id: recipe_id}`

**Step 4: Test with simple examples**
- Iron Plate (simple: 1 input, 1 output)
- Reinforced Iron Plate (complex: multiple inputs)
- Test full dependency chains

### Phase 2: Build Reverse Calculator

**Step 1: Find eligible recipes**
- Given available inputs, find which recipes are possible
- Function: `find_recipes_using_inputs(available_items) -> list[recipe_id]`

**Step 2: Calculate bottlenecks**
- For a recipe, determine which input is the limiting factor
- Calculate max production rate based on limiting input

**Step 3: Optimize allocation**
- Given inputs and desired output, calculate optimal resource allocation
- Show what's needed vs what's available

### Phase 3: Build UI

**Simple Streamlit Interface:**
```
Production Calculator

[Tab 1: Forward Calculator]
┌─────────────────────────────────┐
│ Target Item: [Iron Plate ▼]    │
│ Target Rate: [60] /min          │
│ [Calculate Production Chain]     │
└─────────────────────────────────┘

Results: [Expandable tree view of requirements]

[Tab 2: Reverse Calculator]
┌─────────────────────────────────┐
│ Available Resources:            │
│ [+ Add Resource]                │
│ - Iron Ore: [240] /min          │
│ - Copper Ore: [120] /min        │
│                                 │
│ Target Output: [Wire ▼]         │
│ [Calculate Max Production]       │
└─────────────────────────────────┘

Results: [Production options and leftovers]
```

---

## Data Structures

### Production Chain Result:
```python
{
    "target": {
        "item": "Iron Plate",
        "rate": 60,
        "recipe": "Iron Plate (Constructor)"
    },
    "direct_requirements": [
        {
            "item": "Iron Ingot",
            "rate": 90,
            "machines": 1.5
        }
    ],
    "dependencies": {
        "Iron Ingot": {
            # Nested production chain for Iron Ingot
            "target": {...},
            "direct_requirements": [...],
            "dependencies": {...}
        }
    },
    "raw_materials": {
        "Iron Ore": 90
    },
    "building_summary": {
        "Constructor": 1.5,
        "Smelter": 3
    }
}
```

---

## Challenges to Solve

**1. Circular dependencies**
- Some games have recipes that loop (A needs B, B needs A)
- Satisfactory might not have this, but worth checking
- Handle gracefully if it exists

**2. Multiple recipes for same item**
- Example: Iron Ingot can be made via normal recipe OR alternate
- Need UI to let user choose OR smart default selection
- Store user preferences

**3. Rate precision**
- Machines can't run at partial capacity in-game
- Calculator shows 1.5 machines, but user needs 2
- Show both "ideal" and "practical" numbers

**4. Byproducts**
- Some recipes produce multiple outputs
- Need to track and display these
- Factor into calculations

---

## Implementation Order

1. **Start with Phase 1, Step 1** - Build simple rate calculator
   - Test with one recipe (Iron Plate)
   - Make sure math is correct
   
2. **Phase 1, Step 2** - Add recursion
   - Test with 2-level chain (Iron Plate → Iron Ingot → Iron Ore)
   
3. **Phase 1, Step 3** - Handle multiple recipes
   - Add recipe selection logic
   
4. **Test extensively before UI**
   - Write test functions that print results
   - Verify calculations manually
   
5. **Phase 3** - Build Streamlit UI
   - Start with forward calculator only
   - Add reverse calculator after forward works

6. **Polish** - Better visualization, error handling, edge cases

---

Proposed Tables
1. groups table:
- id (PK)
- name (e.g., "North", "South", "Main Base")
- description (optional)
2. production_lines table:
- id (PK)
- name (e.g., "Computer Production (North)")
- target_item_id (FK → items) - What's being produced
- target_rate (float) - Desired output rate per minute
- group_id (FK → groups, nullable) - Can be ungrouped
- is_active (boolean)
3. factories table:
- id (PK)
- name (e.g., "Circuit Board Assembly #1")
- production_line_id (FK → production_lines)
- recipe_id (FK → recipes)
- building_count (int) - How many buildings
- clock_speed (float, default 100.0) - Overclock percentage
- order (int) - Position in the production chain (1st step, 2nd step, etc.)
4. resource_nodes table:
- id (PK)
- name (custom user name, e.g., "Iron Node Alpha")
- item_id (FK → items) - What resource it produces
- purity (enum: IMPURE, NORMAL, PURE)
- extraction_rate (float) - Items per minute
- production_line_id (FK → production_lines, nullable) - Which line uses it