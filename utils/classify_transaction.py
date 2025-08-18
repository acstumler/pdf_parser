import os

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
