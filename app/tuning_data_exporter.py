import sqlite3
import json
import csv
import os

# Connect to the SQLite database
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "db", "docusense.db")
OUTPUT_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resume_bullet_tuning_data.csv")

def export_tuning_data():
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] Database file not found at: {DB_PATH}")
        return

    print(f"[EXPORTER] Connecting to SQLite database at {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Fetch all resume analyses
        cursor.execute("SELECT id, rewrite_suggestions_json FROM resume_analyses")
        rows = cursor.fetchall()
        
        training_pairs = []
        for row in rows:
            analysis_id = row[0]
            suggestions_str = row[1]
            if not suggestions_str:
                continue
                
            try:
                suggestions = json.loads(suggestions_str)
                if not isinstance(suggestions, list):
                    continue
                    
                for s in suggestions:
                    original = s.get("original", "").strip()
                    suggested = s.get("suggested", "").strip()
                    rationale = s.get("rationale", "").strip()
                    
                    if original and suggested:
                        # Construct a structured prompt for fine-tuning
                        user_prompt = f"Rewrite this weak or descriptive resume bullet point into a strong, metrics-driven, action-oriented bullet point using the Google X-Y-Z formula (Accomplished [X] as measured by [Y], by doing [Z]):\n\"{original}\""
                        model_response = f"\"{suggested}\"\n\nRationale: {rationale}"
                        
                        training_pairs.append({
                            "input": user_prompt,
                            "output": model_response
                        })
            except Exception as e:
                print(f"[EXPORTER] Failed to parse row {analysis_id}: {e}")
                
        if not training_pairs:
            print("[EXPORTER] No rewrite training pairs found in the database. Run some resume analyses first!")
            return

        print(f"[EXPORTER] Exporting {len(training_pairs)} training pairs to {OUTPUT_CSV}...")
        with open(OUTPUT_CSV, mode="w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["input", "output"])
            writer.writeheader()
            writer.writerows(training_pairs)
            
        print(f"[SUCCESS] Training dataset exported successfully to {OUTPUT_CSV}!")
        print("You can now upload this CSV directly to Google AI Studio to fine-tune a model.")
        
    except Exception as e:
        print(f"[ERROR] Failed to query database: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    export_tuning_data()
