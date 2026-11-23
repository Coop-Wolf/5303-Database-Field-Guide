import sqlite3

conn = sqlite3.connect("data/writes.db")
cursor = conn.cursor()

cursor.execute("SELECT COUNT(*) FROM purchases;")
purchase_count = cursor.fetchone()[0]

cursor.execute("SELECT SUM(num_purchases) FROM monthly_sales;")
monthly_total = cursor.fetchone()[0]

print("Purchases:", purchase_count)
print("Monthly sales total:", monthly_total)

conn.close()