import time
import asyncio
import threading
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from app.docker_utils import create_docker_dict, get_filtered_logs, fetch_logs_background, CONTAINER_DICT, LOG_CACHE, client
from app.routes import config
from app import alerts
from contextlib import asynccontextmanager

app = FastAPI()

app.include_router(config.router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],  # Change to frontend origin in prod
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*']
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_docker_dict()

    global CONTAINER_DICT

    # Optionally refresh container list here if needed
    container_names = list(CONTAINER_DICT.keys())  # or re-detect dynamically

    for name in container_names:
        thread = threading.Thread(
            target=fetch_logs_background,
            args=(name,),
            daemon=True
        )
        thread.start()
    print("[LogForge] Background log fetchers started.")

    yield

app.router.lifespan_context = lifespan

@app.get("/containers")
def list_containers():
    """ Get a dictionary of Docker containers with their details."""
    return create_docker_dict()


# @app.get("/logs/{container_name}")
# def logs(container_name: str, tail: int = 100):
#     """ Get logs for a specific container by name.
#     Args:
#         container_name (str): The name of the container.
#         tail (int): The number of lines to show from the end of the logs.

#     Returns:
#         dict: A dictionary containing the logs.
#     """

#     logs = LOG_CACHE.get(container_name)

#     if logs is None:
#         raise HTTPException(status_code=404, detail="Container Not Found")
#     return {'logs': logs}


@app.get("/logs/filter/{container_name}")
def get_filtered_log(container_name: str):
    """ Get filtered logs for a specific container by name.
    Args:
        container_name (str): The name of the container.

    Returns:
        dict: A dictionary containing the filtered logs.    
    """
    return {'filtered_logs': get_filtered_logs(container_name)}

@app.get("/alerts")
def get_alerts():
    """ Get current alerts from the alert store."""
    alerts.scan_logs_for_alerts()
    return alerts.ALERT_STORE
@app.get("/clear_alerts")
def clear_alerts():
    """ Clear all alerts from the alert store."""
    alerts.ALERT_STORE.clear()
    return {"status": "Alerts cleared"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

def alert_loop():
    while True:
        alerts.scan_logs_for_alerts()
        time.sleep(30)

threading.Thread(target=alert_loop, daemon=True).start()


@app.websocket("/ws/logs/{container_name}")
async def websocket_log_stream(websocket: WebSocket, container_name: str):
    await websocket.accept()
    try:
        container_info = CONTAINER_DICT.get(container_name)
        if not container_info:
            await websocket.close(code=1003, reason="Container not found")
            return

        container = client.containers.get(container_info["container_id"])

        # Start streaming new logs
        since_ts = int(time.time()) - 48 * 60 * 60  # 48 hours ago in seconds
        log_stream = container.logs(since= since_ts ,stream=True, stdout=True, stderr=True, follow=True, timestamps=True)

        while True:
            try:
                # Non-blocking read with asyncio
                line = await asyncio.to_thread(next, log_stream, None)
                if line:
                    await websocket.send_text(line.decode())
                else:
                    # If no new line, sleep a bit
                    await asyncio.sleep(0.5)
            except WebSocketDisconnect:
                print(f"[DEBUG] WebSocket disconnected for {container_name}")
                break
            except StopIteration:
                # Docker closed the stream
                break
            except Exception as e:
                print(f"[ERROR] Streaming error: {e}")
                break
    except WebSocketDisconnect:
        print(f"Client disconnected: {container_name}")
        # Just exit, no need to close manually
    except Exception as e:
        print(f"Unexpected error: {e}")
#-----------------
@app.get("/debug/logcache")
def debug_log_cache():
    return {"containers": list(LOG_CACHE.keys())}
