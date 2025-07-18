from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.trades import router as trades_router

origins = [
    "http://localhost:3000",
]

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(trades_router, prefix="/trades")
