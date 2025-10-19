import json, argparse, os, joblib
from sklearn_crfsuite import metrics
from pathlib import Path

def load_jsonl(p):
    X, y = [], []
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            rec = json.loads(line)
            X.append(rec["tokens"])
            y.append(rec["tags"])
    return X, y

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

def sent2feats(tokens): return [tok2feats(tokens, i) for i in range(len(tokens))]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data", help="dev.jsonl")
    ap.add_argument("--model-dir", required=True)
    args = ap.parse_args()

    toks, y_true = load_jsonl(args.data)
    X = [sent2feats(t) for t in toks]

    crf = joblib.load(os.path.join(args.model_dir, "crf.joblib"))
    y_pred = crf.predict(X)
    print(metrics.flat_classification_report(y_true, y_pred, digits=3))

if __name__ == "__main__":
    main()