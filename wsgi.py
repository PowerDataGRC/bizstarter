import subprocess
from main import app

# Run database migrations
# Using subprocess to ensure it runs in a separate process
# before the app starts serving requests.
try:
    subprocess.run(["flask", "db", "upgrade"], check=True)
except subprocess.CalledProcessError as e:
    print(f"Database migration failed: {e}")
    # Depending on the desired behavior, you might want to exit here
    # import sys
    # sys.exit(1)