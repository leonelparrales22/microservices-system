from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Product

DATABASE_URL = "sqlite:///./inventario.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)

# Crear tablas
Base.metadata.create_all(bind=engine)

# Insertar datos iniciales solo si no existen
db = SessionLocal()

products = [
    Product(product_id="P001", name="Laptop", in_stock=True, quantity=50, price=1200.0),
    Product(product_id="P002", name="Mouse", in_stock=True, quantity=200, price=25.5),
    Product(product_id="P003", name="Keyboard", in_stock=False, quantity=0, price=45.0),
]

for p in products:
    exists = db.query(Product).filter_by(product_id=p.product_id).first()
    if not exists:
        db.add(p)

db.commit()
db.close()

print("Base de datos inicializada.")
