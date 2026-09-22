import modal

def main():
    print("Looking up deployed function 'run' from app 'satquery-m1-training'...")
    try:
        f = modal.Function.from_name("satquery-m1-training", "run")
    except modal.exception.NotFoundError:
        print("ERROR: Could not find the deployed app.")
        print("Please run this command first:\n  modal deploy modal_worker/train_m1.py")
        return
        
    print("Spawning function in the background...")
    call = f.spawn()
    
    print(f"\n[DONE] Job launched persistently on Modal!")
    print(f"View progress at: https://modal.com/logs/call/{call.object_id}")
    print("\nYou can now safely close your terminal. The job will not be interrupted.")

if __name__ == "__main__":
    main()
