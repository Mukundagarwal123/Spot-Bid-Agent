from fastapi import FastAPI, Request, Query
from fastapi.responses import PlainTextResponse, JSONResponse

app = FastAPI()

VERIFY_TOKEN = "123"


@app.get("/")
def home():
    return {"status": "WhatsApp webhook server running"}


@app.get("/webhook")
def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    print("Webhook verification request received")
    print("mode:", hub_mode)
    print("token:", hub_verify_token)
    print("challenge:", hub_challenge)

    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return PlainTextResponse(content=hub_challenge)

    return PlainTextResponse(content="Verification token mismatch", status_code=403)


@app.post("/webhook")
async def receive_webhook(request: Request):
    body = await request.json()
    print("Incoming WhatsApp webhook:")
    print(body)
    return JSONResponse(content={"status": "ok"})