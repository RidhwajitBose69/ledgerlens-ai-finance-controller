import io
import pandas as pd
from typing import Optional, Dict, Any
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from backend.app.db.mongo import db_container

router = APIRouter(prefix="/data", tags=["Data Import & Export"])

@router.post("/upload", response_model=Dict[str, Any])
async def upload_csv_file(
    data_type: str = Form(..., description="transactions, settlements, or bank_transactions"),
    file: UploadFile = File(...)
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    content = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {str(e)}")

    records = df.to_dict(orient="records")
    if not records:
        return {"status": "success", "imported": 0, "message": "CSV file was empty"}

    # Dynamic column mapping & normalization
    normalized_records = []
    for r in records:
        cleaned = {str(k).strip().lower(): v for k, v in r.items()}

        if data_type == "transactions":
            amount_val = cleaned.get("amount", cleaned.get("gross_amount", 0))
            amount_paise = int(round(float(amount_val) * 100)) if isinstance(amount_val, (int, float, str)) and str(amount_val).replace('.','',1).isdigit() else 0
            rec = {
                "transaction_id": str(cleaned.get("transaction_id", cleaned.get("tx_id", ""))),
                "payment_id": str(cleaned.get("payment_id", cleaned.get("pay_id", ""))),
                "reference_id": str(cleaned.get("reference_id", cleaned.get("ref_id", ""))),
                "order_id": str(cleaned.get("order_id", "")),
                "customer_id": str(cleaned.get("customer_id", "")),
                "amount": amount_paise,
                "recorded_fee": int(round(float(cleaned.get("recorded_fee", 0)) * 100)),
                "recorded_tax": int(round(float(cleaned.get("recorded_tax", 0)) * 100)),
                "expected_settlement": int(round(float(cleaned.get("expected_settlement", amount_val)) * 100)),
                "currency": str(cleaned.get("currency", "INR")).upper(),
                "payment_method": str(cleaned.get("payment_method", "card")).lower(),
                "status": str(cleaned.get("status", "captured")).lower(),
                "transaction_date": str(cleaned.get("transaction_date", cleaned.get("date", "")))
            }
            normalized_records.append(rec)
            await db_container.db.transactions.update_one({"transaction_id": rec["transaction_id"]}, {"$set": rec}, upsert=True)

        elif data_type == "settlements":
            s_amt = cleaned.get("settlement_amount", cleaned.get("amount", 0))
            net_amt = cleaned.get("net_amount", s_amt)
            rec = {
                "settlement_id": str(cleaned.get("settlement_id", "")),
                "payment_id": str(cleaned.get("payment_id", "")),
                "reference_id": str(cleaned.get("reference_id", "")),
                "settlement_amount": int(round(float(s_amt) * 100)),
                "fee": int(round(float(cleaned.get("fee", 0)) * 100)),
                "tax": int(round(float(cleaned.get("tax", 0)) * 100)),
                "net_amount": int(round(float(net_amt) * 100)),
                "settlement_status": str(cleaned.get("settlement_status", "processed")),
                "utr": str(cleaned.get("utr", "")),
                "settlement_date": str(cleaned.get("settlement_date", ""))
            }
            normalized_records.append(rec)
            await db_container.db.settlements.update_one({"settlement_id": rec["settlement_id"]}, {"$set": rec}, upsert=True)

        elif data_type == "bank_transactions":
            rec = {
                "bank_transaction_id": str(cleaned.get("bank_transaction_id", "")),
                "reference_id": str(cleaned.get("reference_id", "")),
                "utr": str(cleaned.get("utr", "")),
                "amount": int(round(float(cleaned.get("amount", 0)) * 100)),
                "transaction_date": str(cleaned.get("transaction_date", "")),
                "description": str(cleaned.get("description", ""))
            }
            normalized_records.append(rec)
            await db_container.db.bank_transactions.update_one({"bank_transaction_id": rec["bank_transaction_id"]}, {"$set": rec}, upsert=True)

    return {
        "status": "success",
        "data_type": data_type,
        "imported_records_count": len(normalized_records),
        "filename": file.filename
    }

@router.get("/export")
async def export_csv(
    export_type: str = "exceptions", # exceptions or results
    run_id: Optional[str] = None
):
    query: Dict[str, Any] = {}
    if run_id:
        query["run_id"] = run_id

    if export_type == "exceptions":
        cursor = db_container.db.exceptions.find(query, {"_id": 0})
        docs = await cursor.to_list(length=10000)
        df = pd.DataFrame(docs)
        if not df.empty and "financial_impact_paise" in df.columns:
            df["financial_impact_inr"] = df["financial_impact_paise"] / 100.0
    else:
        cursor = db_container.db.reconciliation_results.find(query, {"_id": 0})
        docs = await cursor.to_list(length=10000)
        df = pd.DataFrame(docs)

    output = io.StringIO()
    df.to_csv(output, index=False)
    output.seek(0)

    filename = f"ledgerlens_{export_type}_{run_id or 'all'}.csv"
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
