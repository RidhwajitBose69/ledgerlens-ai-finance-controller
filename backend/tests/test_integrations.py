import pytest
from backend.app.adapters.razorpay import RazorpayAdapter

@pytest.mark.asyncio
async def test_razorpay_mock_adapter_sync():
    adapter = RazorpayAdapter()
    result = await adapter.sync_razorpay_settlements()
    assert result["status"] == "success"
    assert result["mode"] in ["MOCK_GATEWAY", "LIVE_API"]
    assert "synced_settlements_count" in result
