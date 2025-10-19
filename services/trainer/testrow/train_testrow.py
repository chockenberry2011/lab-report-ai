import json, argparse, os, joblib
from pathlib import Path
import sklearn_crfsuite
from sklearn_crfsuite import metrics
from collections import Counter
from datetime import datetime, timezone

try:
    # Prefer package version if available
    from services.trainer.testrow import __version__ as TRAINER_VERSION
except Exception:
    TRAINER_VERSION = "unknown"

def tok2feats(tokens, i):
    w = tokens[i]
    feats = {
        "bias": 1.0,
        "w.lower": w.lower(),
        "w.isdigit": w.isdigit(),
        "w.isalpha": w.isalpha(),
        "w.isalnum": w.isalnum(),
        "pref1": w[:1].lower(),
        "pref2": w[:2].lower(),
        "suf1": w[-1:].lower(),
        "suf2": w[-2:].lower(),
        "shape": "".join("A" if c.isupper() else "a" if c.islower() else "9" if c.isdigit() else c for c in w)[:6]
    }
    if i > 0:
        p = tokens[i-1]
        feats.update({"-1:lower": p.lower(), "-1:shape": "".join("A" if c.isupper() else "a" if c.islower() else "9" if c.isdigit() else c for c in p)[:6]})
    else:
        feats["BOS"] = True
    if i < len(tokens)-1:
        n = tokens[i+1]
        feats.update({"+1:lower": n.lower(), "+1:shape": "".join("A" if c.isupper() else "a" if c.islower() else "9" if c.isdigit() else c for c in n)[:6]})
    else:
        feats["EOS"] = True
    return feats

def sent2feats(tokens):
    return [tok2feats(tokens, i) for i in range(len(tokens))]

def load_jsonl(p):
    X, y = [], []
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            rec = json.loads(line)
            toks = rec["tokens"]
            tags = rec["tags"]
            X.append(sent2feats(toks))
            y.append(tags)
    return X, y

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("training_data", help="train.jsonl")
    ap.add_argument("--dev", help="dev.jsonl")
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--c1", type=float, default=0.1)
    ap.add_argument("--c2", type=float, default=0.1)
    ap.add_argument("--max-iter", type=int, default=200)
    args = ap.parse_args()

    X_train, y_train = load_jsonl(args.training_data)
    X_dev, y_dev = (None, None)
    if args.dev and os.path.exists(args.dev):
        X_dev, y_dev = load_jsonl(args.dev)

    # Labels will be taken from the trained CRF's classes_ to preserve order
    # Fall back to training data-derived set if unavailable
    labels_from_train = sorted({t for seq in y_train for t in seq})

    crf = sklearn_crfsuite.CRF(
        algorithm="lbfgs",
        c1=args.c1, c2=args.c2,
        max_iterations=args.max_iter,
        all_possible_transitions=True
    )
    crf.fit(X_train, y_train)
    os.makedirs(args.output_dir, exist_ok=True)
    joblib.dump(crf, os.path.join(args.output_dir, "crf.joblib"))

    # Resolve label list in the order used by the CRF
    try:
        labels_order = list(getattr(crf, "classes_", [])) or labels_from_train
    except Exception:
        labels_order = labels_from_train

    # Ensure labels are strings
    labels_order = [str(x) for x in labels_order]

    # Build metadata payload
    metadata = {
        "model_type": "crf",
        "labels": labels_order,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "trainer_version": TRAINER_VERSION,
    }

    # Write/overwrite metadata.json alongside the model
    with open(os.path.join(args.output_dir, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    if X_dev:
        y_pred = crf.predict(X_dev)
        print(metrics.flat_classification_report(y_dev, y_pred, digits=3))

if __name__ == "__main__":
    main()
