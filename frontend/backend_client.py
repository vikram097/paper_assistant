import logging
import os
import time

import requests
import streamlit as st

from frontend.auth import get_auth_headers

logger = logging.getLogger(__name__)


BASE_URL = os.getenv(
    "BACKEND_URL",
    "http://127.0.0.1:8000",
)
DOCUMENTS_CACHE_KEY = "_documents_cache"
DOCUMENTS_CACHE_TTL_SECONDS = 5


def invalidate_documents_cache():
    st.session_state.pop(DOCUMENTS_CACHE_KEY, None)


def upload_pdf(file):
    logger.info(file.name)
    logger.info(file.type)

    response = requests.post(
        f"{BASE_URL}/upload",
        files={
            "file": (
                file.name,
                file.getvalue(),
                "application/pdf",
            )
        },
        headers=get_auth_headers(),
        timeout=60,
    )

    logger.info(response.status_code)
    logger.info(response.text)

    if response.status_code == 409:
        try:
            detail = response.json().get(
                "detail",
                "Document already exists.",
            )
        except ValueError:
            detail = "Document already exists."

        st.warning(f"⚠️ {detail}")
        return None

    try:
        response.raise_for_status()
    except requests.HTTPError:
        try:
            detail = response.json().get(
                "detail",
                response.text,
            )
        except ValueError:
            detail = response.text

        st.error(f"❌ Upload failed: {detail}")
        return None

    result = response.json()
    invalidate_documents_cache()
    return result


def ask_question(
    question: str,
    documents: list[str] | None = None,
) -> dict:

    logger.info(f"Asking: {BASE_URL}/chat")
    logger.info(f"Question: {question}")
    logger.info(f"Documents sent: {documents}")

    response = requests.post(
        f"{BASE_URL}/chat",
        json={
            "question": question,
            "documents": documents,
            "mode": st.session_state.search_mode,
        },
        headers=get_auth_headers(),
        timeout=60,
    )

    logger.info(response.status_code)
    logger.info(response.text)

    try:
        response.raise_for_status()
    except requests.HTTPError:
        st.error("Backend request failed.")
        raise

    return response.json()


def get_documents():
    access_token = st.session_state.get("access_token")
    cached = st.session_state.get(DOCUMENTS_CACHE_KEY)
    now = time.monotonic()

    if (
        cached
        and cached["access_token"] == access_token
        and now - cached["fetched_at"] < DOCUMENTS_CACHE_TTL_SECONDS
    ):
        return cached["documents"]

    response = requests.get(
        f"{BASE_URL}/documents",
        headers=get_auth_headers(),
        timeout=30,
    )

    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After", "a few")
        st.warning(
            f"Document list is temporarily rate-limited. "
            f"Retry in {retry_after} seconds."
        )
        if cached and cached["access_token"] == access_token:
            return cached["documents"]
        return []

    try:
        response.raise_for_status()
    except requests.HTTPError:
        st.error("Backend request failed.")
        raise

    documents = response.json()["documents"]
    st.session_state[DOCUMENTS_CACHE_KEY] = {
        "access_token": access_token,
        "fetched_at": now,
        "documents": documents,
    }
    return documents


def get_stats():

    response = requests.get(
        f"{BASE_URL}/stats",
        headers=get_auth_headers(),
        timeout=30,
    )

    try:
        response.raise_for_status()
    except requests.HTTPError:
        try:
            detail = response.json().get(
                "detail",
                response.text,
            )
        except ValueError:
            detail = response.text

        st.error(f"Upload failed: {detail}")
        return None

    data = response.json()

    return {
        "documents": data["total_documents"],
        "chunks": data["total_chunks"],
        "embedding_model": data["embedding_model"],
    }


def delete_document(filename):

    response = requests.delete(
        f"{BASE_URL}/documents/{filename}",
        headers=get_auth_headers(),
        timeout=30,
    )

    if response.ok:
        invalidate_documents_cache()

    return response


def download_document(filename):

    return requests.get(
        f"{BASE_URL}/documents/{filename}/download",
        headers=get_auth_headers(),
        stream=True,
        timeout=30,
    )