from __future__ import annotations

import enum

from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


class Base(DeclarativeBase):
    """Project-wide SQLAlchemy declarative base."""

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

    id: Mapped[int] = mapped_column(primary_key=True)
    class_name: Mapped[str] = mapped_column(String(200), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String, default="")
    form: Mapped[ItemForm | None] = mapped_column(SQLEnum(ItemForm), default=ItemForm.SOLID)
    stack_size_code: Mapped[str | None] = mapped_column(String(50))
    stack_size: Mapped[int | None] = mapped_column()
    energy_value: Mapped[float] = mapped_column(default=0.0)
    radioactive_decay: Mapped[float] = mapped_column(default=0.0)
    sink_points: Mapped[int | None] = mapped_column()
    fluid_color: Mapped[str | None] = mapped_column(String(50))

    ingredients: Mapped[list[RecipeIngredient]] = relationship(back_populates="item")

class Building(Base):
    __tablename__ = 'buildings'

    id: Mapped[int] = mapped_column(primary_key=True)
    class_name: Mapped[str] = mapped_column(String(200), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String, default="")
    power_mw: Mapped[float] = mapped_column(default=0.0)

    recipes: Mapped[list[Recipe]] = relationship(back_populates="building")

class Recipe(Base):
    __tablename__ = 'recipes'

    id: Mapped[int] = mapped_column(primary_key=True)
    class_name: Mapped[str] = mapped_column(String(200), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    crafting_time: Mapped[float] = mapped_column()
    building_id: Mapped[int] = mapped_column(ForeignKey('buildings.id'))

    building: Mapped[Building] = relationship(back_populates="recipes")
    ingredients: Mapped[list[RecipeIngredient]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan"
    )

class RecipeIngredient(Base):
    __tablename__ = 'recipe_ingredients'

    id: Mapped[int] = mapped_column(primary_key=True)
    quantity: Mapped[int] = mapped_column()
    is_output: Mapped[bool] = mapped_column(default=False)
    recipe_id: Mapped[int] = mapped_column(ForeignKey('recipes.id', ondelete='CASCADE'))
    item_id: Mapped[int] = mapped_column(ForeignKey('items.id'))

    recipe: Mapped[Recipe] = relationship(back_populates="ingredients")
    item: Mapped[Item] = relationship(back_populates="ingredients")

class Group(Base):
    __tablename__ = 'groups'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String, default="")

    production_lines: Mapped[list[ProductionLine]] = relationship(back_populates="group")
    resource_nodes: Mapped[list[ResourceNode]] = relationship(back_populates="group")

class ProductionLine(Base):
    __tablename__ = 'production_lines'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    target_item_id: Mapped[int] = mapped_column(ForeignKey('items.id'))
    target_rate: Mapped[float] = mapped_column()
    group_id: Mapped[int] = mapped_column(ForeignKey('groups.id'))
    is_active: Mapped[bool] = mapped_column(default=True)

    group: Mapped[Group] = relationship(back_populates="production_lines")
    factories: Mapped[list[Factory]] = relationship(back_populates="production_line")
    target_item: Mapped[Item] = relationship()

class Factory(Base):
    __tablename__ = 'factories'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    production_line_id: Mapped[int] = mapped_column(ForeignKey('production_lines.id'))
    recipe_id: Mapped[int] = mapped_column(ForeignKey('recipes.id'))
    building_count: Mapped[int] = mapped_column()
    clock_speed: Mapped[float] = mapped_column(default=100.0)
    order: Mapped[int] = mapped_column(default=0)

    production_line: Mapped[ProductionLine] = relationship(back_populates="factories")
    recipe: Mapped[Recipe] = relationship()

class ResourceNode(Base):
    __tablename__ = 'resource_nodes'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    item_id: Mapped[int] = mapped_column(ForeignKey('items.id'))
    purity: Mapped[Purity | None] = mapped_column(SQLEnum(Purity), default=Purity.NORMAL)
    extraction_rate: Mapped[float] = mapped_column()
    group_id: Mapped[int] = mapped_column(ForeignKey('groups.id'))

    group: Mapped[Group] = relationship(back_populates="resource_nodes")
    item: Mapped[Item] = relationship()

def get_engine(database_url):
    return create_engine(database_url)

def create_tables(engine):
    Base.metadata.create_all(engine)

def get_session(engine):
    Session = sessionmaker(bind=engine)
    return Session()

def is_etl_complete(engine) -> bool:
    """True if the ETL has populated the schema (items, buildings, recipes tables exist)."""
    from sqlalchemy import inspect
    tables = set(inspect(engine).get_table_names())
    return {"items", "buildings", "recipes"}.issubset(tables)
