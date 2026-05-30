import sqlite3
import datetime

today = datetime.date.today().isoformat()
conn = sqlite3.connect("eldorado.db")
cursor = conn.cursor()

print("\n=== MENGINTIP BRANKAS DATABASE (KATEGORI ITEM) ===")
cursor.execute("SELECT title, seller, quantity FROM listings WHERE category = 'Item' AND scraped_date = ?", (today,))
items = cursor.fetchall()

if not items:
    print("Tidak ada item ditemukan!")
else:
    for i, row in enumerate(items, 1):
        # Jika judul kosong, ganti dengan teks default agar tidak error
        judul = row[0] if row[0] else "[Tidak Ada Judul]"
        penjual = row[1] if row[1] else "Anonim"
        stok = row[2] if row[2] is not None else 0
        
        print(f"{i}. {judul[:50]} | Penjual: {penjual} | Stok Saat Ini: {stok}")

print(f"Total: {len(items)} item ditemukan.")
print("==================================================\n")