import requests
from typing import List
from config import YOUTUBE_API_KEY
from models import RawComment


class YouTubeClient:
    BASE_URL = "https://www.googleapis.com/youtube/v3/commentThreads"

    def fetch_comments(self, video_id: str, max_comments: int = 100) -> List[RawComment]:
        comments = []
        next_page_token = None

        while len(comments) < max_comments:
            params = {
                "part": "snippet",
                "videoId": video_id,
                "key": YOUTUBE_API_KEY,
                "maxResults": min(100, max_comments - len(comments)),
                "textFormat": "plainText",
                "order": "relevance"
            }

            if next_page_token:
                params["pageToken"] = next_page_token

            response = requests.get(self.BASE_URL, params=params, timeout=10)

            if response.status_code != 200:
                raise Exception(f"YouTube API error: {response.text}")

            data = response.json()

            for item in data.get("items", []):
                top_comment = item["snippet"]["topLevelComment"]["snippet"]

                comments.append(
                    RawComment(
                        comment_id=item["id"],
                        author=top_comment.get("authorDisplayName"),
                        text=top_comment.get("textDisplay", ""),
                        like_count=top_comment.get("likeCount", 0),
                        published_at=top_comment.get("publishedAt")
                    )
                )

            next_page_token = data.get("nextPageToken")

            if not next_page_token:
                break

        return comments