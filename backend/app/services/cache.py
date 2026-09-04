import json
import redis.asyncio as redis
from typing import Dict, Any
import os

# Initialize Redis client (typically configured centrally).
redis_client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))

async def get_revenue_summary(property_id: str, tenant_id: str) -> Dict[str, Any]:
    """
    Fetches revenue summary, utilizing caching to improve performance.
    """
    # ================================================================
    # BUG - cache key missing tenant_id (Client B's privacy complaint)
    # ================================================================
    # OLD (BUGGY) CODE:
    #   cache_key = f"revenue:{property_id}"
    #
    # EVIDENCE THAT CONFIRMED THIS (from the debug prints added below,
    # captured live in the backend logs, two consecutive requests):
    #   DEBUG CACHE: key=revenue:prop-001 (tenant_id=tenant-a is NOT part of this key)
    #   DEBUG CACHE: HIT for revenue:prop-001          <- sunset (tenant-a) caches it first
    #   ...
    #   DEBUG CACHE: key=revenue:prop-001 (tenant_id=tenant-b is NOT part of this key)
    #   DEBUG CACHE: HIT for revenue:prop-001          <- ocean (tenant-b) gets a HIT on the SAME key
    #
    # ROOT CAUSE: property IDs (prop-001, prop-002, ...) are not globally
    # unique to one tenant, so two different tenants requesting the "same"
    # property_id read and wrote the exact same Redis key. Whichever
    # tenant's request populated the cache first had their revenue data
    # served to every OTHER tenant for the next 5 minutes (the cache TTL).
    # This is Client B's exact complaint: "sometimes when we refresh, we
    # see revenue numbers that look like they belong to another company."
    #
    # FIX: include tenant_id in the cache key, so each tenant is scoped to
    # their own cache entry and can never read another tenant's cached data.
    cache_key = f"revenue:{tenant_id}:{property_id}"
    print(f"DEBUG CACHE: key={cache_key}")

    # Try to get from cache
    cached = await redis_client.get(cache_key)
    print(f"DEBUG CACHE: {'HIT' if cached else 'MISS'} for {cache_key}")
    if cached:
        return json.loads(cached)
    
    # Revenue calculation is delegated to the reservation service.
    from app.services.reservations import calculate_total_revenue
    
    # Calculate revenue
    result = await calculate_total_revenue(property_id, tenant_id)
    
    # Cache the result for 5 minutes
    await redis_client.setex(cache_key, 300, json.dumps(result))
    
    return result
