# test.py
from src.database import get_engine, get_session
from src.calculator import calculate_recipe_requirements
import os
from dotenv import load_dotenv

load_dotenv()
engine = get_engine(os.getenv('DATABASE_URL'))
session = get_session(engine)

result = calculate_recipe_requirements(session, recipe_id=1, item_id=14, target_rate=60)
print(result)

session.close()