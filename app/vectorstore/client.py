from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from app.config.settings import settings


@lru_cache
def get_qdrant_client():
    client = QdrantClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
    )

    try:
        if not client.collection_exists(settings.collection_name):
            client.create_collection(
                collection_name=settings.collection_name,
                vectors_config=VectorParams(
                    size=384,
                    distance=Distance.COSINE,
                ),
            )
    except Exception:
        pass

    return client