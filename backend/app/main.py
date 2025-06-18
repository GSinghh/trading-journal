from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

origins = [
    "http://localhost:3000",
]

journal = FastAPI()

journal.add_middleware(
    CORSMiddleware,
    allow_origins=origins,            # or ["*"] to allow all
    allow_credentials=True,
    allow_methods=["*"],              # GET, POST, PUT, DELETE, etc.
    allow_headers=["*"],              # Content-Type, Authorization, etc.
)

@journal.get("/api/test")
async def testing():
    return {"Message":"Endpoint is Active"}

@journal.post("/api/file_upload")
async def parse_csv(file: UploadFile = File(...)):
    if not file:
        return {"Message":"File Not Found"}
    return {"File Name": f"{file.filename}"}
