# test.py
from src.database import get_engine, get_session
from src.calculator import calculate_recipe_requirements, get_production_chain
import os
from dotenv import load_dotenv

load_dotenv()
engine = get_engine(os.getenv('DATABASE_URL'))
session = get_session(engine)

result = get_production_chain(session, 14, 60)
print(result)

session.close()