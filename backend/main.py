from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from youtube_client import YouTubeClient
from llm_client import LocalLLMClient
from agents.comments_parser_agent import CommentParserAgent
from agents.comment_filter_agent import CommentFilterAgent
from agents.recommendation_agent import RecommendationAgent

app = FastAPI(title="YouTube Comment Pulse API", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8000",
        "https://www.youtube.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

youtube_client = YouTubeClient()
parser_agent = CommentParserAgent()
filter_agent = CommentFilterAgent()

llm_client = LocalLLMClient()
recommendation_agent = RecommendationAgent(llm_client=llm_client)


@app.get("/")
def home():
    return {
        "app": "YouTube Comment Pulse API",
        "version": "1.1.0",
        "status": "running",
        "llm_provider": llm_client.provider,
        "llm_model": llm_client.model
    }


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "version": "1.1.0",
        "llm": llm_client.health_check()
    }


@app.get("/analyze")
def analyze_video(
    video_id: str = Query(..., min_length=5, description="YouTube video ID"),
    max_comments: int = Query(100, ge=10, le=300, description="Maximum comments to analyze")
):
    try:
        raw_comments = youtube_client.fetch_comments(
            video_id=video_id,
            max_comments=max_comments
        )

        if not raw_comments:
            raise HTTPException(
                status_code=404,
                detail="No comments found. Comments may be disabled for this video."
            )

        parsed_comments = parser_agent.parse(raw_comments)
        filtered_result = filter_agent.filter(parsed_comments)
        final_result = recommendation_agent.analyze(filtered_result.useful_comments)

        return {
            "video_id": video_id,
            "raw_comments_count": len(raw_comments),
            "parsed_comments_count": len(parsed_comments),
            "useful_comments_count": len(filtered_result.useful_comments),
            "removed_comments_count": len(filtered_result.removed_comments),
            "result": final_result
        }

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error)
        )