from fastapi import FastAPI, Request, HTTPException
from groq import Groq
from dotenv import load_dotenv
import httpx, os, hmac, hashlib, json

load_dotenv()
app = FastAPI()
client = Groq()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

PROMPT = """Review code diff sau, đưa ra 5 nhận xét ngắn gọn:
{diff}

Nhận xét về: bugs, security, performance, readability, điểm tốt."""

def verify(payload: bytes, sig: str) -> bool:
    if not WEBHOOK_SECRET:
        return True
    mac = hmac.new(WEBHOOK_SECRET.encode(), payload, hashlib.sha256)
    return hmac.compare_digest(f"sha256={mac.hexdigest()}", sig)

async def get_diff(owner, repo, pr_num):
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_num}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}",
               "Accept": "application/vnd.github.v3.diff"}
    async with httpx.AsyncClient() as h:
        r = await h.get(url, headers=headers)
        return r.text[:5000]

async def post_comment(owner, repo, pr_num, body):
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_num}/comments"
    headers = {"Authorization": f"token {GITHUB_TOKEN}",
               "Accept": "application/vnd.github.v3+json"}
    async with httpx.AsyncClient() as h:
        await h.post(url, headers=headers, json={"body": body})

@app.post("/webhook")
async def webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("X-Hub-Signature-256", "")
    if not verify(payload, sig):
        raise HTTPException(status_code=401)

    event = request.headers.get("X-GitHub-Event", "")
    data = json.loads(payload)

    if event == "pull_request" and data.get("action") in ["opened", "synchronize"]:
        pr = data["pull_request"]
        owner = data["repository"]["owner"]["login"]
        repo = data["repository"]["name"]
        pr_num = pr["number"]

        diff = await get_diff(owner, repo, pr_num)
        if not diff.strip():
            return {"status": "no_diff"}

        review = client.chat.completions.create(
            model="qwen/qwen3-32b",
            messages=[{"role": "user", "content": PROMPT.format(diff=diff)}],
            max_tokens=500, temperature=0.1
        ).choices[0].message.content

        comment = f"## 🤖 AI Code Review\n\n{review}\n\n---\n*Auto-review by AI Bot*"
        await post_comment(owner, repo, pr_num, comment)

    return {"status": "ok"}

@app.get("/health")
def health():
    return {"status": "ok"}