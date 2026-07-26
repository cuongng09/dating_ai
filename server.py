"""
Dating Chat AI — Local assistant powered by Ollama
Chạy hoàn toàn trên máy của bạn, không gửi dữ liệu ra ngoài (ngoại trừ tới Ollama nội bộ).
"""
import json
import os
import re
import time
import uuid
from datetime import datetime

import requests
from flask import Flask, Response, jsonify, request, send_from_directory

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
THREADS_DIR = os.path.join(DATA_DIR, "threads")
os.makedirs(THREADS_DIR, exist_ok=True)

app = Flask(__name__, static_folder="static", static_url_path="")

# ---------------------------------------------------------------------------
# System prompts cho từng chế độ (persona) hỗ trợ hẹn hò
# ---------------------------------------------------------------------------
MODES = {
    "coach": {
        "label": "Cố vấn hẹn hò",
        "subtitle": "Trò chuyện, xin lời khuyên, gỡ rối tình huống",
        "system": (
            "Bạn là một cố vấn hẹn hò thân thiện, tinh tế và trung thực. "
            "Bạn giúp người dùng hiểu tình huống hẹn hò của họ, đưa ra lời khuyên thực tế, "
            "khích lệ sự chân thành và tôn trọng đối phương. Không khuyến khích thao túng, "
            "lừa dối, gaslighting hay theo dõi người khác. Trả lời ngắn gọn, gần gũi, "
            "như một người bạn hiểu chuyện, có thể hỏi lại một câu để hiểu rõ tình huống hơn."
        ),
    },
    "practice": {
        "label": "Luyện tập hội thoại",
        "subtitle": "AI đóng vai bạn hẹn hò giả định để bạn luyện nói chuyện",
        "system": (
            "Bạn đang đóng vai MỘT NHÂN VẬT HƯ CẤU để người dùng luyện tập kỹ năng trò chuyện "
            "hẹn hò trước khi gặp người thật. Hãy nói rõ ngay từ tin nhắn đầu tiên rằng đây là "
            "một buổi luyện tập với nhân vật giả định, không phải người thật. Nhập vai tự nhiên, "
            "phản hồi như một người đang trò chuyện làm quen, nhưng luôn giữ ranh giới lành mạnh, "
            "lịch sự, không nội dung tình dục. Thỉnh thoảng đưa nhận xét ngắn (trong ngoặc) góp ý "
            "cho người dùng về cách họ vừa nhắn."
        ),
    },
    "rewrite": {
        "label": "Chỉnh sửa tin nhắn",
        "subtitle": "Dán tin nhắn nháp, AI giúp viết lại tự nhiên & cuốn hút hơn",
        "system": (
            "Người dùng sẽ dán một tin nhắn họ định gửi cho người họ đang tìm hiểu. "
            "Hãy: 1) nhận xét ngắn gọn điểm được/chưa được, 2) đề xuất 2-3 phiên bản viết lại "
            "với tông khác nhau (ví dụ: hài hước, chân thành, ngắn gọn), 3) không thay đổi ý định "
            "hay bịa thông tin cá nhân không có thật. Luôn giữ nội dung lịch sự, tôn trọng."
        ),
    },
    "icebreaker": {
        "label": "Câu mở đầu",
        "subtitle": "Gợi ý tin nhắn làm quen dựa trên thông tin profile đối phương",
        "system": (
            "Người dùng sẽ mô tả sở thích/ảnh/bio của người họ muốn nhắn tin làm quen. "
            "Hãy đề xuất 3-5 câu mở đầu (icebreaker) sáng tạo, cụ thể, không sáo rỗng, "
            "không đề cập ngoại hình gợi dục, phù hợp văn hóa Việt Nam. Giải thích ngắn vì sao "
            "mỗi câu có thể hiệu quả."
        ),
    },
    "bio": {
        "label": "Viết bio hẹn hò",
        "subtitle": "Xây dựng phần giới thiệu bản thân thu hút trên app hẹn hò",
        "system": (
            "Bạn giúp người dùng viết bio hồ sơ hẹn hò (Tinder, Bumble,...). Hỏi ngắn gọn về "
            "tính cách, sở thích, điều họ tìm kiếm nếu chưa đủ thông tin, sau đó đề xuất 2-3 "
            "phiên bản bio với độ dài và tông khác nhau. Trung thực, không phóng đại sai sự thật."
        ),
    },
    "dateplan": {
        "label": "Lên kế hoạch hẹn hò",
        "subtitle": "Gợi ý địa điểm, hoạt động cho buổi hẹn phù hợp ngân sách/sở thích",
        "system": (
            "Bạn giúp lên kế hoạch buổi hẹn hò. Hỏi về thành phố, ngân sách, sở thích chung, "
            "buổi hẹn đầu hay đã quen nhau nếu cần, rồi đề xuất 2-3 phương án cụ thể kèm lịch "
            "trình giờ giấc gợi ý và lưu ý an toàn (gặp ở nơi công cộng, báo bạn bè, v.v. cho "
            "lần hẹn đầu)."
        ),
    },
}

DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", "llama3.1")
MAX_HISTORY_MESSAGES = 30  # số tin nhắn gần nhất gửi cho model, tránh tràn ngữ cảnh
PROFILE_PATH = os.path.join(DATA_DIR, "profile.json")
STOP_FLAGS = {}  # thread_id -> True nghĩa là yêu cầu dừng tạo phản hồi


def load_profile():
    if not os.path.exists(PROFILE_PATH):
        return {}
    with open(PROFILE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_profile(data: dict):
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def profile_to_text(p: dict) -> str:
    if not p:
        return ""
    parts = []
    if p.get("name"):
        parts.append(f"tên {p['name']}")
    if p.get("age"):
        parts.append(f"{p['age']} tuổi")
    if p.get("gender"):
        parts.append(f"giới tính {p['gender']}")
    if p.get("looking_for"):
        parts.append(f"đang tìm kiếm: {p['looking_for']}")
    if p.get("interests"):
        parts.append(f"sở thích: {p['interests']}")
    if p.get("notes"):
        parts.append(f"ghi chú thêm: {p['notes']}")
    return "; ".join(parts)


# ---------------------------------------------------------------------------
# Helpers lưu trữ lịch sử (local, không có cloud)
# ---------------------------------------------------------------------------
def thread_path(thread_id: str) -> str:
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "", thread_id)
    return os.path.join(THREADS_DIR, f"{safe_id}.json")


def load_thread(thread_id: str):
    path = thread_path(thread_id)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_thread(thread_id: str, data: dict):
    with open(thread_path(thread_id), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Routes: static frontend
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


# ---------------------------------------------------------------------------
# Routes: modes / models
# ---------------------------------------------------------------------------
@app.route("/api/modes")
def get_modes():
    return jsonify(
        [{"id": k, "label": v["label"], "subtitle": v["subtitle"]} for k, v in MODES.items()]
    )


@app.route("/api/models")
def get_models():
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        r.raise_for_status()
        models = [m["name"] for m in r.json().get("models", [])]
        return jsonify({"ok": True, "models": models})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "models": []})


# ---------------------------------------------------------------------------
# Routes: threads (lịch sử trò chuyện)
# ---------------------------------------------------------------------------
@app.route("/api/threads")
def list_threads():
    items = []
    for fname in os.listdir(THREADS_DIR):
        if not fname.endswith(".json"):
            continue
        try:
            with open(os.path.join(THREADS_DIR, fname), "r", encoding="utf-8") as f:
                d = json.load(f)
            items.append(
                {
                    "id": d.get("id"),
                    "title": d.get("title", "Cuộc trò chuyện"),
                    "mode": d.get("mode", "coach"),
                    "updated_at": d.get("updated_at"),
                }
            )
        except Exception:
            continue
    items.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    return jsonify(items)


@app.route("/api/threads/<thread_id>", methods=["GET"])
def get_thread(thread_id):
    data = load_thread(thread_id)
    if data is None:
        return jsonify({"error": "not_found"}), 404
    return jsonify(data)


@app.route("/api/threads", methods=["POST"])
def create_thread():
    body = request.get_json(force=True) or {}
    mode = body.get("mode", "coach")
    thread_id = uuid.uuid4().hex[:12]
    now = datetime.now().isoformat()
    data = {
        "id": thread_id,
        "title": MODES.get(mode, MODES["coach"])["label"],
        "mode": mode,
        "messages": [],
        "created_at": now,
        "updated_at": now,
    }
    save_thread(thread_id, data)
    return jsonify(data)


@app.route("/api/threads/<thread_id>", methods=["DELETE"])
def delete_thread(thread_id):
    path = thread_path(thread_id)
    if os.path.exists(path):
        os.remove(path)
    return jsonify({"ok": True})


@app.route("/api/threads/<thread_id>/rename", methods=["POST"])
def rename_thread(thread_id):
    data = load_thread(thread_id)
    if data is None:
        return jsonify({"error": "not_found"}), 404
    body = request.get_json(force=True) or {}
    data["title"] = body.get("title", data["title"])[:60]
    save_thread(thread_id, data)
    return jsonify(data)


