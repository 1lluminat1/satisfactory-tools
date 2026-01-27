import json
import os
from dotenv import load_dotenv
from database import get_engine, get_session, create_tables
from database import Item, Building, Recipe, RecipeIngredient, ItemForm
import pprint

# Load environment variables
load_dotenv()

def get_form(s):
    return 'SOLID' if s == 'RF_SOLID' else 'LIQUID' if s == 'RF_LIQUID' else 'GAS' 

def get_ss_value(s):
    return 500 if s == 'SS_HUGE' else 200 if s == 'SS_BIG' else 100 if s == 'SS_MEDIUM' else 50 if s == 'SS_SMALL' else 1 if s == 'SS_ONE' else -1 

def load_json_data():
    """Load the Docs.json file and return the data"""
    with open('data/Docs.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data

def main():
    # Setup database
    engine = get_engine(os.getenv('DATABASE_URL'))
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

    items = session.query(Item).all()
    print(f"✅ Loaded {len(items)} items")
    print(f"Example: {items[0].name} - {items[0].class_name}")
    print(items[0])

    session.close()
    print("✅ ETL Complete!")

if __name__ == "__main__":
    main()