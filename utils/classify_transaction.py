from typing import Tuple, Dict, Any
from google.cloud import firestore
import os

def _fallback_account(allowed_accounts=None) -> str:
    if allowed_accounts:
        lowers = {a.lower(): a for a in allowed_accounts}
        for key in ("uncategorized", "7090 - uncategorized expense", "7090-uncategorized expense"):
            for k, v in lowers.items():
                if key in k:
                    return v
        return allowed_accounts[0]
    return "7090 - Uncategorized Expense"

def _force_map_to_allowed(chosen: str, allowed_accounts: list[str] | None) -> str:
    if not chosen:
        return _fallback_account(allowed_accounts)
    if not allowed_accounts:
        return chosen
    lc_map = {a.lower(): a for a in allowed_accounts}
    c = chosen.strip().lower()
    if c in lc_map:
        return lc_map[c]
    for a in allowed_accounts:
        al = a.lower()
        if c in al or al in c:
            return a
    ctoks = [t for t in c.split(" ") if t]
    best = None
    best_hits = -1
    for a in allowed_accounts:
        toks = [t for t in a.lower().split(" ") if t]
        hits = sum(1 for t in ctoks if t in toks)
        if hits > best_hits:
            best = a
            best_hits = hits
    return best or _fallback_account(allowed_accounts)

def classify_llm(memo: str, amount: float = 0.0, source: str = "", allowed_accounts=None) -> str:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return _fallback_account(allowed_accounts)
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        system = "You classify SMB financial transactions into one exact account label from a provided Chart of Accounts. Return ONLY the chosen label. If uncertain, choose the closest expense account."
        lines = [
            f"Memo: {memo}",
            f"Amount: {amount}",
            f"Source: {source}",
            "You must choose exactly one of these account labels:"
        ]
        if allowed_accounts:
            for a in allowed_accounts:
                lines.append(f"- {a}")
        prompt = "\n".join(lines)
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=16
        )
        raw = (resp.choices[0].message.content or "").strip()
        return _force_map_to_allowed(raw, allowed_accounts)
    except Exception:
        return _fallback_account(allowed_accounts)

def _get_user_memory(db: firestore.Client, uid: str, vendor_key: str) -> str:
    try:
        ref = db.collection("users").document(uid).collection("vendor_memory").document(vendor_key)
        snap = ref.get()
        if snap.exists:
            data = snap.to_dict() or {}
            return str(data.get("account") or "")
    except Exception:
        pass
    return ""

def _get_global_memory(db: firestore.Client, vendor_key: str) -> str:
    try:
        ref = db.collection("vendor_memory_global").document(vendor_key)
        snap = ref.get()
        if snap.exists:
            data = snap.to_dict() or {}
            return str(data.get("account") or "")
    except Exception:
        pass
    return ""

def classify_with_memory(
    db: firestore.Client,
    uid: str,
    vendor_key: str,
    user_mem_cache: Dict[str, str] | None = None,
    global_mem_cache: Dict[str, str] | None = None
) -> Tuple[str, str]:
    if user_mem_cache is None:
        user_mem_cache = {}
    if global_mem_cache is None:
        global_mem_cache = {}
    if vendor_key in user_mem_cache:
        val = user_mem_cache[vendor_key]
    else:
        val = _get_user_memory(db, uid, vendor_key)
        user_mem_cache[vendor_key] = val
    if val:
        return val, "memory:user"
    if vendor_key in global_mem_cache:
        gval = global_mem_cache[vendor_key]
    else:
        gval = _get_global_memory(db, vendor_key)
        global_mem_cache[vendor_key] = gval
    if gval:
        return gval, "memory:global"
    return "", ""

def infer_from_structure(amount: float, source: str, allowed_accounts: list[str] | None) -> str:
    return ""

def _bump_vendor_aggregate(db: firestore.Client, vendor_key: str, account: str, uid: str) -> None:
    agg = db.collection("vendor_memory_agg").document(vendor_key)
    snap = agg.get()
    if snap.exists:
        data = snap.to_dict() or {}
    else:
        data = {"total": 0, "byAccount": {}, "users": []}
    users = set(data.get("users", []))
    by_account = dict(data.get("byAccount", {}))
    total = int(data.get("total", 0))
    by_account[account] = int(by_account.get(account, 0)) + 1
    total += 1
    users.add(uid)
    agg.set({"total": total, "byAccount": by_account, "users": list(users)}, merge=True)
    top_account = max(by_account.items(), key=lambda kv: kv[1])[0]
    if total >= 5 and len(users) >= 3:
        db.collection("vendor_memory_global").document(vendor_key).set({"account": top_account}, merge=True)

def finalize_classification(
    db: firestore.Client,
    uid: str,
    vendor_key: str,
    memo: str,
    amount: float,
    source: str,
    allowed_accounts: list[str] | None
) -> Tuple[str, str]:
    acc, via = classify_with_memory(db=db, uid=uid, vendor_key=vendor_key, user_mem_cache={}, global_mem_cache={})
    if acc:
        return acc, via
    acc_struct = infer_from_structure(amount, source, allowed_accounts)
    if acc_struct:
        return _force_map_to_allowed(acc_struct, allowed_accounts), "ml"
    acc_ai = classify_llm(memo=memo, amount=amount, source=source, allowed_accounts=allowed_accounts)
    return _force_map_to_allowed(acc_ai, allowed_accounts), "ai"

def record_learning(db: firestore.Client, vendor_key: str, account: str, uid: str) -> None:
    try:
        _bump_vendor_aggregate(db, vendor_key, account, uid)
    except Exception:
        pass
