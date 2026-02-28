import sqlite3

def add_admin_columns():
    db_path = 'app.db'
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("Adding is_admin column...")
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0")
        except sqlite3.OperationalError as e:
            print(f"Notice (is_admin): {e}")

        print("Adding admin_role column...")
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN admin_role VARCHAR(50) DEFAULT 'None'")
        except sqlite3.OperationalError as e:
            print(f"Notice (admin_role): {e}")
            
        print("Adding account_status column...")
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN account_status VARCHAR(20) DEFAULT 'active'")
        except sqlite3.OperationalError as e:
            print(f"Notice (account_status): {e}")

        conn.commit()
        print("Successfully patched 'users' table with Admin Schema.")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    add_admin_columns()
