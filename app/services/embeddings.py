from app.services.gemini_llm import client
import time
import re

def get_retry_delay(error_exception) -> float | None:
    try:
        err_msg = str(error_exception)
        # Extract the sleep delay if specified by the Gemini quota error
        match = re.search(r"Please retry in (\d+\.?\d*)s", err_msg)
        if match:
            return float(match.group(1)) + 1.0
    except Exception:
        pass
    return None

def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    
    print(f"      [EMBEDDINGS] Encoding {len(texts)} texts individually using Gemini Cloud Embeddings ('gemini-embedding-2')...")
    
    all_embeddings = []
    
    for text in texts:
        success = False
        last_exception = None
        
        # Attempt to embed the text with retries and backoff
        for attempt in range(6):
            if attempt > 0:
                sleep_time = (2 ** attempt) + 5.0
                delay_from_err = get_retry_delay(last_exception)
                if delay_from_err is not None:
                    sleep_time = delay_from_err
                    print(f"      [EMBEDDINGS] Quota exceeded. Waiting {sleep_time:.2f}s as requested by API...")
                else:
                    print(f"      [EMBEDDINGS] Rate limit hit. Waiting {sleep_time:.2f}s before retry (Attempt {attempt+1}/6)...")
                time.sleep(sleep_time)
            
            try:
                response = client.models.embed_content(
                    model="gemini-embedding-2",
                    contents=text
                )
                if response.embeddings:
                    all_embeddings.append(response.embeddings[0].values)
                success = True
                break  # Success, exit the retry loop
            except Exception as e:
                last_exception = e
                err_str = str(e).upper()
                print(f"      [EMBEDDINGS] Model failed with error: {e}")
                
                # If rate limited or transient error, retry
                if any(term in err_str for term in ["429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE", "500"]):
                    continue
                raise e  # Permanent configuration/api errors are raised immediately
        
        if not success:
            print(f"      [EMBEDDINGS] Failed to embed text after multiple attempts.")
            raise last_exception
            
    print("      [EMBEDDINGS] Cloud encoding complete.")
    return all_embeddings


def embed_texts_parallel(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    
    import concurrent.futures
    max_workers = 10
    
    def embed_single(index: int, text: str) -> tuple[int, list[float]]:
        success = False
        last_exception = None
        for attempt in range(4):
            if attempt > 0:
                sleep_time = (2 ** attempt) + 2.0
                delay_from_err = get_retry_delay(last_exception)
                if delay_from_err is not None:
                    sleep_time = delay_from_err
                time.sleep(sleep_time)
            try:
                response = client.models.embed_content(
                    model="gemini-embedding-2",
                    contents=text
                )
                if response.embeddings:
                    return index, response.embeddings[0].values
            except Exception as e:
                last_exception = e
                err_str = str(e).upper()
                if any(term in err_str for term in ["429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE", "500"]):
                    continue
                raise e
        raise last_exception if last_exception else ValueError(f"Failed to embed: {text}")

    print(f"      [EMBEDDINGS] Encoding {len(texts)} texts in parallel...")
    
    results = [None] * len(texts)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(embed_single, idx, text) for idx, text in enumerate(texts)]
        for future in concurrent.futures.as_completed(futures):
            idx, embedding = future.result()
            results[idx] = embedding
            
    return results

