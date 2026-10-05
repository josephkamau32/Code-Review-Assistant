from typing import List, Dict, Any, Set, Optional
from loguru import logger
from unidiff import PatchSet
from src.rag.embeddings import EmbeddingService
from src.rag.vector_store import VectorStoreManager
from src.rag.llm_service import LLMService
from src.models.schemas import (
    PullRequest,
    ReviewSuggestion,
    ReviewResponse,
    HistoricalReview,
)
from src.config.settings import settings
from src.utils.redaction import redact_text
import time


def extract_valid_lines(diff: str, file_path: str) -> Set[int]:
    """Extract the set of valid target (new-side) line numbers from a unified diff.

    Uses `unidiff` to parse the diff hunk headers and identify lines that were
    added or left unchanged in the target file. Suggestions referencing line
    numbers outside this set are hallucinated by the LLM (LLM-04).
    """
    valid: Set[int] = set()
    try:
        # unidiff expects a full patch; wrap single-file diff with header
        patch_text = f"--- a/{file_path}\n+++ b/{file_path}\n{diff}"
        patch = PatchSet(patch_text)
        for patched_file in patch:
            for hunk in patched_file:
                for line in hunk:
                    # target lines include added (+) and context (space) lines
                    if line.target_line_no is not None:
                        valid.add(line.target_line_no)
    except Exception as e:
        logger.debug(f"Could not parse diff for {file_path}: {e}")
    return valid


# Default max snap distance: 20 lines.
# Rationale: typical diff hunks have 3 lines of context on each side (6 total)
# plus the changed lines. A 20-line tolerance covers most realistic cases where
# the LLM is slightly off, while preventing a suggestion for line 500 from
# snapping to an unrelated line 10 in a small diff.
MAX_SNAP_DISTANCE: int = 20


def snap_to_nearest(
    line: int, valid_lines: Set[int], max_snap_distance: int = MAX_SNAP_DISTANCE
) -> Optional[int]:
    """Return the closest valid line number, or None if too far or set is empty.

    If the nearest valid line is farther than *max_snap_distance*, return None
    (file-level fallback) instead of snapping to unrelated code (CR-05).
    """
    if not valid_lines:
        return None
    nearest = min(valid_lines, key=lambda v: abs(v - line))
    if abs(nearest - line) > max_snap_distance:
        return None
    return nearest


