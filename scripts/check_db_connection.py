#!/usr/bin/env python3
"""
Database connectivity test script
Helps diagnose PostgreSQL connection issues
"""

import os
import sys
import time
import socket
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_network_connectivity(host, port):
    """Test basic network connectivity to host:port"""
    print(f"🌐 Testing network connectivity to {host}:{port}")
    try:
        sock = socket.create_connection((host, port), timeout=10)
        sock.close()
        print("✅ Network connectivity OK")
        return True
    except socket.timeout:
        print("❌ Connection timeout - possible network/VPN issue")
        return False
    except socket.gaierror as e:
        print(f"❌ DNS resolution failed: {e}")
        return False
    except ConnectionRefusedError:
        print("❌ Connection refused - check security groups")
        return False
    except Exception as e:
        print(f"❌ Network error: {e}")
        return False

def test_db_connection():
    """Test PostgreSQL database connection"""
    print("🐘 Testing PostgreSQL connection")
    
    db_params = {
        "host": os.getenv("POSTGRES_HOST", "172.31.85.170"),
        "database": os.getenv("POSTGRES_DB", "applywise"),
        "user": os.getenv("POSTGRES_USER", "postgres"),
        "password": os.getenv("POSTGRES_PASSWORD"),
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "connect_timeout": 10,
    }
    
    print(f"📊 Connection parameters:")
    for key, value in db_params.items():
        if key == 'password':
            print(f"  {key}: {'*' * len(str(value)) if value else 'NOT SET'}")
        else:
            print(f"  {key}: {value}")
    
    if not db_params['password']:
        print("❌ POSTGRES_PASSWORD not set in environment")
        return False
    
    try:
        print("🔗 Attempting database connection...")
        start_time = time.time()
        
        conn = psycopg2.connect(**db_params)
        
        # Test a simple query
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        
        end_time = time.time()
        print(f"✅ Database connection successful!")
        print(f"📊 Connection time: {end_time - start_time:.2f} seconds")
        print(f"🗄️ PostgreSQL version: {version}")
        return True
        
    except psycopg2.OperationalError as e:
        print(f"❌ Database connection failed: {e}")
        
        error_str = str(e).lower()
        if "timeout" in error_str:
            print("\n💡 Troubleshooting timeout issues:")
            print("1. Check if you're connected to VPN")
            print("2. Verify RDS security group allows your IP on port 5432")
            print("3. Check if RDS instance is in a private subnet")
            
        elif "authentication failed" in error_str:
            print("\n💡 Troubleshooting authentication issues:")
            print("1. Verify POSTGRES_PASSWORD is correct")
            print("2. Check if user exists and has proper permissions")
            
        elif "could not connect to server" in error_str:
            print("\n💡 Troubleshooting connection issues:")
            print("1. Check RDS endpoint hostname")
            print("2. Verify RDS instance is running")
            print("3. Check VPC/subnet configuration")
            
        return False
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def get_public_ip():
    """Get your current public IP address"""
    try:
        import requests
        response = requests.get('https://httpbin.org/ip', timeout=5)
        ip = response.json()['origin']
        print(f"🌍 Your public IP: {ip}")
        return ip
    except Exception as e:
        print(f"⚠️ Could not determine public IP: {e}")
        return None

def main():
    """Main diagnostic function"""
    print("🔍 PostgreSQL Connection Diagnostics")
    print("=" * 50)
    
    # Get environment info
    print(f"📁 Working directory: {os.getcwd()}")
    print(f"🐍 Python version: {sys.version}")
    
    # Check if .env file exists
    env_file = ".env"
    if os.path.exists(env_file):
        print(f"✅ Found {env_file}")
    else:
        print(f"⚠️ No {env_file} file found")
    
    print()
    
    # Get public IP
    get_public_ip()
    print()
    
    # Test network connectivity first
    host = os.getenv("POSTGRES_HOST", "172.31.85.170")
    port = int(os.getenv("POSTGRES_PORT", "5432"))
    print(host)
    network_ok = test_network_connectivity(host, port)
    print()
    
    if network_ok:
        # Test database connection
        db_ok = test_db_connection()
    else:
        print("⏭️ Skipping database test due to network connectivity issues")
        db_ok = False
    
    print()
    print("=" * 50)
    
    if network_ok and db_ok:
        print("🎉 All tests passed! Database is accessible.")
    elif network_ok and not db_ok:
        print("⚠️ Network OK but database connection failed.")
        print("   This is likely an authentication or configuration issue.")
    else:
        print("❌ Network connectivity failed.")
        print("   You likely need VPN access or security group changes.")
        
    print()
    print("📋 Next steps:")
    if not network_ok:
        print("1. Set up VPN connection to AWS VPC")
        print("2. Or add your IP to RDS security group")
        print("3. Or use SSH tunnel through bastion host")
    elif not db_ok:
        print("1. Verify database credentials")
        print("2. Check database user permissions")
        print("3. Verify RDS instance is running")

if __name__ == "__main__":
    main() 