import os
import psycopg2
from dotenv import load_dotenv

def test_connection():
    """
    Tests the database connection using the URL from the .env file.
    """
    # Load environment variables from the correct file
    # You might need to run 'pip install python-dotenv'
    load_dotenv('.env.development.local')

    # Get the unpooled database URL
    db_url = os.environ.get('DATABASE_URL_UNPOOLED')

    if not db_url:
        print("ERROR: DATABASE_URL_UNPOOLED not found in .env.development.local")
        return

    print(f"Attempting to connect to the database...")
    try:
        # Attempt to connect with a 15-second timeout
        conn = psycopg2.connect(db_url, connect_timeout=15)
        print("\n✅ Connection Successful!")
        conn.close()
    except psycopg2.OperationalError as e:
        print("\n❌ CONNECTION FAILED: An OperationalError occurred.")
        print("This strongly suggests a network issue (like a firewall) or a problem with the database endpoint itself.")
        print(f"\nDetails: {e}")

if __name__ == "__main__":
    test_connection()