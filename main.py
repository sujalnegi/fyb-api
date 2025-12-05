import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import numpy as np
import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from pydantic import BaseModel, ValidationError
from scipy.spatial.distance import cdist
from werkzeug.exceptions import BadRequest

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[
    logging.FileHandler("server.log"),
    logging.StreamHandler()
])
logger = logging.getLogger(__name__)

with open("debug.txt", "w") as f:
    f.write("Server script started\n")

BASE_DIR = Path(__file__).resolve().parent
HOBBIES_PATH = BASE_DIR / "hobbies.json"
with open("debug.txt", "a") as f:
    f.write(f"BASE_DIR: {BASE_DIR}\n")
    f.write(f"HOBBIES_PATH: {HOBBIES_PATH}\n")
    f.write(f"Exists: {HOBBIES_PATH.exists()}\n")
EMB_PATH = BASE_DIR / "hobby_emb_gemini.npy"
DOCS_PATH = BASE_DIR / "hobby_docs.json"
MODEL_NAME = "models/text-embedding-004"

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

class Answers(BaseModel):
    interest: Optional[str] = ""
    environment: Optional[str] = "both"
    physical: Optional[str] = "low"
    creative: Optional[str] = "no"
    social: Optional[str] = "either"
    budget: Optional[str] = "low"
    time: Optional[str] = "medium"

class AppState:
    def __init__(self):
        self.hobbies: List[Dict[str, Any]] = []
        self.model = None
        self.hobby_embeddings: Optional[np.ndarray] = None
        self.hobby_docs: List[str] = []

    def load_hobbies(self):
        try:
            if not HOBBIES_PATH.exists():
                logger.error(f"Hobbies file not found at {HOBBIES_PATH}")
                self.hobbies = []
                return

            with open(HOBBIES_PATH, "r", encoding="utf-8") as f:
                raw = json.load(f)

            self.hobbies = []
            if isinstance(raw, list):
                for item in raw:
                    if isinstance(item, dict):
                        self.hobbies.append(item)
                    elif isinstance(item, list): 
                        for sub in item:
                            if isinstance(sub, dict):
                                self.hobbies.append(sub)
            elif isinstance(raw, dict):
                self.hobbies = [raw]
            
            logger.info(f"Loaded {len(self.hobbies)} hobbies.")

        except Exception as e:
            logger.error(f"Failed to load hobbies: {e}")
            self.hobbies = []

    def build_docs(self) -> List[str]:
        out = []
        for h in self.hobbies:
            parts = [h.get("name", ""), h.get("short", "")] + h.get("interests", [])
            txt = " | ".join([str(x) for x in parts if x])
            out.append(txt)
        return out

    def load_or_build_embeddings(self):
        try:
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                logger.error("GEMINI_API_KEY not found in environment variables.")
                self.hobby_embeddings = None
                return

            genai.configure(api_key=api_key)
            
            if EMB_PATH.exists() and DOCS_PATH.exists():
                try:
                    mats = np.load(str(EMB_PATH))
                    with open(DOCS_PATH, "r", encoding="utf-8") as f:
                        docs = json.load(f)
                    
                    if len(docs) == len(self.hobbies) and mats.shape[0] == len(self.hobbies):
                        self.hobby_embeddings = mats
                        self.hobby_docs = docs
                        logger.info("Loaded cached embeddings.")
                        return
                except Exception as e:
                    logger.warning(f"Failed to load cached embeddings, rebuilding: {e}")

            logger.info("Building new embeddings...")
            self.hobby_docs = self.build_docs()
            if not self.hobby_docs:
                 logger.warning("No documents to embed.")
                 self.hobby_embeddings = None
                 return

            # Generate embeddings using Gemini API
            result = genai.embed_content(
                model=MODEL_NAME,
                content=self.hobby_docs,
                task_type="retrieval_document"
            )
            
            self.hobby_embeddings = np.array(result['embedding'])
            
            np.save(str(EMB_PATH), self.hobby_embeddings)
            with open(DOCS_PATH, "w", encoding="utf-8") as f:
                json.dump(self.hobby_docs, f, ensure_ascii=False, indent=2)
            logger.info("Embeddings built and saved.")

        except Exception as e:
            logger.error(f"Failed to initialize embeddings: {e}")
            self.hobby_embeddings = None
            self.hobby_docs = []

state = AppState()

def safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except (ValueError, TypeError):
        return default

