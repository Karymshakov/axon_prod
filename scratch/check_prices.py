import os
import sys
import django

# Set DATABASE_URL to sqlite
os.environ['DATABASE_URL'] = r'sqlite:///c:\Users\kille\OneDrive\Рабочий стол\Axon_prod\test_db.sqlite3'

# Set up Django environment
sys.path.append(r"c:\Users\kille\OneDrive\Рабочий стол\Axon_prod\axon_prod\backend")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.hotel_info.models import RoomPricing

print("=== ROOM PRICING IN DATABASE ===")
for p in RoomPricing.objects.all():
    print(f"ID: {p.id} | Category: {p.kategoria_nomera} | Guests: {p.kolichestvo_chelovek} | Standard: {p.standartny_tarif} | Breakfast: {p.s_zavtrakom} | Half Board: {p.polupansion} | Full Board: {p.polny_pansion} | Validity: {p.deystvitelno_s} to {p.deystvitelno_do}")
