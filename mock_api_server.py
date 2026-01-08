"""Mock API server for testing."""
from fastapi import FastAPI, Header
import uvicorn

app = FastAPI()

@app.post("/api/data")
async def receive_data(x_api_key: str = Header(None)):
    """Mock endpoint to receive forwarded data."""
    print(f"Received request with X-API-Key: {x_api_key}")
    return {"status": "ok", "message": "Data received successfully"}

if __name__ == "__main__":
    print("Starting mock API server on http://localhost:8080")
    uvicorn.run(app, host="127.0.0.1", port=8080, log_level="info")
