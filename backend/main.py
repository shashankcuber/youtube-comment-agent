from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from youtube_client import YouTubeClient
from agents.comments_parser_agent import CommentParserAgent
from agents.comment_filter_agent import CommentFilterAgent
from agents.recommendation_agent import RecommendationAgent

app = FastAPI(title="YouTube Comment Intelligence API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

youtube_client = YouTubeClient()
parser_agent = CommentParserAgent()
filter_agent = CommentFilterAgent()
recommendation_agent = RecommendationAgent()


@app.get("/")
def home():
    return {
        "message": "YouTube Comment Intelligence API is running"
    }


@app.get("/analyze")
def analyze_video(
    video_id: str = Query(..., description="YouTube video ID"),
    max_comments: int = Query(100, description="Maximum comments to analyze")
):
    raw_comments = youtube_client.fetch_comments(
        video_id=video_id,
        max_comments=max_comments
    )

    parsed_comments = parser_agent.parse(raw_comments)

    filtered_result = filter_agent.filter(parsed_comments)

    final_result = recommendation_agent.analyze(
        filtered_result.useful_comments
    )

    return {
        "video_id": video_id,
        "raw_comments_count": len(raw_comments),
        "parsed_comments_count": len(parsed_comments),
        "useful_comments_count": len(filtered_result.useful_comments),
        "removed_comments_count": len(filtered_result.removed_comments),
        "result": final_result
    }