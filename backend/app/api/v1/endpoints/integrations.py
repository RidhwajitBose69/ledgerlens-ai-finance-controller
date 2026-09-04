from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Request, Header
from backend.app.adapters.razorpay import RazorpayAdapter

router = APIRouter(prefix="/integrations", tags=["Payment Gateway Integrations"])
razorpay_adapter = RazorpayAdapter()

@router.post("/razorpay/sync", response_model=Dict[str, Any])
async def sync_razorpay_data():
    try:
        result = await razorpay_adapter.sync_razorpay_settlements()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/razorpay/webhook")
async def razorpay_webhook_listener(request: Request, x_razorpay_signature: str = Header(None)):
    body = await request.body()
    # Log webhook event for audit trail
    return {"status": "event_received"}
