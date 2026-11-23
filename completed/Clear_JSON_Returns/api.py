
# Lesson 09: the first POST route. Register a customer, with validation.
#
# Run:  python api.py
# Open: http://127.0.0.1:8000

import os
from pathlib import Path
from typing import Literal

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from pymongo import MongoClient, ReturnDocument

HERE = Path(__file__).parent

client = MongoClient(os.getenv("MONGO_URL", "mongodb://localhost:27017"))
db = client[os.getenv("MONGO_DB", "noidx_10k")]

app = FastAPI()


# ---- Standardized response format ----


def format_output(
    *,
    query,
    response_code=200,
    error_response=None,
    data=None,
    total_size=None,
    offset=0,
    limit=None,
):
    """Format API responses consistently."""

    if data is None:
        data = []

    # Number of records returned in this response.
    if isinstance(data, list):
        size = len(data)
    else:
        size = 1

    # Total number of matching records in the database.
    if total_size is None:
        total_size = size

    return {
        "query": query,
        "response_code": response_code,
        "error_response": error_response,
        "data": data,
        "size": size,
        "total_size": total_size,
        "offset": offset,
        "limit": limit,
    }



def get_query(request: Request):
    """Return the path plus any query parameters."""
    query = request.url.path

    if request.url.query:
        query += f"?{request.url.query}"

    return query


# ---- Global error handlers ----

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    body = format_output(
        query=get_query(request),
        response_code=exc.status_code,
        error_response=exc.detail,
        data=[],
        total_size=0,
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=body,
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):
    body = format_output(
        query=get_query(request),
        response_code=422,
        error_response=jsonable_encoder(exc.errors()),
        data=[],
        total_size=0,
    )

    return JSONResponse(
        status_code=422,
        content=body,
    )


# ---- Integer IDs from the counters collection ----

def ensure_counter(name, current_max):
    """Create a counter starting at current_max if it doesn't exist."""
    db.counters.update_one(
        {"_id": name},
        {"$setOnInsert": {"seq": current_max}},
        upsert=True,
    )


def next_id(name, count=1):
    """Reserve count IDs and return the first reserved ID."""
    counter = db.counters.find_one_and_update(
        {"_id": name},
        {"$inc": {"seq": count}},
        return_document=ReturnDocument.AFTER,
    )
    return counter["seq"] - count + 1


# Initialize counters without resetting existing ones.
last_customer = db.customers.find_one(
    {},
    {"_id": 1},
    sort=[("_id", -1)],
)
ensure_counter(
    "customer_id",
    last_customer["_id"] if last_customer else 0,
)

top_card = next(
    db.customers.aggregate([
        {"$unwind": "$cards"},
        {"$group": {"_id": None, "max": {"$max": "$cards.card_id"}}},
    ]),
    None,
)
ensure_counter("card_id", top_card["max"] if top_card else 0)


# ---- Request model ----

class NewCustomer(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    first_name: str = Field(min_length=1, max_length=40)
    last_name: str = Field(min_length=1, max_length=40)
    email: str = Field(
        max_length=100,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )
    address: str = Field(min_length=1, max_length=100)
    zipcode: str = Field(pattern=r"^\d{5}$")
    state_code: str = Field(pattern=r"^[A-Z]{2}$")
    card_type: Literal[
        "americanexpress", "discover", "mastercard", "visa"
    ]
    card_number: str = Field(pattern=r"^\d{16}$")


# ---- Output conversion helpers ----

def customer_out(doc):
    return {
        "id": doc["_id"],
        "name": f"{doc['first_name']} {doc['last_name']}",
    }


def product_out(doc):
    return {
        "id": doc["_id"],
        "name": doc["product_name"],
        "price": str(doc["unit_price"]),
    }


def purchase_out(doc):
    return {
        "id": doc["_id"],
        "product_name": doc["product_name"],
        "amount": str(doc["amount"]),
        "department": doc["department"],
        "purchase_date": doc["purchase_date"].date().isoformat(),
    }


# ---- Page ----

@app.get("/")
def page():
    return FileResponse(HERE / "index.html")


# ---- Customers ----

@app.get("/api/customers")
def get_customers(
    request: Request,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100),
):
    total_size = db.customers.count_documents({})

    docs = (
        db.customers.find(
            {},
            {"first_name": 1, "last_name": 1},
        )
        .sort([("last_name", 1), ("first_name", 1), ("_id", 1)])
        .skip(offset)
        .limit(limit)
    )

    data = [customer_out(doc) for doc in docs]

    return format_output(
        query=get_query(request),
        data=data,
        total_size=total_size,
        offset=offset,
        limit=limit,
    )


@app.get("/api/customers/{customer_id}/purchases")
def get_customer_purchases(
    customer_id: int,
    request: Request,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100),
):
    if db.customers.find_one(
        {"_id": customer_id},
        {"_id": 1},
    ) is None:
        raise HTTPException(
            status_code=404,
            detail=f"Customer {customer_id} not found",
        )

    purchase_filter = {"customer_id": customer_id}
    total_size = db.purchases.count_documents(purchase_filter)

    docs = (
        db.purchases.find(purchase_filter)
        .sort([("purchase_date", -1), ("_id", -1)])
        .skip(offset)
        .limit(limit)
    )

    data = [purchase_out(doc) for doc in docs]

    return format_output(
        query=get_query(request),
        data=data,
        total_size=total_size,
        offset=offset,
        limit=limit,
    )


@app.post("/api/customers", status_code=201)
def create_customer(new: NewCustomer, request: Request):
    email = new.email.lower()

    if db.customers.find_one({"email": email}, {"_id": 1}):
        raise HTTPException(
            status_code=409,
            detail=f"A customer with email {email} already exists",
        )

    doc = {
        "_id": next_id("customer_id"),
        "first_name": new.first_name,
        "last_name": new.last_name,
        "email": email,
        "address": new.address,
        "zipcode": new.zipcode,
        "state_code": new.state_code,
        "cards": [
            {
                "card_id": next_id("card_id"),
                "card_type": new.card_type,
                "card_number": new.card_number,
            }
        ],
    }

    db.customers.insert_one(doc)

    return format_output(
        query=get_query(request),
        response_code=201,
        data=customer_out(doc),
        total_size=1,
    )


# ---- Products ----

@app.get("/api/products")
def get_products(
    request: Request,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100),
):
    total_size = db.products.count_documents({})

    docs = (
        db.products.find(
            {},
            {"product_name": 1, "unit_price": 1},
        )
        .sort([("product_name", 1), ("_id", 1)])
        .skip(offset)
        .limit(limit)
    )

    data = [product_out(doc) for doc in docs]

    return format_output(
        query=get_query(request),
        data=data,
        total_size=total_size,
        offset=offset,
        limit=limit,
    )


@app.get("/api/products/{product_id}")
def get_product(product_id: int, request: Request):
    doc = db.products.find_one({"_id": product_id})

    if doc is None:
        raise HTTPException(
            status_code=404,
            detail=f"Product {product_id} not found",
        )

    product = product_out(doc)
    product["times_purchased"] = db.purchases.count_documents(
        {"product_id": product_id}
    )

    return format_output(
        query=get_query(request),
        data=product,
        total_size=1,
    )


# ---- Start server ----

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
