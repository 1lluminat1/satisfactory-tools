import json
import os
from dotenv import load_dotenv
from database import Base, get_engine, get_session, create_tables
from database import Item, Building, Recipe, RecipeIngredient, ItemForm
import pprint
import re

# Load environment variables
load_dotenv()

def load_json_data():
    """Load the Docs.json file and return the data"""
    with open('data/Docs.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data

def get_form(s):
    return 'SOLID' if s == 'RF_SOLID' else 'LIQUID' if s == 'RF_LIQUID' else 'GAS' 

def get_ss_value(s):
    return 500 if s == 'SS_HUGE' else 200 if s == 'SS_BIG' else 100 if s == 'SS_MEDIUM' else 50 if s == 'SS_SMALL' else 1 if s == 'SS_ONE' else -1 

def parse_ingredients_or_products(ingredient_string):
    """
    Parse strings like:
    "((ItemClass=.../Desc_IronIngot.Desc_IronIngot_C',Amount=3))"
    Returns list of tuples: [('Desc_IronIngot_C', 3)]
    """
    # Extract all class names and amounts
    class_pattern = r"Desc_(\w+)_C"
    amount_pattern = r"Amount=(\d+)"
    
    class_names = re.findall(class_pattern, ingredient_string)
    amounts = re.findall(amount_pattern, ingredient_string)
    
    return list(zip(class_names, amounts))

def get_or_create_building(session, building_class_name):
    """
    Check if building exists, create if not.
    Returns the building object.
    """
    building = session.query(Building).filter_by(class_name=building_class_name).first()
    if not building:
        # Extract a readable name from class name
        # "Build_ConstructorMk1_C" -> "Constructor Mk1"
        name = building_class_name.replace("Build_", "").replace("_C", "").replace("_", " ")
        building = Building(
            class_name=building_class_name,
            name=name,
            description=""  # No description available
        )
        session.add(building)
        session.flush()
    return building

def load_recipes(session, data):
    """Load all recipes from JSON data"""
    recipe_count = 0
    processed_recipes = set()
    
    # Find recipe entries
    for entry in data:
        if "FGRecipe" in entry.get("NativeClass", ""):
            for recipe_data in entry["Classes"]:

                # Skip if Build Gun recipe
                if 'BuildGun' in recipe_data['mProducedIn']:
                    continue

                class_name = recipe_data['ClassName']

                # Skip if recipe has been processed already
                if class_name in processed_recipes:
                    continue

                processed_recipes.add(class_name)
                # Extract building name from mProducedIn
                produced_in = recipe_data.get("mProducedIn", "")
                building_match = re.search(r"Build_(\w+)\.Build_(\w+)_C", produced_in)
                if not building_match:
                    continue  # Skip recipes without valid building
                
                building_class_name = f"Build_{building_match.group(2)}_C"
                
                # Get or create building
                building = get_or_create_building(session, building_class_name)
                
                # Create recipe
                recipe = Recipe(
                    class_name=recipe_data["ClassName"],
                    name=recipe_data["mDisplayName"],
                    crafting_time=float(recipe_data["mManufactoringDuration"]),
                    building_id=building.id
                )
                session.add(recipe)
                session.flush()  # Get recipe.id before adding ingredients
                
                # Parse and add ingredients (inputs)
                ingredients = parse_ingredients_or_products(recipe_data.get("mIngredients", ""))
                for class_name_part, amount in ingredients:
                    full_class_name = f"Desc_{class_name_part}_C"
                    item = session.query(Item).filter_by(class_name=full_class_name).first()
                    if item:
                        ingredient = RecipeIngredient(
                            quantity=int(amount),
                            is_output=False,
                            recipe_id=recipe.id,
                            item_id=item.id
                        )
                        session.add(ingredient)
                
                # Parse and add products (outputs)
                products = parse_ingredients_or_products(recipe_data.get("mProduct", ""))
                for class_name_part, amount in products:
                    full_class_name = f"Desc_{class_name_part}_C"
                    item = session.query(Item).filter_by(class_name=full_class_name).first()
                    if item:
                        product = RecipeIngredient(
                            quantity=int(amount),
                            is_output=True,
                            recipe_id=recipe.id,
                            item_id=item.id
                        )
                        session.add(product)
                
                recipe_count += 1
    
    session.commit()
    print(f"Loaded {recipe_count} recipes")

def main():
    # Setup database
    engine = get_engine(os.getenv('DATABASE_URL'))
    Base.metadata.drop_all(engine)
    create_tables(engine)
    session = get_session(engine)
    
    # Load JSON data
    data = load_json_data()
    
    print(f"Loaded {len(data)} entries from JSON")
    
    # TODO: Parse and load data here
    # You have access to:
    # - data (the JSON array)
    # - session (to add/commit to database)
    # - All the models (Item, Building, Recipe, RecipeIngredient)
    
    # Your code goes here!
        # Load items
    for entry in data:
        if 'ItemDescriptor' in entry['NativeClass']:
            for item_data in entry['Classes']:
                # Insert directly, no fancy logic
                name = item_data['mDisplayName']
                class_name = item_data['ClassName']
                description = item_data['mDescription']
                form = get_form(item_data['mForm'])
                stack_size_code = item_data['mStackSize']
                stack_size = get_ss_value(stack_size_code)
                energy_value = item_data['mEnergyValue']
                radioactive_decay = item_data['mRadioactiveDecay']
                sink_points = item_data['mResourceSinkPoints']
                fluid_color = item_data['mFluidColor']
                item = Item(class_name=class_name, name=name, description=description, 
                            form=form, stack_size_code=stack_size_code, 
                            stack_size=stack_size, energy_value=energy_value, 
                            radioactive_decay=radioactive_decay, sink_points=sink_points, 
                            fluid_color=fluid_color)
                session.add(item)    

    session.commit()

    load_recipes(session, data)

    items = session.query(Item).all()
    print(f"✅ Loaded {len(items)} items")
    print(f"Example: {items[0].name} - {items[0].class_name}")

    recipes = session.query(Recipe).all()
    print(f"✅ Loaded {len(recipes)} recipes")
    print(f"Example: {recipes[0].name} - {recipes[0].crafting_time}")

    session.close()
    print("✅ ETL Complete!")

if __name__ == "__main__":
    main()