from dotenv import load_dotenv

load_dotenv()

import json
import os

from agents.guidance_extractor import extract_guidance
from langchain_openai import ChatOpenAI
from pipeline.state import create_initial_state


def run_evaluation():
    """
    Standalone evaluation of Agent 2 (guidance_extractor).

    Evaluates on 20 manually curated input-output pairs.
    Computes precision, recall, F1 on metric identification.
    Prints results table and failure analysis.
    """
    _ = ChatOpenAI(model="gpt-4o", temperature=0)

    # Load eval dataset
    eval_path = os.path.join(os.getcwd(), "evaluation", "eval_dataset.json")
    with open(eval_path, "r", encoding="utf-8") as f:
        eval_data = json.load(f)

    results = []

    for item in eval_data:
        # Build minimal state with just the transcript snippet
        # as prior_transcript (guidance extractor reads prior_transcript)
        state = create_initial_state("EVAL", "2020-Q1")
        state["prior_transcript"] = item["transcript_snippet"]
        state["input_valid"] = True

        # Run guidance extractor
        try:
            result = extract_guidance(state)
            extracted = result.get("guidance_items", [])
            extracted_count = len(extracted)
            extracted_metrics = [i.get("metric", "").lower() for i in extracted]
        except Exception:
            extracted_count = 0
            extracted_metrics = []

        # Evaluate
        expected_count = item["expected_guidance_count"]
        expected_metrics = [m.lower() for m in item["expected_metrics"]]
        has_guidance = item["has_guidance"]

        # True positive: extracted metric matches expected metric
        # Use substring matching (fuzzy)
        tp = sum(
            1
            for em in expected_metrics
            if any(em in xm or xm in em for xm in extracted_metrics)
        )
        fp = max(0, extracted_count - tp)
        fn = max(0, len(expected_metrics) - tp)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )

        results.append(
            {
                "id": item["id"],
                "has_guidance": has_guidance,
                "expected_count": expected_count,
                "extracted_count": extracted_count,
                "precision": round(precision, 2),
                "recall": round(recall, 2),
                "f1": round(f1, 2),
                "notes": item["notes"],
                "failure": f1 < 0.5 and has_guidance,
            }
        )

    # Print results table
    print("\n" + "=" * 70)
    print("GUIDANCE EXTRACTOR EVALUATION RESULTS")
    print("=" * 70)
    print(
        f"{'ID':>3} {'Expected':>8} {'Got':>5} "
        f"{'Precision':>10} {'Recall':>8} {'F1':>6} "
        f"{'Fail?':>6}"
    )
    print("-" * 70)

    for r in results:
        fail_flag = "❌" if r["failure"] else "✅"
        print(
            f"{r['id']:>3} {r['expected_count']:>8} "
            f"{r['extracted_count']:>5} "
            f"{r['precision']:>10.2f} {r['recall']:>8.2f} "
            f"{r['f1']:>6.2f} {fail_flag:>6}"
        )

    # Aggregate metrics
    positive_cases = [r for r in results if r["has_guidance"]]
    avg_precision = sum(r["precision"] for r in positive_cases) / len(positive_cases)
    avg_recall = sum(r["recall"] for r in positive_cases) / len(positive_cases)
    avg_f1 = sum(r["f1"] for r in positive_cases) / len(positive_cases)
    failure_count = sum(1 for r in results if r["failure"])

    print("-" * 70)
    print(f"{'AVG':>3} {'':>8} {'':>5} {avg_precision:>10.2f} {avg_recall:>8.2f} {avg_f1:>6.2f}")
    print(f"\nTotal failures (F1 < 0.5): {failure_count}/20")

    # Failure analysis
    failures = [r for r in results if r["failure"]]
    if failures:
        print("\n--- FAILURE ANALYSIS ---")
        for r in failures:
            item = eval_data[r["id"] - 1]
            print(f"\nID {r['id']}: {item['notes']}")
            print(f"  Expected: {item['expected_metrics']}")
            print(f"  Got {r['extracted_count']} items, F1={r['f1']}")
    else:
        print("\n✅ No failures — all cases F1 >= 0.5")

    print("\n📊 Final Scores:")
    print(f"   Precision: {avg_precision:.2f}")
    print(f"   Recall:    {avg_recall:.2f}")
    print(f"   F1:        {avg_f1:.2f}")

    return results


if __name__ == "__main__":
    run_evaluation()
