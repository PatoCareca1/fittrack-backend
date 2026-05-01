import asyncio
import websockets
import json

async def test():
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzc3NTk3MDM5LCJpYXQiOjE3Nzc1OTYxMzksImp0aSI6IjYwMzQxZjgzZjIzNjQ4MzVhYTNjY2NkM2MyNmFlYTE3IiwidXNlcl9pZCI6NH0.CcxnpXPHO-VfWQXfVQ6iu6MOTPua-7KvT0iq7o6cDz8"
    uri = f"ws://localhost:8001/ws/chat/1/?token={token}"
    
    print(f"Connecting to {uri} ...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected! Sending message...")
            await websocket.send(json.dumps({"content": "Olá!"}))
            
            response = await websocket.recv()
            print("Received:", response)
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(test())
