from docu_serve.database import engine
from docu_serve.models import Base

# Create all tables
Base.metadata.create_all(bind=engine)
print("Database tables created successfully!")