# src/formatters.py

from typing import Any


def format_ingredients_list(ingredients: list[dict[str, Any]]) -> str:
    """
    Format a list of ingredient dictionaries into a human-readable string.
    
    Args:
        ingredients: List of ingredient dicts with 'name' and 'quantity' keys
        
    Returns:
        Comma-separated string like "Iron Ingot x3, Copper Wire x2"
    """
    
    formatted_list = [f"{item['name']} x{item['quantity']}" for item in ingredients]

    return ", ".join(formatted_list)

def format_recipe_for_table(recipe: dict[str, Any]) -> dict[str, Any]:
    """
    Format a recipe dictionary for display in a table by converting
    ingredient/product lists into readable strings.
    
    Args:
        recipe: Recipe dict containing 'inputs' and 'outputs' as lists
        
    Returns:
    """

    formatted_dict = recipe.copy()
    formatted_dict['inputs'] = format_ingredients_list(recipe['inputs'])
    formatted_dict['outputs'] = format_ingredients_list(recipe['outputs'])

    return formatted_dict