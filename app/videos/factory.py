from app.core.config import Settings
from app.videos.base import VideosClient
from app.videos.fake_client import FakeVideosClient
from app.videos.tolerante import VideosTolerante
from app.videos.youtube_client import YouTubeClient


def crear_videos_client(settings: Settings) -> VideosClient:
    if settings.videos_proveedor == "youtube":
        return VideosTolerante(YouTubeClient(settings))
    return VideosTolerante(FakeVideosClient())
