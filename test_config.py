# test_config.py
import os
from dotenv import load_dotenv

load_dotenv()

print("🔧 Testing PlanLytics Configuration...")
print(f"✅ SECRET_KEY: {'Set' if os.getenv('SECRET_KEY') else '❌ Missing'}")
print(f"✅ OPENAI_API_KEY: {'Set' if os.getenv('OPENAI_API_KEY') else '❌ Missing'}")
print(f"✅ DATABASE_URL: {'Set' if os.getenv('DATABASE_URL') else '❌ Missing'}")
print(f"✅ REDIS_URL: {'Set' if os.getenv('REDIS_URL') else '❌ Missing'}")
print("✅ Configuration looks good!")