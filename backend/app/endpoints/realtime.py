from fastapi import WebSocket, WebSocketDisconnect

from genesis import realtime, router

api = router("/realtime")


@api.websocket("/ws/{channel}")
async def subscribe_channel(websocket: WebSocket, channel: str):
    await websocket.accept()
    try:
        async for message in realtime.subscribe(channel):
            await websocket.send_json(message)
    except WebSocketDisconnect:
        pass


@api.post("/{channel}", status_code=204)
async def publish_to_channel(channel: str, message: dict):
    await realtime.publish(channel, message)