def score_and_reasons(h: Dict[str, Any], a: Answers) -> Tuple[float, List[str]]:
    s = 0.0
    reasons: List[str] = []
    
    try:
        interests = [str(x).lower() for x in h.get("interests", [])]
        if a.interest and a.interest.strip().lower() in interests:
            s += 3.0
            reasons.append("Matches your interest")
    except Exception:
        pass 
    pref = safe_float(h.get("pref_indoor", 0))
    if a.environment == "indoor" and pref > 0:
        s += 1.0 * pref
        reasons.append("Good for indoor preference")
    elif a.environment == "outdoor" and pref < 0:
        s += 1.0 * abs(pref)
        reasons.append("Good for outdoor preference")

    if a.creative == "yes" and safe_float(h.get("creative", 0)) > 0:
        s += 1.0
        reasons.append("Suits creative preference")

    social_val = safe_float(h.get("social", 0))
    if a.social == "solo" and social_val >= 0:
        s += 0.5
        reasons.append("Solo-friendly")
    elif a.social == "group" and social_val <= 0:
        s += 0.5
        reasons.append("Group-friendly")

    cost = max(safe_float(h.get("cost_level", 1)), 1.0)
    if a.budget == "low":
        s += 1.0 / cost
        reasons.append("Fits low budget")

    time_need = safe_float(h.get("time_hours", h.get("time_per_week_hours", 0)))
    if a.time == "low":
        if time_need <= 3:
            s += 1.0
            reasons.append("Low weekly time needed")
    elif a.time == "high":
        time_commit = safe_float(h.get("time_commit", h.get("time_hours", 0)))
        s += time_commit * 0.2

    return float(s), reasons

def format_data(h: Dict[str, Any], score: float, reasons: List[str]) -> Dict[str, Any]:
    cost_label = h.get("cost_label") or h.get("cost_level_label") or "Unknown"
    difficulty_label = h.get("difficulty") or h.get("difficulty_label") or "Unknown"
    
    return {
        "name": h.get("name", "Unknown Hobby"),
        "short": h.get("short", ""),
        "cost_level": cost_label,
        "difficulty": difficulty_label,
        "time_per_week_hours": h.get("time_hours", h.get("time_per_week_hours", 0)),
        "how_to_start": h.get("how_to_start", []),
        "why_fit": reasons,
        "match_score": round(score, 2)
    }

def topk_by_embedding(user_text: str, k: int = 10) -> Tuple[List[int], List[float]]:
    if state.hobby_embeddings is None:
        n = min(k, len(state.hobbies))
        return list(range(n)), [0.0] * n
    
    try:
        result = genai.embed_content(
            model=MODEL_NAME,
            content=user_text,
            task_type="retrieval_query"
        )
        ue = np.array([result['embedding']])
        
        dists = cdist(ue, state.hobby_embeddings, metric="cosine")[0]
        sims = 1.0 - dists
        idx = np.argsort(dists)[:k]
        return idx.tolist(), sims[idx].tolist()
    except Exception as e:
        logger.error(f"Error in embedding search: {e}")
        n = min(k, len(state.hobbies))
        return list(range(n)), [0.0] * n

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/hobbies", methods=["GET"])
def all_hobbies():
    try:
        results = []
        for h in state.hobbies:
            s, reasons = score_and_reasons(h, Answers())
            results.append(format_data(h, s, reasons))
        return jsonify(results)
    except Exception as e:
        logger.error(f"Error in /hobbies: {e}")
        return jsonify({"error": "Failed to prepare hobbies", "detail": str(e)}), 500

@app.route("/suggest", methods=["POST"])
def suggest():
    with open("debug.txt", "a") as f:
        f.write("Entered /suggest\n")
    try:
        try:
            payload = request.get_json(force=True)
        except BadRequest:
            return jsonify({"error": "Invalid JSON"}), 400

        if payload is None:
             return jsonify({"error": "Empty payload"}), 400
             
        try:
            a = Answers.model_validate(payload)
        except ValidationError as ve:
            return jsonify({"error": "Invalid payload", "detail": ve.errors()}), 400

        user_text = f"{a.interest} | env:{a.environment} | creative:{a.creative} | social:{a.social} | budget:{a.budget} | time:{a.time}"
        
        idxs, sims = topk_by_embedding(user_text, k=10)
        
        candidates: List[Tuple[float, Dict[str, Any], List[str]]] = []
        
        for i, sim in zip(idxs, sims):
            if i >= len(state.hobbies): continue
            
            h = state.hobbies[int(i)]
            embed_score = float(sim)
            
            rule_score, reasons = score_and_reasons(h, a)
            rule_norm = rule_score / (rule_score + 1.0) 
            
            final = 0.6 * embed_score + 0.4 * rule_norm
            
            merged_reasons = reasons.copy()
            merged_reasons.append(f"embed_sim={round(embed_score, 2)}")
            
            candidates.append((final, h, merged_reasons))
        
        candidates.sort(key=lambda x: x[0], reverse=True)
        
        top = [format_data(h, float(score) * 10.0, reasons) for score, h, reasons in candidates[:3]]
        return jsonify(top)

    except Exception as e:
        logger.error(f"Error in /suggest: {e}")
        return jsonify({"error": "Suggestion error", "detail": str(e)}), 500

state.load_hobbies()
state.load_or_build_embeddings()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001, debug=False)
