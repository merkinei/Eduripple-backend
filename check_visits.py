import sqlite3
import os

VISITORS_DB = os.path.join(".", "visitors.db")

conn = sqlite3.connect(VISITORS_DB)
cursor = conn.cursor()

# Get total visits
cursor.execute("SELECT COUNT(*) FROM page_visits")
total_visits = cursor.fetchone()[0]

print(f"Total visits recorded: {total_visits}")

if total_visits > 0:
    print("\nLast 15 visits:")
    print("-" * 110)
    cursor.execute('''
        SELECT timestamp, path, ip_address, user_agent, country, status_code 
        FROM page_visits 
        ORDER BY timestamp DESC 
        LIMIT 15
    ''')
    
    for row in cursor.fetchall():
        timestamp, path, ip, user_agent, country, status = row
        user_agent_short = (user_agent[:40] + "...") if user_agent and len(user_agent) > 40 else user_agent or "N/A"
        country_display = country or "N/A"
        print(f"Time: {timestamp[:19]:<20} Path: {path:<20} IP: {ip:<15} Status: {status}")
        print(f"  UA: {user_agent_short}")
        print(f"  Country: {country_display}\n")
else:
    print("No visits recorded yet. The site has not been visited since analytics was set up.")

conn.close()
