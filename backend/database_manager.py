import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor, execute_values
import streamlit as st

class DatabaseManager:
    """
    Handles all database interactions using a connection pool.
    Automatically switches between local Fedora and Neon Cloud.
    """
    _connection_pool = None

    @staticmethod
    def initialize_pool():
        """Initialize the connection pool with health check settings"""
        if DatabaseManager._connection_pool is None:
            try:
                # 1. Try to get the Neon URL from Streamlit Secrets (Cloud/Local Test)
                if "connections" in st.secrets:
                    db_url = st.secrets["connections"]["postgresql"]["url"]
                    DatabaseManager._connection_pool = psycopg2.pool.SimpleConnectionPool(
                        1, 20,
                        dsn=db_url,
                        # CRITICAL: Add these settings for NEON stability
                        keepalives=1,
                        keepalives_idle=30,
                        keepalives_interval=10,
                        keepalives_count=5,
                        connect_timeout=10
                    )
                    print(" Connected to NEON Cloud Pool.")
                
                # 2. Fallback to your local Fedora Postgres
                else:
                    DatabaseManager._connection_pool = psycopg2.pool.SimpleConnectionPool(
                        1, 20,
                        user="kenza",
                        password="kenza123",
                        host="localhost",
                        port="5432",
                        database="exam_sch",
                        keepalives=1,
                        keepalives_idle=30,
                        keepalives_interval=10,
                        keepalives_count=5
                    )
                    print(" Connected to LOCAL Fedora Pool.")
            except Exception as e:
                print(f" Error creating connection pool: {e}")
                raise

    def __init__(self):
        """Initialize pool when DatabaseManager is instantiated"""
        DatabaseManager.initialize_pool()

    @staticmethod
    def _get_connection():
        """Get a connection from pool with health check"""
        if DatabaseManager._connection_pool is None:
            DatabaseManager.initialize_pool()
        
        conn = DatabaseManager._connection_pool.getconn()
        
        # Health check: test if connection is alive
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            return conn
        except Exception:
            # Connection is dead, close it and get a new one
            try:
                DatabaseManager._connection_pool.putconn(conn, close=True)
            except:
                pass
            # Get a fresh connection
            return DatabaseManager._connection_pool.getconn()

    def execute_query(self, query, params=None, fetch=True):
        """
        Execute a database query with automatic retry on connection failure
        
        Args:
            query: SQL query string
            params: Query parameters (tuple)
            fetch: Whether to fetch results (default True)
        
        Returns:
            Query results if fetch=True, True if fetch=False, None on error
        """
        max_retries = 2
        retry_count = 0
        
        while retry_count <= max_retries:
            conn = None
            try:
                conn = DatabaseManager._get_connection()
                
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(query, params)
                    
                    if fetch:
                        result = cursor.fetchall()
                        conn.commit()
                        return result
                    else:
                        conn.commit()
                        return True
                        
            except Exception as e:
                # Try to rollback, but don't fail if connection is already closed
                if conn:
                    try:
                        conn.rollback()
                    except:
                        pass
                
                # Check if it's a connection error and we can retry
                error_msg = str(e).lower()
                if retry_count < max_retries and any(term in error_msg for term in 
                    ['ssl', 'connection', 'closed', 'server closed', 'timeout', 'unexpectedly']):
                    retry_count += 1
                    print(f" Connection error, retrying ({retry_count}/{max_retries})...")
                    
                    # Close bad connection
                    if conn:
                        try:
                            DatabaseManager._connection_pool.putconn(conn, close=True)
                            conn = None
                        except:
                            pass
                    
                    # Force reconnect by clearing pool
                    try:
                        DatabaseManager._connection_pool.closeall()
                        DatabaseManager._connection_pool = None
                        DatabaseManager.initialize_pool()
                    except:
                        pass
                    
                    continue  # Retry the query
                else:
                    print(f" Query Error: {e}")
                    return None
                    
            finally:
                if conn:
                    try:
                        DatabaseManager._connection_pool.putconn(conn)
                    except:
                        pass
        
        return None

    def execute_batch(self, query, params_list):
        """Execute batch insert with retry logic"""
        max_retries = 2
        retry_count = 0
        
        while retry_count <= max_retries:
            conn = None
            try:
                conn = DatabaseManager._get_connection()
                
                with conn.cursor() as cursor:
                    execute_values(cursor, query, params_list)
                    conn.commit()
                    return True
                    
            except Exception as e:
                if conn:
                    try:
                        conn.rollback()
                    except:
                        pass
                
                error_msg = str(e).lower()
                if retry_count < max_retries and any(term in error_msg for term in 
                    ['ssl', 'connection', 'closed', 'server closed', 'timeout']):
                    retry_count += 1
                    print(f"  Connection error in batch, retrying ({retry_count}/{max_retries})...")
                    
                    if conn:
                        try:
                            DatabaseManager._connection_pool.putconn(conn, close=True)
                            conn = None
                        except:
                            pass
                    
                    try:
                        DatabaseManager._connection_pool.closeall()
                        DatabaseManager._connection_pool = None
                        DatabaseManager.initialize_pool()
                    except:
                        pass
                    
                    continue
                else:
                    print(f" Batch Insert Error: {e}")
                    return False
                    
            finally:
                if conn:
                    try:
                        DatabaseManager._connection_pool.putconn(conn)
                    except:
                        pass
        
        return False

    def close_all_connections(self):
        """Close all connections in the pool"""
        if DatabaseManager._connection_pool:
            try:
                DatabaseManager._connection_pool.closeall()
                print(" Database connections closed.")
            except Exception as e:
                print(f" Error closing connections: {e}")