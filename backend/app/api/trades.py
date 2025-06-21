from fastapi import APIRouter, UploadFile, File, HTTPException, Request
import pandas as pd
import asyncio
import re

router = APIRouter()

# @router.get("/test")
# async def testing():
#     return {"Message":"Endpoint is Active"}

@router.post("/upload")
async def import_csv(trades_csv: UploadFile = File(...)):
    
    # Validating File
    await file_validation(trades_csv)
    # Once file validation is complete, parse csv
    df = await parse_trades_csv(trades_csv)
    # One CSV is parsed, data processing can be begin
    await process_df(df)
    
    
async def parse_trades_csv(trades_csv: UploadFile = File(...)):
    # Move fiel reader back to beginning of file
    trades_csv.file.seek(0)
    
    expected_columns = ["DATE","TIME","TYPE", "DESCRIPTION", "Misc Fees", "Commissions & Fees", "AMOUNT", "BALANCE"] 
    try:
        df = await asyncio.to_thread (
            lambda: pd.read_csv( 
            trades_csv.file,
            on_bad_lines='skip',
            header=2,
            usecols=expected_columns,
            engine="python",
            ).loc[lambda df: df["TYPE"] == "TRD"]
        )
    except (pd.errors.ParserError, ValueError) as e:
        raise HTTPException(400, f"Error during file parsing: {e}") 
    return df
        
async def file_validation(trades_csv: UploadFile = File(...)):
    # Doing basic checks on file
    # 1. File not uploaded
    # 2. File not .csv
    # 3. File structure does not match that of thinkorswim
    
    if trades_csv is None:
        raise HTTPException(400, "No file uploaded")
    filename: str = trades_csv.filename or ""
    if not filename.lower().endswith(".csv"):
        raise HTTPException(400, "Not a .csv file")
    
    # Moving file reader to beginning to read csv file header
    # If header doesn't contain proper columns, will not parse file
    trades_csv.file.seek(0)
    expected_columns = ["DATE","TIME","TYPE", "DESCRIPTION", "Misc Fees", "Commissions & Fees", "AMOUNT", "BALANCE"] 
    try:
        df_header = await asyncio.to_thread(
            pd.read_csv, 
            trades_csv.file,
            on_bad_lines='skip',
            nrows=0,
            header=2,
            usecols=expected_columns,
            engine="python")
    except (pd.errors.ParserError, ValueError) as e:
        raise HTTPException(400, f"Error during file valdiation: {e}") 
    
async def process_df(df: pd.DataFrame):
    options_pattern = re.compile(
    r'(?P<action>BOT|SOLD)\s+'                   # buy or sell
    r'(?P<quantity>[+-]?\d+)\s+'                 # +1, -2, etc.
    r'(?P<symbol>[A-Z]+)\s+'                     # underlying ticker
    r'(?P<multiplier>\d+)\s*'                    # usually 100
    r'(?:\((?P<series>[^)]+)\)\s+)?'             # optional (Weekly, Monthly) etc
    r'(?P<day>\d{1,2})\s+'                       # expiration day
    r'(?P<month>[A-Z]{3})\s+'                    # expiration month, e.g. MAR
    r'(?P<year>\d{2})\s+'                        # expiration year, e.g. 25
    r'(?P<strike>\d+(?:\.\d+)?)\s+'              # strike price
    r'(?P<right>CALL|PUT)\s+'                    # CALL or PUT
    r'@(?P<premium>[\d\.]+)'                      # @.29, @1.05, etc.
    r'(?:\s+(?P<exchange>[A-Z]+))?'              # Exchange Code, e.g. CBOE, NASDAQ
)