import threading
import time
from typing import Optional

import streamlit as st
import requests
import logging

logger = logging.getLogger(__name__)


def _poll_task(task_id: str, status_url: str, result_key: str, interval: float = 5.0, max_attempts: int = 60):
    """Background poller that checks the assistant task status and writes the result into st.session_state[result_key].

    This runs in a daemon thread. It is intentionally lightweight and tolerant of intermittent errors.
    """
    logger.info(f"Starting background poller for task {task_id} -> {status_url}")
    attempts = 0
    last_result = None
    while attempts < max_attempts:
        attempts += 1
        try:
            resp = requests.get(status_url, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                logger.debug(f"Poll attempt {attempts} for {task_id}: {data}")
                if data.get("status") in ("completed", "failed"):
                    # Write final result to session state
                    try:
                        st.session_state[result_key] = data
                        st.session_state[f"assistant_task_status_{task_id}"] = data.get("status")
                    except Exception:
                        # If we cannot write to st.session_state (rare), keep a module-level cache
                        logger.exception("Failed to write poll result to st.session_state")
                    logger.info(f"Task {task_id} finished with status: {data.get('status')}")
                    return
                else:
                    # Update last known result
                    last_result = data
                    try:
                        st.session_state[f"assistant_task_status_{task_id}"] = data.get("status")
                    except Exception:
                        pass
            else:
                logger.warning(f"Status check for {task_id} returned HTTP {resp.status_code}")
        except Exception as e:
            logger.warning(f"Error polling task {task_id} attempt {attempts}: {e}")

        time.sleep(interval)

    # If we exit loop due to attempts exhausted, store timeout/failure
    timeout_result = {"status": "timeout", "task_id": task_id, "last_result": last_result}
    try:
        st.session_state[result_key] = timeout_result
        st.session_state[f"assistant_task_status_{task_id}"] = "timeout"
    except Exception:
        logger.exception("Failed to write timeout result to st.session_state")
    logger.warning(f"Polling for task {task_id} timed out after {max_attempts} attempts")


def start_task_poller(task_id: str, status_url: str, result_key: str = "assistant_parsed_data", interval: float = 5.0, max_attempts: int = 60) -> Optional[threading.Thread]:
    """Start a daemon thread that polls `status_url` and writes the final JSON to st.session_state[result_key].

    Returns the Thread object.
    """
    thread_name = f"assistant_poller_{task_id}"
    thread = threading.Thread(target=_poll_task, args=(task_id, status_url, result_key, interval, max_attempts), name=thread_name)
    thread.daemon = True
    thread.start()
    logger.info(f"Started background poller thread {thread_name}")
    return thread