class RAGPipeline:
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.vector_store = VectorStoreManager()
        self.llm_service = LLMService()

    def ingest_historical_reviews(self, reviews: List[HistoricalReview]):
        """Ingest historical reviews into the vector database"""
        if not reviews:
            logger.warning("No reviews to ingest")
            return

        logger.info(f"Ingesting {len(reviews)} historical reviews...")

        try:
            # Validate reviews
            valid_reviews = []
            for idx, review in enumerate(reviews):
                try:
                    # Validate required fields
                    if not review.review_comment or not review.repository:
                        logger.warning(
                            f"Skipping review {idx}: missing required fields"
                        )
                        continue

                    # Validate field lengths
                    if len(review.review_comment) > 10000:
                        logger.warning(
                            f"Skipping review {idx}: comment too long ({len(review.review_comment)} chars)"
                        )
                        continue

                    if review.code_snippet and len(review.code_snippet) > 50000:
                        logger.warning(
                            f"Skipping review {idx}: code snippet too long ({len(review.code_snippet)} chars)"
                        )
                        continue

                    valid_reviews.append(review)

                except Exception as e:
                    logger.error(f"Error validating review {idx}: {e}")
                    continue

            if not valid_reviews:
                logger.error("No valid reviews after validation")
                return

            logger.info(f"Validated {len(valid_reviews)}/{len(reviews)} reviews")

            # Prepare documents for embedding with secrets/PII redacted (PRIV-02)
            redacted_reviews = []
            documents = []
            for review in valid_reviews:
                redacted_snippet = ""
                if review.code_snippet:
                    redacted_snippet, rep_snip = redact_text(review.code_snippet)
                    if rep_snip.total_redactions > 0:
                        logger.info(
                            f"Redacted {rep_snip.total_redactions} potential secret(s) "
                            f"from historical review snippet (PR #{review.pr_number}, "
                            f"{review.file_path}): {rep_snip.redactions_by_label}"
                        )
                redacted_comment, rep_com = redact_text(review.review_comment)
                if rep_com.total_redactions > 0:
                    logger.info(
                        f"Redacted {rep_com.total_redactions} potential secret(s) "
                        f"from historical review comment (PR #{review.pr_number}, "
                        f"{review.file_path}): {rep_com.redactions_by_label}"
                    )

                redacted_review = review.model_copy(
                    update={
                        "code_snippet": redacted_snippet,
                        "review_comment": redacted_comment,
                    }
                )
                redacted_reviews.append(redacted_review)

                code_part = redacted_snippet.strip()
                comment_part = redacted_comment.strip()
                doc = f"Code:\n{code_part}\n\nReview Comment:\n{comment_part}"
                documents.append(doc)

            # Generate embeddings in batch with error handling
            logger.info("Generating embeddings...")
            try:
                embeddings = self.embedding_service.embed_batch(documents)
            except Exception as e:
                logger.error(f"Failed to generate embeddings: {e}")
                raise

            if len(embeddings) != len(redacted_reviews):
                logger.error(
                    f"Embedding count mismatch: got {len(embeddings)}, expected {len(redacted_reviews)}"
                )
                raise ValueError("Embedding count mismatch")

            # Store in vector database
            logger.info("Storing in vector database...")
            try:
                self.vector_store.add_reviews_batch(redacted_reviews, embeddings)
            except Exception as e:
                logger.error(f"Failed to store in vector database: {e}")
                raise

            logger.info(f"Successfully ingested {len(redacted_reviews)} reviews")

        except Exception as e:
            logger.error(f"Error during review ingestion: {type(e).__name__} - {e}")
            raise

    def review_pull_request(
        self, pull_request: PullRequest, style_guide: str = ""
    ) -> ReviewResponse:
        """Main pipeline: Review a pull request using RAG"""
        start_time = time.time()
        all_suggestions = []

        # Validate input
        if not pull_request:
            raise ValueError("pull_request cannot be None")
        if not pull_request.changes:
            logger.warning(f"PR #{pull_request.pr_number} has no changes to review")
            return ReviewResponse(
                pr_number=pull_request.pr_number,
                repository=pull_request.repository,
                suggestions=[],
                summary="No code changes found to review.",
                processing_time_seconds=0.0,
            )

        logger.info(
            f"Starting review for PR #{pull_request.pr_number} in "
            f"{pull_request.repository} ({len(pull_request.changes)} files)"
        )

        for code_change in pull_request.changes:
            # Skip files with no meaningful changes or non-code files
            if not code_change.diff or code_change.language == "other":
                continue

            # --- Step 0: Line validation on the REAL diff (LLM-04) -----------
            # Must happen BEFORE redaction so unidiff sees the original
            # hunk headers and content unchanged.
            valid_lines = extract_valid_lines(code_change.diff, code_change.file_path)

            # --- Step 0b: Redact secrets/PII from diff and file path (PRIV-02)
            # Create a redacted copy of the CodeChange for all external API
            # calls (embedding + LLM).  The original code_change is kept
            # intact for line-number bookkeeping above.
            redacted_diff, diff_report = redact_text(code_change.diff)
            redacted_file_path, fp_report = redact_text(code_change.file_path)
            total_redactions = diff_report.total_redactions + fp_report.total_redactions
            if total_redactions > 0:
                combined_labels = dict(diff_report.redactions_by_label)
                for lbl, count in fp_report.redactions_by_label.items():
                    combined_labels[lbl] = combined_labels.get(lbl, 0) + count
                logger.info(
                    f"Redacted {total_redactions} potential "
                    f"secret(s) from {code_change.file_path}: "
                    f"{combined_labels}"
                )
            redacted_change = code_change.model_copy(
                update={"diff": redacted_diff, "file_path": redacted_file_path}
            )

            # Step 1: Generate embedding for the code change (redacted)
            code_context = (
                f"File: {redacted_change.file_path}\n"
                f"Language: {redacted_change.language.value}"
            )
            logger.debug(
                f"DEBUG: Generating embedding for {redacted_change.file_path}, diff_length: {len(redacted_change.diff)}"
            )
            query_embedding = self.embedding_service.embed_code_change(
                redacted_change.diff, context=code_context
            )
            logger.debug(
                f"DEBUG: Generated query embedding, length: {len(query_embedding)}"
            )

            # Step 2: Retrieve similar past reviews
            filter_dict = {"language": code_change.language.value}

            logger.debug(
                f"DEBUG: Searching for similar reviews with filter: {filter_dict}"
            )
            search_results = self.vector_store.search_similar_reviews(
                query_embedding=query_embedding,
                n_results=settings.top_k_results,
                filter_dict=filter_dict,
            )

            # Format similar reviews for LLM context
            similar_reviews = []
            if search_results["documents"] and len(search_results["documents"][0]) > 0:
                logger.debug(
                    f"DEBUG: Found {len(search_results['documents'][0])} similar reviews"
                )
                for i, doc in enumerate(search_results["documents"][0]):
                    similar_reviews.append(
                        {
                            "document": doc,
                            "metadata": search_results["metadatas"][0][i],
                            "distance": (
                                search_results["distances"][0][i]
                                if "distances" in search_results
                                else None
                            ),
                        }
                    )
            else:
                logger.debug("DEBUG: No similar reviews found")

            # Step 3: Generate review using LLM with RAG context (redacted)
            review_result = self.llm_service.generate_review(
                code_change=redacted_change,
                similar_reviews=similar_reviews,
                style_guide_context=style_guide,
            )

            # Step 4: Parse suggestions with line-number validation (LLM-04)
            # valid_lines was computed in Step 0 from the REAL (un-redacted) diff.
            for suggestion_data in review_result.get("suggestions", []):
                raw_line = suggestion_data.get("line_number")
                validated_line = None
                if raw_line is not None:
                    try:
                        raw_line = int(raw_line)
                    except (TypeError, ValueError):
                        raw_line = None

                if raw_line is not None and valid_lines:
                    if raw_line in valid_lines:
                        validated_line = raw_line
                    else:
                        validated_line = snap_to_nearest(raw_line, valid_lines)
                        logger.debug(
                            f"LLM suggested line {raw_line} not in diff; "
                            f"snapped to {validated_line}"
                        )
                elif raw_line is not None:
                    # Could not parse diff; trust LLM as fallback
                    validated_line = raw_line

                suggestion = ReviewSuggestion(
                    file_path=code_change.file_path,
                    line_number=validated_line,
                    suggestion=suggestion_data["suggestion"],
                    severity=suggestion_data["severity"],
                    category=suggestion_data["category"],
                    confidence=suggestion_data.get("confidence", 0.8),
                    similar_past_reviews=[sr["document"] for sr in similar_reviews[:2]],
                )
                all_suggestions.append(suggestion)

        # Generate overall summary
        summary = self.llm_service.generate_summary(all_suggestions)

        processing_time = time.time() - start_time

        response = ReviewResponse(
            pr_number=pull_request.pr_number,
            repository=pull_request.repository,
            suggestions=all_suggestions,
            summary=summary,
            processing_time_seconds=round(processing_time, 2),
        )

        logger.info(
            f"Review complete for PR #{pull_request.pr_number}. "
            f"Found {len(all_suggestions)} suggestions in {processing_time:.2f}s"
        )

        return response

    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics"""
        return self.vector_store.get_collection_stats()
