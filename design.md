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