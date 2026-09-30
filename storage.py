import os
import re
import json
import hashlib

VAULT_DIR = "local_vault"
USERS_FILE = os.path.join(VAULT_DIR, "users.json")
CASES_DIR = os.path.join(VAULT_DIR, "cases")

def hash_val(val: str) -> str:
    return hashlib.sha256(val.strip().encode("utf-8")).hexdigest()

def sanitize_name(name: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_-]', '_', name.strip())

def ensure_storage_ready():
    os.makedirs(VAULT_DIR, exist_ok=True)
    os.makedirs(CASES_DIR, exist_ok=True)
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=4)

ensure_storage_ready()

def load_users() -> dict:
    ensure_storage_ready()
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return {}
            return json.loads(content)
    except Exception:
        return {}

def save_users(users: dict):
    ensure_storage_ready()
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=4)
        f.flush()
        os.fsync(f.fileno())

def register_user(username: str, password: str, org_name: str) -> tuple[bool, str]:
    users = load_users()
    u_clean = username.strip().lower()
    
    if not u_clean or not password.strip() or not org_name.strip():
        return False, "All verification fields are required."
    
    if u_clean in users:
        return False, f"Handle '{username.strip()}' is already registered."
    
    users[u_clean] = {
        "display_name": username.strip(),
        "password": hash_val(password),
        "org": org_name.strip()
    }
    save_users(users)
    get_org_dir(org_name.strip())
    return True, f"Operative '{username.strip()}' registered successfully!"

def authenticate_user(username: str, password: str) -> tuple[bool, str]:
    users = load_users()
    u_clean = username.strip().lower()
    
    if not u_clean:
        return False, "Please enter an operative handle."
    
    if u_clean not in users:
        return False, f"Operative '{username.strip()}' not found on this machine. Please register first."
    
    stored_hash = users[u_clean].get("password")
    if stored_hash == hash_val(password):
        # Fallback to username if display_name is missing from older accounts
        display_name = users[u_clean].get("display_name", username.strip())
        return True, display_name
    else:
        return False, "Invalid clearance password."
def get_org_dir(org_name: str) -> str:
    ensure_storage_ready()
    path = os.path.join(CASES_DIR, sanitize_name(org_name))
    os.makedirs(path, exist_ok=True)
    return path

def load_org_cases(org_name: str) -> dict:
    org_dir = get_org_dir(org_name)
    cases = {}
    if not os.path.exists(org_dir):
        return cases

    for filename in sorted(os.listdir(org_dir)):
        if filename.endswith(".json"):
            filepath = os.path.join(org_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    case_id = data.get("id", filename.replace(".json", ""))
                    cases[case_id] = data
            except Exception:
                continue
    return cases

def save_case(org_name: str, case_id: str, case_data: dict):
    org_dir = get_org_dir(org_name)
    filepath = os.path.join(org_dir, f"{case_id}.json")
    case_data["id"] = case_id
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(case_data, f, indent=4)
        f.flush()
        os.fsync(f.fileno())

def delete_case_from_disk(org_name: str, case_id: str):
    org_dir = get_org_dir(org_name)
    filepath = os.path.join(org_dir, f"{case_id}.json")
    if os.path.exists(filepath):
        os.remove(filepath)

