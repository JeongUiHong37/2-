import sqlite3
import pandas as pd
import os
from typing import List, Dict, Any

class DatabaseService:
    def __init__(self, db_path: str = "quality_analysis.db"):
        self.db_path = db_path
        
    def init_database(self):
        """Initialize database with table schemas"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Create TB_SUM_MQS_QMHT200 (품질부적합통합실적)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS TB_SUM_MQS_QMHT200 (
                    DAY_CD TEXT,
                    TR_F_PRODQUANTITY INTEGER,
                    QLY_INC_HPW INTEGER,
                    ITEM_TYPE_GROUP_NAME TEXT,
                    EX_A_MAST_GD_CAU_NM TEXT,
                    END_USER_NAME TEXT,
                    QLY_INC_HPN_FAC_TP_NM TEXT,
                    QLY_INC_RESP_FAC_TP_NM TEXT,
                    SPECIFICATION_CD_N TEXT
                )
            """)
            
            # Create TB_S95_SALS_CLAM030 (클레임제기보상)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS TB_S95_SALS_CLAM030 (
                    END_USER_NAME TEXT,
                    RMA_QTY INTEGER,
                    ITEM_TYPE_GROUP_NAME TEXT,
                    EXPECTED_RESOLUTION_DATE TEXT
                )
            """)
            
            # Create TB_S95_A_GALA_SALESPROD (매출실적분석제품)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS TB_S95_A_GALA_SALESPROD (
                    END_USER_NAME TEXT,
                    ITEM_TYPE_GROUP_NAME TEXT,
                    SALE_QTY INTEGER,
                    SALES_DATE TEXT
                )
            """)
            
            conn.commit()
            print("Database tables created successfully")
            
        except Exception as e:
            print(f"Error creating database tables: {e}")
            raise
        finally:
            conn.close()
    
    def is_database_empty(self) -> bool:
        """Check if database tables are empty"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT COUNT(*) FROM TB_SUM_MQS_QMHT200")
            count = cursor.fetchone()[0]
            return count == 0
        except:
            return True
        finally:
            conn.close()
    
    def load_csv_data(self):
        """Load data from CSV files into database"""
        # Load TB_SUM_MQS_QMHT200
        csv_files = {
            'TB_SUM_MQS_QMHT200': 'attached_assets/TB_SUM_MQS_QMHT200_1749701517202.csv',
            'TB_S95_SALS_CLAM030': 'attached_assets/TB_S95_SALS_CLAM030_1749701517203.csv',
            'TB_S95_A_GALA_SALESPROD': 'attached_assets/TB_S95_A_GALA_SALESPROD_1749701517204.csv'
        }
        
        conn = sqlite3.connect(self.db_path)
        
        try:
            for table_name, csv_path in csv_files.items():
                if os.path.exists(csv_path):
                    print(f"Loading {csv_path} into {table_name}")
                    df = pd.read_csv(csv_path, encoding='utf-8')
                    
                    # Clean column names and data
                    df.columns = df.columns.str.strip()
                    
                    # Handle missing values
                    df = df.fillna('')
                    
                    # Convert numeric columns
                    if table_name == 'TB_SUM_MQS_QMHT200':
                        df['TR_F_PRODQUANTITY'] = pd.to_numeric(df['TR_F_PRODQUANTITY'], errors='coerce').fillna(0).astype(int)
                        df['QLY_INC_HPW'] = pd.to_numeric(df['QLY_INC_HPW'], errors='coerce').fillna(0).astype(int)
                    elif table_name == 'TB_S95_SALS_CLAM030':
                        df['RMA_QTY'] = pd.to_numeric(df['RMA_QTY'], errors='coerce').fillna(0).astype(int)
                    elif table_name == 'TB_S95_A_GALA_SALESPROD':
                        df['SALE_QTY'] = pd.to_numeric(df['SALE_QTY'], errors='coerce').fillna(0).astype(int)
                    
                    # Insert data
                    df.to_sql(table_name, conn, if_exists='replace', index=False)
                    print(f"Loaded {len(df)} records into {table_name}")
                else:
                    print(f"CSV file not found: {csv_path}")
                    
        except Exception as e:
            print(f"Error loading CSV data: {e}")
            raise
        finally:
            conn.close()
    
    def execute_query(self, query: str) -> pd.DataFrame:
        """Execute SQL query and return results as DataFrame"""
        conn = sqlite3.connect(self.db_path)
        
        try:
            df = pd.read_sql_query(query, conn)
            return df
        except Exception as e:
            print(f"Error executing query: {e}")
            print(f"Query: {query}")
            raise
        finally:
            conn.close()
    
    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """Get table schema information"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            row_count = cursor.fetchone()[0]
            
            return {
                "table_name": table_name,
                "columns": [{"name": col[1], "type": col[2]} for col in columns],
                "row_count": row_count
            }
        except Exception as e:
            print(f"Error getting table info: {e}")
            raise
        finally:
            conn.close()
    
    def get_sample_data(self, table_name: str, limit: int = 5) -> pd.DataFrame:
        """Get sample data from table"""
        query = f"SELECT * FROM {table_name} LIMIT {limit}"
        return self.execute_query(query)
