import os
import pyodbc
from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv

# Load credentials from the .env file
load_dotenv()
BPCS_DSN = os.getenv("BPCS_DSN")
BPCS_USER = os.getenv("BPCS_USER")
BPCS_PASS = os.getenv("BPCS_PASS")

# Validate if credentials exist
if not all([BPCS_DSN, BPCS_USER, BPCS_PASS]):
    raise ValueError("CRITICAL ERROR: Database credentials missing in the .env file.")

# Initialize the API
app = FastAPI(title="Makita BPCS Integration API")

# Final SQL Query
SQL_QUERY = """
SELECT 
    H.HORD AS QuoteNumber, L.LLINE AS QuoteLineNumber, H.HCPO AS CustomerPONumber,
    H.HCUST AS CustomerNumber, C.CNME AS CustomerName, H.HSHIP AS ShipToNumber,
    S.TNAME AS ShipToName, L.LPROD AS ItemNumber, I.IDESC AS ItemDescription,
    L.LQORD AS OrderedQuantity, H.HSDTE AS ScheduleDate, H.HRDTE AS RequestDate,
    C.CDISC AS StandardDiscount, I.IDISC AS ItemDiscountCode, 
    P5.P05PRCD AS PriceAgreementCode, P3.P03PRC1 AS NetPriceTier1
FROM BPNLCMF02.EQH H
INNER JOIN BPNLCMF02.EQL L ON H.HORD = L.LORD AND L.LID = 'QL'
LEFT JOIN BPNLCMF02.RCM C ON H.HCUST = C.CCUST
LEFT JOIN BPNLCMF02.EST S ON H.HCUST = S.TCUST AND H.HSHIP = S.TSHIP
LEFT JOIN BPNLCMF02.IIM I ON L.LPROD = I.IPROD
LEFT JOIN BUNLCMF02.PRO05P P5 ON H.HCUST = P5.P05CUST
LEFT JOIN BUNLCMF02.PRO03P P3 ON P5.P05PRCD = P3.P03PCDE AND L.LPROD = P3.P03PROD
WHERE H.HORD = ?
ORDER BY L.LLINE ASC
"""

@app.get("/api/v1/orders/{quote_number}")
def get_order_details(quote_number: int):
    try:
        # Define connection string using DSN
        conn_str = f"DSN={BPCS_DSN};UID={BPCS_USER};PWD={BPCS_PASS};"
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        # Execute query and fetch data
        cursor.execute(SQL_QUERY, quote_number)
        columns = [column[0] for column in cursor.description]
        rows = cursor.fetchall()
        
        conn.close()
        
        # Return 404 if no data is found
        if not rows:
            raise HTTPException(status_code=404, detail="Quote not found in BPCS")

        # Transform data into the exact JSON format required by Excel
        json_result = []
        for row in rows:
            # Força as colunas que vieram do banco a ficarem em CAIXA ALTA para evitar erros do driver
            db_item = dict(zip([c.upper() for c in columns], row))
            
            # Constrói o objeto JSON final com os nomes exatos que o Excel espera
            item = {
                "QuoteNumber": db_item.get("QUOTENUMBER"),
                "QuoteLineNumber": db_item.get("QUOTELINENUMBER"),
                "CustomerPONumber": db_item.get("CUSTOMERPONUMBER", ""),
                "CustomerNumber": db_item.get("CUSTOMERNUMBER"),
                "CustomerName": db_item.get("CUSTOMERNAME", "").strip() if db_item.get("CUSTOMERNAME") else "",
                "ShipToNumber": db_item.get("SHIPTONUMBER"),
                "ShipToName": db_item.get("SHIPTONAME", "").strip() if db_item.get("SHIPTONAME") else "",
                "ItemNumber": db_item.get("ITEMNUMBER", "").strip() if db_item.get("ITEMNUMBER") else "",
                "ItemDescription": db_item.get("ITEMDESCRIPTION", "").strip() if db_item.get("ITEMDESCRIPTION") else "",
                "OrderedQuantity": float(db_item.get("ORDEREDQUANTITY", 0)) if db_item.get("ORDEREDQUANTITY") else 0,
                "ScheduleDate": db_item.get("SCHEDULEDATE"),
                "RequestDate": db_item.get("REQUESTDATE"),
                "StandardDiscount": float(db_item.get("STANDARDDISCOUNT", 0)) if db_item.get("STANDARDDISCOUNT") else 0,
                "ItemDiscountCode": db_item.get("ITEMDISCOUNTCODE", "").strip() if db_item.get("ITEMDISCOUNTCODE") else "",
                "PriceAgreementCode": db_item.get("PRICEAGREEMENTCODE", "").strip() if db_item.get("PRICEAGREEMENTCODE") else "",
                "NetPriceTier1": float(db_item.get("NETPRICETIER1", 0)) if db_item.get("NETPRICETIER1") else None
            }
            
            json_result.append(item)
            
        return json_result

    except Exception as e:
        # Return 500 Internal Server Error for any other exceptions
        raise HTTPException(status_code=500, detail=str(e))