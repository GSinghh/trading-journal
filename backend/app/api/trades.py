from fastapi import APIRouter, UploadFile, File, HTTPException, Request
import pandas as pd
import asyncio
import re
import time

router = APIRouter()

overall_profit_loss = 0

EXPECTED_COLUMNS = ["DATE","TIME","TYPE", "DESCRIPTION", "Misc Fees", "Commissions & Fees", "AMOUNT", "BALANCE"] 

OPTIONS_PATTERN = re.compile (
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

@router.post("/upload")
async def import_csv(trades_csv: UploadFile = File(...)):
    
    # Validating File
    await file_validation(trades_csv)
    # Once file validation is complete, parse csv
    df = await parse_trades_csv(trades_csv)
    # One CSV is parsed, data processing can be begin
    await extract_from_csv(df)
    return {"Message": "File Uploaded Succesfully"}

@router.post("/check-upload-times")
async def handle_csv_import(trades_csv: UploadFile = File(...)):
    total_start = time.perf_counter()

    # 1. File validation
    step_start = time.perf_counter()
    await file_validation(trades_csv)
    print(f"file_validation took {time.perf_counter() - step_start:.3f}s")

    # 2. CSV parsing
    step_start = time.perf_counter()
    df = await parse_trades_csv(trades_csv)
    print(f"parse_trades_csv took {time.perf_counter() - step_start:.3f}s")

    # 3. Data extraction & stats
    step_start = time.perf_counter()
    await extract_from_csv(df)
    print(f"extract_from_csv took {time.perf_counter() - step_start:.3f}s")

    # Total time
    total_elapsed = time.perf_counter() - total_start
    print(f"Total /upload time: {total_elapsed:.3f}s")
    
    
async def parse_trades_csv(trades_csv: UploadFile = File(...)):    
    try:
        df = await asyncio.to_thread (
            lambda: pd.read_csv( 
            trades_csv.file,
            on_bad_lines='skip',
            header=2,
            usecols=EXPECTED_COLUMNS,
            engine="c",
            ).loc[lambda df: df["TYPE"] == "TRD"]
        )
    except (pd.errors.ParserError, ValueError) as e:
        raise HTTPException(400, f"Error during file parsing: {e}") 
    finally:
        trades_csv.file.seek(0)
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
    try:
        df_header = await asyncio.to_thread(
            pd.read_csv, 
            trades_csv.file,
            on_bad_lines='skip',
            nrows=0,
            header=2,
            usecols=EXPECTED_COLUMNS,
            engine="c")
    except (pd.errors.ParserError, ValueError) as e:
        raise HTTPException(400, f"Error during file valdiation: {e}")
    finally:
        trades_csv.file.seek(0)
                           
async def extract_from_csv(filtered_trades: pd.DataFrame):
    all_trades = {}
    for idx, row in filtered_trades.iterrows():
        execution_date = row["DATE"]
        execution_time = row["TIME"]
        description = row["DESCRIPTION"]
        commission = abs(float(row["Misc Fees"])) + abs(float(row["Commissions & Fees"]))
        cost = float(row["AMOUNT"])
        contract_info = OPTIONS_PATTERN.match(description) # Extract information related to option contract
        if not contract_info:
            continue 
    
        trade_info = {
            "Action": contract_info["action"],
            "Name": f"{contract_info['symbol']} {contract_info['strike']} {contract_info['right']}",
            "Expiration": f"{contract_info['day']} {contract_info['month']} {contract_info['year']}",
            "Date": execution_date,
            "Time": execution_time,
            "Cost": cost,
            "Premium": float(contract_info['premium']),
            "Quantity": abs(int(contract_info["quantity"])),
            "Exchange": contract_info["exchange"] if contract_info["exchange"] is not None else "",
            "Fees": commission,
            }
        
        key = f"{trade_info['Name']} {trade_info['Expiration']}"
        all_trades.setdefault(key, []).append(trade_info)
    for trades in all_trades:
        calculate_stats(all_trades[trades], trades)

def calculate_stats(trades, key):
    global overall_profit_loss
    current_segment = []
    segments = []
    open_contracts = 0
    
    for trade in trades: 
        quantity = trade['Quantity']
        cost = trade['Cost']  
        fees = trade['Fees']
        premium = trade['Premium']
        action = trade['Action']
        
        if action == "BOT":
            open_contracts += quantity
            current_segment.append(trade)
        else:
            open_contracts -= quantity
            current_segment.append(trade)
        if open_contracts == 0:
            segments.append(current_segment)
            current_segment = []
    
    for seg in segments:
        total_contracts = 0
        open_contracts = 0
        total_fees = 0.0
        total_cost_basis = 0.0
        realized_pnl = 0.0
        avg_contract_price = 0
        total_pnl = 0.0
        win_or_loss = ''
        
        for idx, trade in enumerate(seg):
            quantity = trade['Quantity']
            cost = trade['Cost']  
            fees = trade['Fees']
            premium = trade['Premium']
            action = trade['Action']
            total_fees += fees
            num_trades = len(seg) - 1
            
            if action == 'BOT':
                total_contracts += quantity
                open_contracts += quantity
                avg_contract_price = round(((avg_contract_price * (total_contracts - quantity)) + (quantity * premium)) / total_contracts, 2)
                total_cost_basis += abs(cost)
            else:
                open_contracts -= quantity
                realized_pnl += (premium - avg_contract_price) * 100
            if action != 'BOT':
                pnl = ((premium - avg_contract_price) * 100)
                total_pnl = realized_pnl - total_fees
                overall_profit_loss += total_pnl
                win_or_loss = 'W' if total_pnl > 0 else 'L'
                # print(f"Date: {trade['Date']}\nTime: {trade['Time']}\nPosition: {trade['Action']} {trade['Quantity']} {key}")
                # print(f"Total Contracts: {total_contracts} \nOpen Contracts: {open_contracts} \nAverage Contract Price: {avg_contract_price} \nTotal Cost Basis: {total_cost_basis}")
                # print(f"Win or Loss: {win_or_loss}")
                # print(f"Profit and Loss: {pnl:.2f}\n")
                # if idx == num_trades: print(f"Total PnL: {total_pnl:.2f}\n") 
                
