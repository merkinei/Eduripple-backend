import sqlite3

conn = sqlite3.connect('curriculum.db')
cursor = conn.cursor()

# Check if visitor_visits table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='visitor_visits'")
table_exists = cursor.fetchone()

if table_exists:
    cursor.execute('SELECT COUNT(*) FROM visitor_visits')
    total_visits = cursor.fetchone()[0]
    print(f'Total visits: {total_visits}')
    
    if total_visits > 0:
        cursor.execute('SELECT visit_id, page_path, visitor_country, visit_timestamp FROM visitor_visits ORDER BY visit_timestamp DESC LIMIT 10')
        print('\nLast 10 visits:')
        print('-' * 100)
        for row in cursor.fetchall():
            print(f'ID: {row[0]:<8} Page: {row[1]:<25} Country: {row[2]:<15} Time: {row[3]}')
    else:
        print('No visits recorded yet.')
else:
    print('visitor_visits table not found in database')

conn.close()