@app.route("/api/threads/<thread_id>/export")
def export_thread(thread_id):
    data = load_thread(thread_id)
    if data is None:
        return jsonify({"error": "not_found"}), 404
    lines = [f"# {data['title']}", f"Chế độ: {MODES.get(data['mode'], {}).get('label', data['mode'])}", ""]
    for m in data["messages"]:
        who = "Bạn" if m["role"] == "user" else "AI"
        lines.append(f"[{who}] {m['content']}")
        lines.append("")
    content = "\n".join(lines)
    return Response(
        content,
        mimetype="text/plain",
        headers={"Content-Disposition": f"attachment; filename=hoithoai_{thread_id}.txt"},
    )


# ---------------------------------------------------------------------------
# Route: hồ sơ cá nhân (dùng để cá nhân hoá lời khuyên)
# ---------------------------------------------------------------------------
@app.route("/api/profile", methods=["GET"])
def get_profile():
    return jsonify(load_profile())


@app.route("/api/profile", methods=["POST"])
def set_profile():
    body = request.get_json(force=True) or {}
    allowed = {"name", "age", "gender", "looking_for", "interests", "notes"}
    profile = {k: v for k, v in body.items() if k in allowed and str(v).strip()}
    save_profile(profile)
    return jsonify(profile)


@app.route("/api/health")
def health():
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        r.raise_for_status()
        models = [m["name"] for m in r.json().get("models", [])]
        return jsonify({"ollama_running": True, "models": models})
    except Exception:
        return jsonify({"ollama_running": False, "models": []})


@app.route("/api/chat/stop", methods=["POST"])
def stop_chat():
    body = request.get_json(force=True) or {}
    thread_id = body.get("thread_id")
    if thread_id:
        STOP_FLAGS[thread_id] = True
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Route: chat (streaming, gọi Ollama cục bộ)
# ---------------------------------------------------------------------------
@app.route("/api/chat", methods=["POST"])
def chat():
    body = request.get_json(force=True) or {}
    thread_id = body.get("thread_id")
    user_message = body.get("message", "").strip()
    model = body.get("model") or DEFAULT_MODEL
    temperature = float(body.get("temperature", 0.8))
    regenerate = bool(body.get("regenerate", False))

    data = load_thread(thread_id) if thread_id else None
    if data is None:
        return jsonify({"error": "thread_not_found"}), 404

    mode = data.get("mode", "coach")
    system_prompt = MODES.get(mode, MODES["coach"])["system"]
    profile_text = profile_to_text(load_profile())
    if profile_text:
        system_prompt += (
            "\n\nThông tin về người dùng để cá nhân hoá phản hồi (đừng liệt kê lại y nguyên, "
            "chỉ dùng ngầm để tư vấn phù hợp hơn): " + profile_text
        )

    if regenerate:
        while data["messages"] and data["messages"][-1]["role"] == "assistant":
            data["messages"].pop()
        if not data["messages"] or data["messages"][-1]["role"] != "user":
            return jsonify({"error": "nothing_to_regenerate"}), 400
    else:
        data["messages"].append({"role": "user", "content": user_message, "ts": time.time()})

    STOP_FLAGS[thread_id] = False

    history = data["messages"][-MAX_HISTORY_MESSAGES:]
    ollama_messages = [{"role": "system", "content": system_prompt}]
    for m in history:
        ollama_messages.append({"role": m["role"], "content": m["content"]})

    def generate():
        full_reply = ""
        try:
            with requests.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": model,
                    "messages": ollama_messages,
                    "stream": True,
                    "options": {"temperature": temperature},
                },
                stream=True,
                timeout=120,
            ) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if STOP_FLAGS.get(thread_id):
                        break
                    if not line:
                        continue
                    chunk = json.loads(line.decode("utf-8"))
                    piece = chunk.get("message", {}).get("content", "")
                    full_reply += piece
                    yield f"data: {json.dumps({'delta': piece}, ensure_ascii=False)}\n\n"
                    if chunk.get("done"):
                        break
        except Exception as e:
            err = f"[Lỗi kết nối Ollama: {e}. Kiểm tra Ollama đã chạy (ollama serve) và model '{model}' đã được tải (ollama pull {model}) chưa.]"
            full_reply = err
            yield f"data: {json.dumps({'delta': err}, ensure_ascii=False)}\n\n"

        STOP_FLAGS.pop(thread_id, None)
        data["messages"].append({"role": "assistant", "content": full_reply, "ts": time.time()})
        data["updated_at"] = datetime.now().isoformat()
        if data["title"] in (MODES.get(mode, {}).get("label"), "Cuộc trò chuyện") and len(data["messages"]) >= 2:
            data["title"] = user_message[:40] + ("…" if len(user_message) > 40 else "")
        save_thread(thread_id, data)
        yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"

    return Response(generate(), mimetype="text/event-stream")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    print(f"\n💬 Dating Chat AI đang chạy tại: http://localhost:{port}")
    print(f"   (Đảm bảo Ollama đang chạy tại {OLLAMA_URL})\n")
    app.run(host="0.0.0.0", port=port, debug=False)
