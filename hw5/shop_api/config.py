import os

# postgres — данные в PostgreSQL, memory — в памяти процесса (удобно для тестов).
STORAGE_BACKEND = os.getenv('STORAGE_BACKEND', 'postgres')
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql+asyncpg://shop:shop@localhost:5432/shop')
