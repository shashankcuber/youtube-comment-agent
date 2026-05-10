from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from youtube_client import YouTubeClient
from llm_client import LocalLLMClient

from agents.comments_parser_agent import CommentParserAgent
from agents.comment_filter_agent import CommentFilterAgent
from agents.recommendation_agent import RecommendationAgent
from agents.raw_comment_llm_agent import RawCommentLLMAgent

from models import PublicSentimentResult, LLMStatus

app = FastAPI(title="YouTube Comment Pulse API", version="1.2.0")

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

rule_based_recommendation_agent = RecommendationAgent(
    llm_client=None
)

raw_comment_llm_agent = RawCommentLLMAgent(
    llm_client=llm_client
)

from graph.comment_analysis_graph import build_comment_analysis_graph

comment_graph = build_comment_analysis_graph()

@app.get("/")
def home():
    return {
        "app": "YouTube Comment Pulse API",
        "version": "1.2.0",
        "status": "running",
        "llm_provider": llm_client.provider,
        "llm_model": llm_client.model
    }


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "version": "1.2.0",
        "llm": llm_client.health_check()
    }

@app.get("/analyze")
def analyze_video(
    video_id: str = Query(..., min_length=5, description="YouTube video ID"),
    max_comments: int = Query(100, ge=10, le=300, description="Maximum raw comments to fetch"),
    max_comments_for_llm: int = Query(80, ge=10, le=150, description="Maximum raw comments to send to LLM")
):
    execution_steps = []

    try:
        step_start = now()

        raw_comments = youtube_client.fetch_comments(
            video_id=video_id,
            max_comments=max_comments
        )

        execution_steps.append(
            make_step(
                node="fetch_comments",
                label="Fetch YouTube comments",
                status="success",
                message=f"Fetched {len(raw_comments)} raw comments.",
                duration_seconds=elapsed(step_start)
            )
        )

        if not raw_comments:
            execution_steps.append(
                make_step(
                    node="fetch_comments",
                    label="Fetch YouTube comments",
                    status="failed",
                    message="No comments found. Comments may be disabled."
                )
            )

            raise HTTPException(
                status_code=404,
                detail="No comments found. Comments may be disabled for this video."
            )

        execution_steps.append(
            make_step(
                node="raw_llm_agent",
                label="Raw Comment LLM Agent",
                status="running",
                message=f"Sending up to {max_comments_for_llm} comments to {llm_client.model}."
            )
        )

        try:
            step_start = now()

            llm_result = raw_comment_llm_agent.analyze(
                raw_comments=raw_comments,
                max_comments_for_llm=max_comments_for_llm
            )

            execution_steps[-1] = make_step(
                node="raw_llm_agent",
                label="Raw Comment LLM Agent",
                status="success",
                message=f"LLM analysis completed using {llm_client.model}.",
                duration_seconds=elapsed(step_start)
            )

            execution_steps.append(
                make_step(
                    node="final_response",
                    label="Final Response",
                    status="success",
                    message="Generated final public sentiment and recommendation."
                )
            )

            llm_result.execution_steps = execution_steps

            return {
                "video_id": video_id,
                "analysis_mode": "raw_comments_llm",
                "raw_comments_count": len(raw_comments),
                "result": llm_result
            }

        except Exception as llm_error:
            execution_steps[-1] = make_step(
                node="raw_llm_agent",
                label="Raw Comment LLM Agent",
                status="failed",
                message=str(llm_error)
            )

            step_start = now()

            parsed_comments = parser_agent.parse(raw_comments)

            execution_steps.append(
                make_step(
                    node="parser_agent",
                    label="Parser Agent",
                    status="success",
                    message=f"Parsed {len(parsed_comments)} comments.",
                    duration_seconds=elapsed(step_start)
                )
            )

            step_start = now()

            filtered_result = filter_agent.filter(parsed_comments)

            execution_steps.append(
                make_step(
                    node="filter_agent",
                    label="Filter Agent",
                    status="success",
                    message=(
                        f"Kept {len(filtered_result.useful_comments)} useful comments "
                        f"and removed {len(filtered_result.removed_comments)} comments."
                    ),
                    duration_seconds=elapsed(step_start)
                )
            )

            step_start = now()

            fallback_result = rule_based_recommendation_agent.analyze(
                filtered_result.useful_comments
            )

            execution_steps.append(
                make_step(
                    node="rule_based_recommendation_agent",
                    label="Rule-based Recommendation Agent",
                    status="fallback",
                    message="Used rule-based fallback because LLM failed.",
                    duration_seconds=elapsed(step_start)
                )
            )

            execution_steps.append(
                make_step(
                    node="final_response",
                    label="Final Response",
                    status="success",
                    message="Generated final response from fallback system."
                )
            )

            llm_status = LLMStatus(
                attempted=True,
                success=False,
                provider=llm_client.provider,
                model=llm_client.model,
                source="rule_based_fallback",
                error=str(llm_error)
            )

            fallback_public_result = PublicSentimentResult(
                result_source="rule_based_fallback",
                llm_status=llm_status,

                execution_steps=execution_steps,

                total_raw_comments=len(raw_comments),
                comments_sent_to_llm=0,

                overall_public_sentiment=fallback_result.overall_sentiment,
                sentiment_distribution=_groups_to_distribution(fallback_result.groups),

                authenticity_score=5.0,
                authenticity_label="uncertain",
                authenticity_explanation=(
                    "LLM analysis failed, so authenticity could not be estimated from raw comments. "
                    "Rule-based fallback was used."
                ),

                public_opinion_summary=fallback_result.summary,
                watch_decision=_rating_to_decision(fallback_result.watch_rating),
                watch_rating=fallback_result.watch_rating,
                recommendation=fallback_result.recommendation,

                positive_themes=fallback_result.positives,
                negative_themes=fallback_result.negatives,
                neutral_themes=[],
                warning_themes=fallback_result.warnings,

                evidence_comments=_collect_group_examples(fallback_result.groups),

                fallback_used=True,
                fallback_reason=str(llm_error),
                fallback_rule_based_result=fallback_result
            )

            return {
                "video_id": video_id,
                "analysis_mode": "rule_based_fallback",
                "raw_comments_count": len(raw_comments),
                "parsed_comments_count": len(parsed_comments),
                "useful_comments_count": len(filtered_result.useful_comments),
                "removed_comments_count": len(filtered_result.removed_comments),
                "result": fallback_public_result
            }

    except HTTPException:
        raise

    except Exception as error:
        execution_steps.append(
            make_step(
                node="backend_error",
                label="Backend Error",
                status="failed",
                message=str(error)
            )
        )

        raise HTTPException(
            status_code=500,
            detail={
                "error": str(error),
                "execution_steps": execution_steps
            }
        )

