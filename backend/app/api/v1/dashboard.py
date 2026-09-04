from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from app.services.cache import get_revenue_summary
from app.core.auth import authenticate_request as get_current_user

router = APIRouter()

@router.get("/dashboard/summary")
async def get_dashboard_summary(
    property_id: str,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    
    tenant_id = getattr(current_user, "tenant_id", "default_tenant") or "default_tenant"

    print(f"DEBUG DASHBOARD: request received - property_id={property_id}, tenant_id={tenant_id}")

    revenue_data = await get_revenue_summary(property_id, tenant_id)

    print(f"DEBUG DASHBOARD: revenue_data returned = {revenue_data}")

    # ================================================================
    # BUG - unrounded sub-cent revenue returned from the API (finance
    # team's "off by a few cents" complaint)
    # ================================================================
    # OLD (BUGGY) CODE:
    #   total_revenue_float = float(revenue_data['total'])
    #
    # EVIDENCE THAT CONFIRMED THIS (real DB query result, captured via the
    # DEBUG RESERVATIONS print in reservations.py):
    #   DEBUG RESERVATIONS: REAL DB QUERY SUCCESS - property_id=prop-001,
    #   tenant_id=tenant-a, total=2250.000, count=4
    #   DEBUG DASHBOARD: revenue_data returned = {'total': '2250.000', ...}
    #
    # ROOT CAUSE: database/schema.sql defines
    #   total_amount NUMERIC(10, 3) NOT NULL, -- storing as numeric with 3
    #   decimals to allow sub-cent precision tracking
    # Revenue is deliberately stored with 3 decimal places, not 2. The old
    # code returned this raw value as-is (e.g. 2250.000, or something like
    # 1234.567 depending on the sum). Only the FRONTEND rounded it to 2
    # decimals for display (see RevenueSummary.tsx's `displayTotal`, and its
    # own "Precision Mismatch Detected" warning that already anticipated
    # exactly this gap). Anyone consuming this API directly - an export, a
    # report, finance cross-referencing numbers - saw a different,
    # un-rounded figure than what the dashboard displayed: not randomly
    # wrong, just inconsistently rounded depending on where you looked.
    #
    # FIX: round once, here at the API boundary, so every consumer of this
    # endpoint sees the same, correct, cent-accurate number.
    total_revenue_float = round(float(revenue_data['total']), 2)

    return {
        "property_id": revenue_data['property_id'],
        "total_revenue": total_revenue_float,
        "currency": revenue_data['currency'],
        "reservations_count": revenue_data['count']
    }
