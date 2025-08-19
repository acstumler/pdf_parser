from typing import Tuple, Dict
from google.cloud import firestore
from clean_vendor_name import clean_vendor_name
import os

# Existing LLM fallback (already in this file per your repo)
def _fallback_account(allowed_accounts=None):
  return "7090 - Uncategorized Expense"

def classify_llm(memo: str, amount: float = 0.0, source: str = "", allowed_accounts=None) -> str:
  api_key = os.environ.get("OPENAI_API_KEY", "").strip()
  if not api_key:
    return _fallback_account(allowed_accounts)
  try:
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    system = "You classify financial transactions into EXACT account labels from a provided Chart of Accounts. Always return only one of the allowed labels. If nothing fits, choose the closest expense account."
    lines = [f"Memo: {memo}", f"Amount: {amount}", f"Source: {source}"]
    if allowed_accounts:
      lines.append("Allowed Accounts:")
      for a in allowed_accounts:
        lines.append(f"- {a}")
    prompt = "\n".join(lines)
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    resp = client.chat.completions.create(
      model=model,
      messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
      temperature=0.1,
      max_tokens=32
    )
    choice = (resp.choices[0].message.content or "").strip()
    if allowed_accounts:
      lower = {a.lower(): a for a in allowed_accounts}
      chosen = lower.get(choice.lower())
      if chosen:
        return chosen
      for a in allowed_accounts:
        if a.lower() in choice.lower():
          return a
      return _fallback_account(allowed_accounts)
    return choice or _fallback_account()
  except Exception:
    return _fallback_account(allowed_accounts)

def _get_user_memory(db: firestore.Client, uid: str, vendor_key: str) -> str:
  try:
    ref = db.collection("users").document(uid).collection("vendor_memory").document(vendor_key)
    snap = ref.get()
    if snap.exists:
      data = snap.to_dict() or {}
      acct = str(data.get("account") or "")
      return acct
  except Exception:
    pass
  return ""

def _get_global_memory(db: firestore.Client, vendor_key: str) -> str:
  try:
    ref = db.collection("vendor_memory_global").document(vendor_key)
    snap = ref.get()
    if snap.exists:
      data = snap.to_dict() or {}
      acct = str(data.get("account") or "")
      return acct
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
  """
  Returns (account, via) if found in memory; otherwise ("", "")
  via = "memory:user" or "memory:global"
  """
  if user_mem_cache is None:
    user_mem_cache = {}
  if global_mem_cache is None:
    global_mem_cache = {}

  # user memory
  if vendor_key in user_mem_cache:
    val = user_mem_cache[vendor_key]
  else:
    val = _get_user_memory(db, uid, vendor_key)
    user_mem_cache[vendor_key] = val
  if val:
    return val, "memory:user"

  # global memory
  if vendor_key in global_mem_cache:
    gval = global_mem_cache[vendor_key]
  else:
    gval = _get_global_memory(db, vendor_key)
    global_mem_cache[vendor_key] = gval
  if gval:
    return gval, "memory:global"

  return "", ""