# @app.get("/analyze")
# def analyze_video(
#     video_id: str = Query(..., min_length=5, description="YouTube video ID"),
#     max_comments: int = Query(100, ge=10, le=300, description="Maximum raw comments to fetch"),
#     max_comments_for_llm: int = Query(80, ge=10, le=150, description="Maximum raw comments to send to LLM")
# ):
#     try:
#         raw_comments = youtube_client.fetch_comments(
#             video_id=video_id,
#             max_comments=max_comments
#         )

#         if not raw_comments:
#             raise HTTPException(
#                 status_code=404,
#                 detail="No comments found. Comments may be disabled for this video."
#             )

#         try:
#             llm_result = raw_comment_llm_agent.analyze(
#                 raw_comments=raw_comments,
#                 max_comments_for_llm=max_comments_for_llm
#             )

#             return {
#                 "video_id": video_id,
#                 "analysis_mode": "raw_comments_llm",
#                 "raw_comments_count": len(raw_comments),
#                 "result": llm_result
#             }

#         except Exception as llm_error:
#             parsed_comments = parser_agent.parse(raw_comments)
#             filtered_result = filter_agent.filter(parsed_comments)

#             fallback_result = rule_based_recommendation_agent.analyze(
#                 filtered_result.useful_comments
#             )

#             llm_status = LLMStatus(
#                 attempted=True,
#                 success=False,
#                 provider=llm_client.provider,
#                 model=llm_client.model,
#                 source="rule_based_fallback",
#                 error=str(llm_error)
#             )

