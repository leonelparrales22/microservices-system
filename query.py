import sqlite3

conn = sqlite3.connect("pedidos1.db")
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("Tablas en la BD:", tables)
cursor.execute("SELECT * FROM orders")
rows = cursor.fetchall()
print("Historial de pedidos en pedidos1:")
for row in rows:
    print(row)
conn.close()
