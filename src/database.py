from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
import enum

Base = declarative_base()

class ItemForm(enum.Enum):
    SOLID = "SOLID"
    LIQUID = "LIQUID"
    GAS = "GAS"

class Purity(enum.Enum):
    IMPURE = "IMPURE"
    NORMAL = "NORMAL"
    PURE = "PURE"

class Item(Base):
    __tablename__ = 'items'
    
    id = Column(Integer, primary_key=True)
    class_name = Column(String(200), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(String, default="")
    form = Column(SQLEnum(ItemForm), default=ItemForm.SOLID)
    stack_size_code = Column(String(50), nullable=True)
    stack_size = Column(Integer, nullable=True)
    energy_value = Column(Float, default=0)
    radioactive_decay = Column(Float, default=0)
    sink_points = Column(Integer, nullable=True)
    fluid_color = Column(String(50), nullable=True)
    
    ingredients = relationship("RecipeIngredient", back_populates="item")

class Building(Base):
    __tablename__ = 'buildings'
    
    id = Column(Integer, primary_key=True)
    class_name = Column(String(200), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(String, default="")
    
    recipes = relationship("Recipe", back_populates="building")

class Recipe(Base):
    __tablename__ = 'recipes'
    
    id = Column(Integer, primary_key=True)
    class_name = Column(String(200), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    crafting_time = Column(Float, nullable=False)
    building_id = Column(Integer, ForeignKey('buildings.id'))
    
    building = relationship("Building", back_populates="recipes")
    ingredients = relationship("RecipeIngredient", back_populates="recipe", cascade="all, delete-orphan")

class RecipeIngredient(Base):
    __tablename__ = 'recipe_ingredients'
    
    id = Column(Integer, primary_key=True)
    quantity = Column(Integer, nullable=False)
    is_output = Column(Boolean, default=False)
    recipe_id = Column(Integer, ForeignKey('recipes.id', ondelete='CASCADE'))
    item_id = Column(Integer, ForeignKey('items.id'))
    
    recipe = relationship("Recipe", back_populates="ingredients")
    item = relationship("Item", back_populates="ingredients")

class Group(Base):
    __tablename__ = 'groups'

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(String, default="")

    production_lines = relationship("ProductionLine", back_populates="group")

class ProductionLine(Base):
    __tablename__ = 'production_lines'

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    target_item_id = Column(Integer, ForeignKey('items.id'))
    target_rate = Column(Float, nullable=False)
    group_id = Column(Integer, ForeignKey('groups.id'), nullable=True)
    is_active = Column(Boolean, default=True)

    group = relationship("Group", back_populates="production_lines")
    factories = relationship("Factory", back_populates="production_line")
    target_item = relationship("Item")
    resource_nodes = relationship("ResourceNode", back_populates="production_line")

class Factory(Base):
    __tablename__ = 'factories'

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    production_line_id = Column(Integer, ForeignKey('production_lines.id'))
    recipe_id = Column(Integer, ForeignKey('recipes.id'))
    building_count = Column(Integer, nullable=False)
    clock_speed = Column(Float, default=100.0)
    order = Column(Integer, default=0)

    production_line = relationship("ProductionLine", back_populates="factories")
    recipe = relationship("Recipe")

class ResourceNode(Base):
    __tablename__ = 'resource_nodes'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    item_id = Column(Integer, ForeignKey('items.id'))
    purity = Column(SQLEnum(Purity), default=Purity.NORMAL)
    extraction_rate = Column(Float)
    production_line_id = Column(Integer, ForeignKey('production_lines.id'))

    production_line = relationship("ProductionLine", back_populates="resource_nodes")
    item = relationship("Item")

def get_engine(database_url):
    return create_engine(database_url)

def create_tables(engine):
    Base.metadata.create_all(engine)

def get_session(engine):
    Session = sessionmaker(bind=engine)
    return Session()