#             fallback_public_result = PublicSentimentResult(
#                 result_source="rule_based_fallback",
#                 llm_status=llm_status,

#                 total_raw_comments=len(raw_comments),
#                 comments_sent_to_llm=0,

#                 overall_public_sentiment=fallback_result.overall_sentiment,
#                 sentiment_distribution=_groups_to_distribution(fallback_result.groups),

#                 authenticity_score=5.0,
#                 authenticity_label="uncertain",
#                 authenticity_explanation=(
#                     "LLM analysis failed, so authenticity could not be estimated from raw comments. "
#                     "Rule-based fallback was used."
#                 ),

#                 public_opinion_summary=fallback_result.summary,
#                 watch_decision=_rating_to_decision(fallback_result.watch_rating),
#                 watch_rating=fallback_result.watch_rating,
#                 recommendation=fallback_result.recommendation,

#                 positive_themes=fallback_result.positives,
#                 negative_themes=fallback_result.negatives,
#                 neutral_themes=[],
#                 warning_themes=fallback_result.warnings,

#                 evidence_comments=_collect_group_examples(fallback_result.groups),

#                 fallback_used=True,
#                 fallback_reason=str(llm_error),
#                 fallback_rule_based_result=fallback_result
#             )

#             return {
#                 "video_id": video_id,
#                 "analysis_mode": "rule_based_fallback",
#                 "raw_comments_count": len(raw_comments),
#                 "parsed_comments_count": len(parsed_comments),
#                 "useful_comments_count": len(filtered_result.useful_comments),
#                 "removed_comments_count": len(filtered_result.removed_comments),
#                 "result": fallback_public_result
#             }

#     except HTTPException:
#         raise

#     except Exception as error:
#         raise HTTPException(
#             status_code=500,
#             detail=str(error)
        # )

@app.get("/analyze-graph")
def analyze_video_graph(
    video_id: str = Query(..., min_length=5),
    max_comments: int = Query(100, ge=10, le=300),
    max_comments_for_llm: int = Query(40, ge=10, le=100)
):
    raw_comments = youtube_client.fetch_comments(
        video_id=video_id,
        max_comments=max_comments
    )

    raw_comment_dicts = [
        {
            "comment_id": comment.comment_id,
            "author": comment.author,
            "text": comment.text,
            "like_count": comment.like_count,
            "published_at": comment.published_at
        }
        for comment in raw_comments
    ]

    comments_for_llm = sorted(
        raw_comment_dicts,
        key=lambda c: c.get("like_count", 0),
        reverse=True
    )[:max_comments_for_llm]

    result_state = comment_graph.invoke({
        "video_id": video_id,
        "raw_comments": raw_comment_dicts,
        "comments_for_llm": comments_for_llm,
        "errors": [],
        "used_fallback": False
    })

    return {
        "video_id": video_id,
        "analysis_mode": "langgraph",
        "final_result": result_state.get("final_result"),
        "full_state": result_state
    }

def _groups_to_distribution(groups):
    counts = {
        "positive": 0,
        "negative": 0,
        "neutral": 0,
        "warning": 0
    }

    total = 0

    for group in groups:
        label = group.label
        count = group.count

        if label in counts:
            counts[label] = count
            total += count

    if total == 0:
        return {
            "positive": 0.0,
            "negative": 0.0,
            "neutral": 1.0,
            "warning": 0.0
        }

    return {
        key: round(value / total, 2)
        for key, value in counts.items()
    }


def _rating_to_decision(rating: float) -> str:
    if rating >= 8:
        return "watch"

    if rating >= 6:
        return "skim"

    if rating >= 4:
        return "uncertain"

    return "skip"


def _collect_group_examples(groups):
    examples = []

    for group in groups:
        for example in group.examples[:2]:
            examples.append(example)

    return examples[:5]

import time
from typing import Optional

def make_step(
    node: str,
    label: str,
    status: str,
    message: Optional[str] = None,
    duration_seconds: float = None
):
    return {
        "node": node,
        "label": label,
        "status": status,
        "message": message,
        "duration_seconds": duration_seconds
    }


def now():
    return time.perf_counter()


def elapsed(start_time: float):
    return round(time.perf_counter() - start_time, 3)