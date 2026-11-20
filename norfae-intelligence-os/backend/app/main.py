from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.authorization import get_business_context
from app.core.dependencies import get_current_user
from app.core.middleware import logging_middleware
from app.events.event_listeners import register_event_listeners
from app.routers import *
from app.routers.auth import router as auth_router
from app.routers.businesses import router as businesses_router
from app.routers.categories import router as categories_router
from app.routers.inventory import router as inventory_router
from app.routers.order_items import router as order_items_router
from app.routers.settings import router as settings_router
from app.routers.intelligence import router as intelligence_router
from app.routers.assistant import router as assistant_router, assistant_business_context
from app.websocket.websocket_routes import router as websocket_router

from app.models import *
from app.models.product_match_memory_model import ProductMatchMemory


app = FastAPI(title="Norfae Intelligence OS", version="1.0.0")
app.middleware("http")(logging_middleware)

# This API uses bearer headers rather than cookies; wildcard origins do not need
# credentialed CORS access.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_event_listeners()

app.include_router(auth_router)
app.include_router(businesses_router)
app.include_router(settings_router)
app.include_router(system_router, dependencies=[Depends(get_current_user)])


def _include_tenant_router(router) -> None:
    app.include_router(router, dependencies=[Depends(get_business_context)])


# Legacy route paths stay stable. Their requests now require a verified business
# context, while TenantSession adds fail-closed ORM scoping for tenant models.
for _router in (
    creatives_router,
    dashboard_router,
    discord_router,
    expenses_router,
    meta_ads_router,
    orders_router,
    products_router,
    product_intelligence_router,
    inventory_router,
    reports_router,
    city_intelligence_router,
    shopify_router,
    analytics_router,
    order_items_router,
    categories_router,
    intelligence_router,
):
    _include_tenant_router(_router)

app.include_router(assistant_router, dependencies=[Depends(assistant_business_context)])

app.include_router(websocket_router)


@app.get("/")
def root():
    return {"message": "Norfae Intelligence OS Backend Running"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}
