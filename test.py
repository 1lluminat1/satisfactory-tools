# test.py
import os
from dotenv import load_dotenv

from src.database import get_engine, get_session
from src.calculator import ProductionCalculator

load_dotenv()
engine = get_engine(os.getenv('DATABASE_URL'))
session = get_session(engine)

calculator = ProductionCalculator(session)
result = calculator.calculate(14, 60)
print(result)

session.close()
